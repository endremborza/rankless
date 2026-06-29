"""Local Rust server lifecycle management."""

import os
import re
import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import requests
from tqdm import tqdm

DEFAULT_BINARY = Path("target/release/rankless-server")
DEFAULT_PORT = 3038


def _base_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


DEFAULT_BE_ADDR = os.environ.get("RANKLESS_BE_URL") or _base_url(DEFAULT_PORT)


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def container_state(name: str) -> tuple[bool, int]:
    """(running, exit_code). running=False with exit_code=-1 if the container is gone."""
    r = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Running}} {{.State.ExitCode}}",
            name,
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return (False, -1)
    parts = r.stdout.split()
    return (parts[0] == "true", int(parts[-1]))


def container_logs(name: str, tail: int = 50) -> str:
    r = subprocess.run(
        ["docker", "logs", "--tail", str(tail), name], capture_output=True, text=True
    )
    return (r.stdout + r.stderr).strip() or "(no container logs)"


def wait_for_url(
    spec_url: str,
    max_attempts: int,
    desc: str,
    dead_check: Optional[Callable[[], bool]] = None,
    on_fail: Optional[Callable[[], str]] = None,
    accept_any: bool = False,
) -> None:
    """Poll until the URL responds. Fail fast if ``dead_check`` reports death.

    ``accept_any`` treats any HTTP response (even 4xx) as ready — for servers
    with no health endpoint. ``on_fail`` returns diagnostics (e.g. container
    logs) appended to death/timeout errors so failures are self-explanatory.
    """

    def _diag() -> str:
        return f"\n--- logs ---\n{on_fail()}" if on_fail else ""

    for _ in tqdm(range(max_attempts), desc=desc):
        try:
            r = requests.get(spec_url, timeout=5)
            if accept_any or r.ok:
                return
        except Exception:
            pass
        if dead_check and not dead_check():
            raise RuntimeError(f"{desc}: died before becoming ready.{_diag()}")
        time.sleep(3)
    raise TimeoutError(f"{desc}: not ready after {max_attempts * 3}s.{_diag()}")


@dataclass
class ServerConfig:
    data_root: Path
    binary: Path = field(default_factory=lambda: DEFAULT_BINARY)
    port: int = DEFAULT_PORT

    @property
    def base_url(self) -> str:
        return _base_url(self.port)

    @property
    def spec_url(self) -> str:
        return f"{self.base_url}/v1/specs"


class ServerProcess:
    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self._proc: Optional[subprocess.Popen] = None
        self._log_path: Optional[Path] = None
        self._log_handle = None

    @property
    def pid(self) -> Optional[int]:
        return self._proc.pid if self._proc else None

    def assert_port_free(self) -> None:
        try:
            r = requests.get(self.config.spec_url, timeout=2)
            if r.ok:
                raise RuntimeError(f"Server already running at {self.config.base_url}")
        except RuntimeError:
            raise
        except Exception:
            pass

    def start(self, log_path: Optional[Path] = None) -> None:
        assert self._proc is None, "Server already started"
        self._log_path = log_path
        if log_path:
            self._log_handle = log_path.open("wb")
        self._proc = subprocess.Popen(
            [str(self.config.binary), str(self.config.data_root)],
            stdout=self._log_handle,
            stderr=subprocess.DEVNULL,
        )

    def wait_ready(self, max_attempts: int = 500) -> None:
        wait_for_url(
            self.config.spec_url,
            max_attempts,
            desc=f"waiting for {self.config.base_url}",
            dead_check=lambda: self._proc is not None and self._proc.poll() is None,
        )

    def stop(self) -> str:
        """Kill server, close log; return log text."""
        if self._proc:
            self._proc.kill()
            self._proc.wait()
            self._proc = None
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None
        if self._log_path and self._log_path.exists():
            return self._log_path.read_text()
        return ""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stop()


def build_server() -> None:
    subprocess.run(["cargo", "build", "--release"], check=True)


# ── Docker container servers ──────────────────────────────────────────────────

RUST_DOCKERFILE = "sql-yardstick/docker/Dockerfile.rust"
FLASK_DOCKERFILE = "sql-yardstick/docker/Dockerfile.pg-python"
TARGET_PORT = 3000

# containerd's overlayfs snapshotter intermittently corrupts its snapshot store
# and aborts the export step of an otherwise-successful build. Pruning the build
# cache clears it, so we detect that signature and retry once.
_SNAPSHOT_CORRUPTION = re.compile(
    r"parent snapshot .* does not exist|failed to prepare extraction snapshot"
)


