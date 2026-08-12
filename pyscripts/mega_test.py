"""End-to-end ledger integration test, riding the real release path.

Flow
────
1. make nuke, then the refresh-data release stage with --from-snapshot
   --no-db-pull (nuke removed $OA_ROOT and the sqlite DB): to-csv → filter →
   scoped ladder force → stamp → lib data → restart backend → showcase.
2. Wait for the backend, start the SvelteKit dev server (bun run dev).
3. Playwright pre-pipeline: login, disown a paper, merge two papers, verify pending.
4. refresh-data --no-db-pull (re-exports ledger → filter → forced ladder →
   stamp → restart), wait for backend.
5. Playwright post-pipeline: verify applied events + author page reflects changes.

Records the outcome (timestamp, result, duration) to docs/mega-test-last-run.md
on every run, pass or fail.

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
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .deploy import be_service_name
from .server_ops import DEFAULT_BE_ADDR

DEV_PORT = 5173
BASE_URL = f"http://localhost:{DEV_PORT}"
BE_URL = f"{DEFAULT_BE_ADDR}/v1"
REPO_ROOT = Path(__file__).parent.parent
LOG_DIR = REPO_ROOT / "logs"
DEV_SERVER_LOG = LOG_DIR / "dev-server.log"
RUN_RECORD = REPO_ROOT / "docs" / "mega-test-last-run.md"


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
    dead_check: "Callable[[], bool] | None" = None,
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


def _wait_backend(timeout: int = 180) -> None:
    # The backend has no /health route; /tops is a cheap always-present endpoint
    # that only answers once the server has finished loading its data.
    url = f"{BE_URL}/tops"
    print(f"Waiting for backend at {url} …", flush=True)
    if not _wait_http(url, timeout=timeout):
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


def _refresh_data(*flags: str) -> None:
    _run(["uv", "run", "-m", "pyscripts", "release", "refresh-data", *flags])


def _fmt_duration(elapsed: float) -> str:
    minutes, seconds = divmod(int(elapsed), 60)
    return f"{minutes}m {seconds}s" if minutes else f"{seconds}s"


def _write_run_record(outcome: str, detail: str, elapsed: float) -> None:
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    RUN_RECORD.write_text(
        "# Mega-test — last run\n\n"
        f"- **When:** {stamp}\n"
        f"- **Result:** {outcome}\n"
        f"- **Duration:** {_fmt_duration(elapsed)}\n"
        f"- **Detail:** {detail}\n"
    )
    print(f"Run record written to {RUN_RECORD}", flush=True)


def main() -> None:
    start_time = time.monotonic()
    outcome, detail = "FAILED", "did not complete"
    dev_server: "subprocess.Popen | None" = None
    try:
        _run(["make", "nuke"])
        _refresh_data("--from-snapshot", "--no-db-pull")
        _wait_backend()

        dev_server = _start_dev_server()

        rc = _run_playwright("pre-pipeline")
        if rc != 0:
            detail = f"pre-pipeline playwright exited {rc}"
            raise SystemExit(f"\n[FAIL] {detail}")

        _refresh_data("--no-db-pull")
        _wait_backend()

        rc = _run_playwright("post-pipeline")
        if rc != 0:
            detail = f"post-pipeline playwright exited {rc}"
            raise SystemExit(f"\n[FAIL] {detail}")

        outcome = "PASSED"
        detail = "pre-pipeline, pipeline rebuild, and post-pipeline all green"
        print("\n[OK] mega-test passed.", flush=True)
    except BaseException as e:
        if detail == "did not complete":
            detail = f"{type(e).__name__}: {e}".strip()
        raise
    finally:
        elapsed = time.monotonic() - start_time
        if dev_server is not None:
            dev_server.send_signal(signal.SIGTERM)
            try:
                dev_server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                dev_server.kill()
        _write_run_record(outcome, detail, elapsed)
        print(f"\nTotal time: {_fmt_duration(elapsed)}", flush=True)


if __name__ == "__main__":
    main()
