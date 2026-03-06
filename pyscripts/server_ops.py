"""Local Rust server lifecycle management."""

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import requests
from tqdm import tqdm

DEFAULT_BINARY = Path("target/release/rankless-server")
DEFAULT_PORT = 3038


@dataclass
class ServerConfig:
    data_root: Path
    binary: Path = field(default_factory=lambda: DEFAULT_BINARY)
    port: int = DEFAULT_PORT

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

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
        for _ in tqdm(range(max_attempts), desc="waiting for server"):
            try:
                r = requests.get(self.config.spec_url, timeout=5)
                if r.ok:
                    return
            except Exception:
                pass
            assert self._proc and self._proc.poll() is None, "Server process died"
            time.sleep(3)
        raise TimeoutError(
            f"Server at {self.config.base_url} not ready after {max_attempts * 3}s"
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
        return f"http://127.0.0.1:{self.host_port}"

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

    def wait_ready(self, max_attempts: int = 500) -> None:
        for _ in tqdm(range(max_attempts), desc=f"waiting for {self.container}"):
            try:
                r = requests.get(self.spec_url, timeout=5)
                if r.ok:
                    return
            except Exception:
                pass
            time.sleep(3)
        raise TimeoutError(
            f"Container {self.container} not ready after {max_attempts * 3}s"
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
    uncommitted = [l for l in result.stdout.splitlines() if not l.startswith("?")]
    if uncommitted:
        print("WARNING: uncommitted changes present — git checkout may fail:")
        for line in uncommitted:
            print(f"  {line}")
    subprocess.run(["git", "checkout", branch], check=True)