@dataclass
class DockerServer:
    """A server running inside a Docker container, port-mapped to the host.

    Generic over the Rust server and the Flask/PG comparison backend: set
    ``target_port`` / ``extra_volumes`` / ``ready_accept_any`` to specialise.
    ``data_root`` is mounted read-only at ``/data/oa-root``; ``extra_volumes``
    are ``(host_path, container_path)`` pairs mounted read-only too.
    """

    container: str
    image: str
    host_port: int
    data_root: Path
    dockerfile: str = RUST_DOCKERFILE
    target_port: int = TARGET_PORT
    memory: str = "16g"
    cpus: str = "8"
    ready_accept_any: bool = False
    extra_volumes: list[tuple[Path, str]] = field(default_factory=list)
    ready_desc: Optional[str] = None

    @property
    def base_url(self) -> str:
        return _base_url(self.host_port)

    @property
    def spec_url(self) -> str:
        return f"{self.base_url}/v1/specs"

    def is_running(self) -> bool:
        return container_state(self.container)[0]

    def build_image(self) -> None:
        _docker_build(self.dockerfile, self.image)

    def stop(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.container], capture_output=True)

    def start(self) -> None:
        self.stop()
        volumes = ["-v", f"{self.data_root}:/data/oa-root:ro"]
        for host, dest in self.extra_volumes:
            volumes += ["-v", f"{host}:{dest}:ro"]
        _docker(
            [
                "run",
                "-d",
                "--name",
                self.container,
                "--memory",
                self.memory,
                "--cpus",
                self.cpus,
                "-p",
                f"{self.host_port}:{self.target_port}",
                *volumes,
                self.image,
            ]
        )

    def wait_ready(self, max_attempts: int = 300) -> None:
        ready_url = self.base_url if self.ready_accept_any else self.spec_url
        wait_for_url(
            ready_url,
            max_attempts,
            desc=self.ready_desc or f"waiting for {self.container}",
            dead_check=lambda: container_state(self.container)[0],
            on_fail=lambda: container_logs(self.container),
            accept_any=self.ready_accept_any,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stop()


@dataclass
class FlaskPgServer(DockerServer):
    """Flask/PostgreSQL comparison backend: mounts the ccl-science-data lib next
    to the data root, and is ready on any HTTP response (no health endpoint)."""

    ccl_lib: Optional[Path] = None
    dockerfile: str = FLASK_DOCKERFILE
    target_port: int = 5000
    memory: str = "8g"
    cpus: str = "4"
    ready_accept_any: bool = True

    def __post_init__(self) -> None:
        if self.ccl_lib is not None:
            self.extra_volumes = [
                *self.extra_volumes,
                (self.ccl_lib, "/ccl-science-data"),
            ]
        if self.ready_desc is None:
            self.ready_desc = (
                f"waiting for {self.container} (loading OA data into PostgreSQL)"
            )


def _docker(args: list) -> None:
    cmd = ["docker", *[str(a) for a in args]]
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _docker_build(dockerfile: str, image: str, context: str = ".") -> None:
    """Build an image, self-healing the containerd snapshot corruption that
    intermittently aborts the export of an otherwise-successful build: on that
    signature, prune the build cache once and retry."""
    cmd = ["docker", "build", "-f", str(dockerfile), "-t", image, context]
    print("$", " ".join(cmd))
    code, output = _stream(cmd)
    if code == 0:
        return
    if _SNAPSHOT_CORRUPTION.search(output):
        print("[docker] snapshot store corruption — pruning build cache and retrying")
        subprocess.run(["docker", "builder", "prune", "-af"], check=False)
        code, _ = _stream(cmd)
        if code == 0:
            return
        raise RuntimeError(
            f"docker build still failing after cache prune for {image}; "
            f"try `docker system prune -af` (or restart the docker daemon)"
        )
    raise RuntimeError(f"docker build failed for {image}")


def _stream(cmd: list) -> tuple[int, str]:
    """Run a command, echoing combined output live while capturing it."""
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    assert proc.stdout is not None
    captured = []
    for line in proc.stdout:
        print(line, end="")
        captured.append(line)
    proc.wait()
    return proc.returncode, "".join(captured)


def current_branch() -> str:
    return subprocess.check_output(["git", "branch", "--show-current"]).decode().strip()


def checkout(branch: str) -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    )
    uncommitted = [ln for ln in result.stdout.splitlines() if not ln.startswith("?")]
    if uncommitted:
        print("WARNING: uncommitted changes present — git checkout may fail:")
        for line in uncommitted:
            print(f"  {line}")
    subprocess.run(["git", "checkout", branch], check=True)


# ── git worktrees + per-ref builds (perf comparison) ──────────────────────────

PERF_ROOT = Path("/tmp/rankless-perf")


def resolve_ref(ref: str) -> str:
    """Full commit sha for any git ref (tag / branch / commit-ish)."""
    return subprocess.check_output(["git", "rev-parse", ref]).decode().strip()


def ensure_worktree(ref: str) -> tuple[str, Path]:
    """Check ``ref`` out detached into a per-sha worktree; reuse if present.

    The main working tree is never touched, so uncommitted changes are safe and
    ``ref`` may be any commit-ish, not just a local branch.
    """
    sha = resolve_ref(ref)
    path = PERF_ROOT / "worktrees" / sha
    if path.exists():
        return sha, path
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "worktree", "add", "--detach", str(path), sha], check=True)
    return sha, path


def remove_worktree(path: Path) -> None:
    subprocess.run(["git", "worktree", "remove", "--force", str(path)], check=False)


def build_server_at(worktree: Path) -> None:
    """Release-build the server binary inside a worktree (isolated ``target/``)."""
    subprocess.run(
        ["cargo", "build", "--release", "-p", "rankless-server"],
        cwd=worktree,
        check=True,
    )


def image_exists(image: str) -> bool:
    return (
        subprocess.run(
            ["docker", "image", "inspect", image], capture_output=True
        ).returncode
        == 0
    )


def build_perf_image(sha: str, worktree: Path) -> str:
    """Build (or reuse) the ``rankless-perf-<sha>`` image from a worktree's binary."""
    image = f"rankless-perf-{sha[:12]}"
    if image_exists(image):
        print(f"[perf] reusing image {image}")
        return image
    build_server_at(worktree)
    _docker_build(str(worktree / RUST_DOCKERFILE), image, context=str(worktree))
    return image


def cgroup_mem_bytes(container: str, kind: str) -> Optional[int]:
    """Container's cgroup v2 ``memory.<kind>`` (kind: current | peak) in bytes."""
    r = subprocess.run(
        ["docker", "exec", container, "cat", f"/sys/fs/cgroup/memory.{kind}"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    try:
        return int(r.stdout.strip())
    except ValueError:
        return None
