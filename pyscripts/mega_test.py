"""End-to-end ledger integration test.

Flow
────
1. [--full-rebuild] make nuke && make -B complete && make restart-service
2. Start SvelteKit dev server (bun run dev) and wait for it to be ready.
3. Playwright pre-pipeline: login, disown a paper, merge two papers, verify pending.
4. make -B filter   (re-exports ledger → clean-filters → filter binary)
5. make -B rankless_rs/src/gen/derive_links5.rs  (full pipeline rebuild)
6. make restart-service && wait for backend.
7. Playwright post-pipeline: verify applied events + author page reflects changes.

Usage
─────
    uv run -m pyscripts.mega_test
"""

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from .deploy import be_service_name
from .server_ops import DEFAULT_BE_ADDR

DEV_PORT = 5173
BASE_URL = f"http://localhost:{DEV_PORT}"
BE_URL = f"{DEFAULT_BE_ADDR}/v1"
REPO_ROOT = Path(__file__).parent.parent
LOG_DIR = REPO_ROOT / "logs"
DEV_SERVER_LOG = LOG_DIR / "dev-server.log"


def _run(
    cmd: str | list[str], *, check: bool = True, **kw
) -> subprocess.CompletedProcess:
    if isinstance(cmd, str):
        cmd = cmd.split()
    print(f"\n>>> {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, check=check, cwd=REPO_ROOT, **kw)


def _tail(path: Path, n: int = 40) -> str:
    try:
        lines = path.read_text(errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception as e:
        return f"(could not read {path}: {e})"


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_http(
    url: str,
    timeout: int = 120,
    interval: float = 2.0,
    dead_check: "None | (() -> bool)" = None,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3):
                return True
        except Exception:
            pass
        if dead_check is not None and not dead_check():
            return False
        time.sleep(interval)
    return False


def _start_dev_server() -> subprocess.Popen:
    if _port_in_use(DEV_PORT):
        sys.exit(
            f"Port {DEV_PORT} already in use before starting dev server. "
            "Kill the existing process and retry."
        )

    LOG_DIR.mkdir(exist_ok=True)
    log_fh = DEV_SERVER_LOG.open("wb")
    env = {**os.environ, "NODE_ENV": "development"}
    proc = subprocess.Popen(
        ["bun", "run", "dev", "--port", str(DEV_PORT)],
        cwd=REPO_ROOT,
        env=env,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
    )
    print(
        f"Dev server PID {proc.pid} started (log: {DEV_SERVER_LOG}), "
        f"waiting for {BASE_URL} …",
        flush=True,
    )

    def alive() -> bool:
        return proc.poll() is None

    ready = _wait_http(BASE_URL, dead_check=alive)

    log_fh.flush()
    log_fh.close()

    if not ready:
        rc = proc.poll()
        proc.kill()
        tail = _tail(DEV_SERVER_LOG)
        if rc is not None:
            sys.exit(
                f"Dev server (PID {proc.pid}) exited early with code {rc}.\n"
                f"--- last lines of {DEV_SERVER_LOG} ---\n{tail}"
            )
        sys.exit(
            f"Dev server did not come up within 120 s at {BASE_URL}.\n"
            f"--- last lines of {DEV_SERVER_LOG} ---\n{tail}"
        )

    print("Dev server ready.", flush=True)
    return proc


def _wait_backend(timeout: int = 120) -> None:
    url = f"{BE_URL}/health"
    print(f"Waiting for backend at {url} …", flush=True)
    if not _wait_http(url, timeout=timeout):
        alt = f"{BE_URL}/paper-profile/robert-langer"
        print(f"  /health timed out, trying {alt} …", flush=True)
        if not _wait_http(alt, timeout=30):
            try:
                log = subprocess.check_output(
                    ["journalctl", "--user", "-n", "50", "-u", be_service_name],
                    text=True,
                )
            except Exception:
                log = "(could not read journalctl)"
            sys.exit(
                f"Backend did not come up in time after restart.\n"
                f"--- journalctl (last 50 lines) ---\n{log}"
            )
    print("Backend ready.", flush=True)


def _run_playwright(grep: str, *, env: dict[str, str] | None = None) -> int:
    cmd = [
        "npx",
        "playwright",
        "test",
        "--config",
        "playwright.ledger.config.ts",
        "--grep",
        grep,
        "--reporter",
        "line",
    ]
    e = {**os.environ, "BASE_URL": BASE_URL, "BE_URL": BE_URL}
    if env:
        e.update(env)
    print(f"\n>>> playwright {grep}", flush=True)
    result = subprocess.run(cmd, cwd=REPO_ROOT, env=e)
    return result.returncode


def _run_pipeline() -> None:
    _run(["make", "-B", "post-csvs"])
    _run(["make", "restart-service"])
    _wait_backend()


def main() -> None:
    start_time = time.monotonic()
    _run(["make", "nuke"])
    _run(["make", "-B", "complete"])
    _run(["make", "restart-service"])
    _wait_backend()

    dev_server = _start_dev_server()
    try:
        rc = _run_playwright("pre-pipeline")
        assert rc == 0, f"\n[FAIL] pre-pipeline tests exited {rc}"

        _run_pipeline()

        rc = _run_playwright("post-pipeline")
        assert rc == 0, f"\n[FAIL] post-pipeline tests exited {rc}"

        print("\n[OK] mega-test passed.", flush=True)

    finally:
        elapsed = time.monotonic() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        time_str = f"{seconds}s"
        if minutes > 0:
            time_str = f"{minutes}m {time_str}"
        print(f"\nTotal time: {time_str}", flush=True)

        dev_server.send_signal(signal.SIGTERM)
        try:
            dev_server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            dev_server.kill()


if __name__ == "__main__":
    main()
