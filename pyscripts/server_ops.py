"""Local Rust server lifecycle management."""

import os
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


# ── Docker container server ───────────────────────────────────────────────────

RUST_DOCKERFILE = "sql-yardstick/docker/Dockerfile.rust"
TARGET_PORT = 3000


@dataclass
class DockerServer:
    """Rust server running inside a Docker container, port-mapped to the host."""

    container: str
    image: str
    host_port: int
    data_root: Path
    dockerfile: str = RUST_DOCKERFILE
    memory: str = "16g"
    cpus: str = "8"

    @property
    def base_url(self) -> str:
        return _base_url(self.host_port)

    @property
    def spec_url(self) -> str:
        return f"{self.base_url}/v1/specs"

    def build_image(self) -> None:
        _docker(["build", "-f", self.dockerfile, "-t", self.image, "."])

    def stop(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.container], capture_output=True)

    def start(self) -> None:
        self.stop()
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
                f"{self.host_port}:{TARGET_PORT}",
                "-v",
                f"{self.data_root}:/data/oa-root:ro",
                self.image,
            ]
        )

    def wait_ready(self, max_attempts: int = 200) -> None:
        wait_for_url(
            self.spec_url,
            max_attempts,
            desc=f"waiting for {self.container}",
            dead_check=lambda: container_state(self.container)[0],
            on_fail=lambda: container_logs(self.container),
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stop()


def _docker(args: list) -> None:
    cmd = ["docker", *[str(a) for a in args]]
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


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
