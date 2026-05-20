"""Foreground launcher: rankless-server + SvelteKit dev server in one process.

Streams both children's stdout through `[be]` / `[fe]` prefixes. Ctrl-C
forwards SIGTERM (then SIGKILL after a grace period) to both children.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import IO

from pyscripts.server_ops import ServerConfig, ServerProcess, wait_for_url

from ._common import (
    BACKEND_PORT,
    FRONTEND_PORT,
    REPO_ROOT,
    die,
    env_with_dotenv,
    header,
    info,
    resolve_path,
    warn,
)


BINARY = REPO_ROOT / "target" / "release" / "rankless-server"
BACKEND_WAIT_ATTEMPTS = 60  # × 3s = 3 min, matches wait_for_url's cadence
SHUTDOWN_GRACE_S = 6


def _stream_with_prefix(stream: IO[bytes], prefix: str) -> None:
    for raw in iter(stream.readline, b""):
        try:
            line = raw.decode("utf-8", errors="replace").rstrip()
        except Exception:
            continue
        print(f"{prefix} {line}", flush=True)


def _spawn(
    cmd: list[str], *, cwd: Path, env: dict[str, str]
) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
    )


class _Children:
    def __init__(self) -> None:
        self.procs: list[tuple[str, subprocess.Popen[bytes]]] = []
        self._shutting_down = False

    def add(self, label: str, proc: subprocess.Popen[bytes]) -> None:
        self.procs.append((label, proc))

    def alive(self) -> list[tuple[str, subprocess.Popen[bytes]]]:
        return [(label, p) for label, p in self.procs if p.poll() is None]

    def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        info("shutting down…")
        for label, p in self.procs:
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
        deadline = time.time() + SHUTDOWN_GRACE_S
        while time.time() < deadline and self.alive():
            time.sleep(0.2)
        for label, p in self.alive():
            warn(f"force-killing {label}")
            p.kill()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--open", action="store_true", help="open the FE in your browser when ready"
    )
    args = parser.parse_args(argv)

    header("rankless dev")
    env = env_with_dotenv()
    if "OA_ROOT" not in env:
        die("OA_ROOT not set — run `make bootstrap` first")
    oa_root = resolve_path(env["OA_ROOT"])
    if not oa_root.exists():
        die(f"OA_ROOT does not exist: {oa_root} — run `make bootstrap`")
    if not BINARY.exists():
        die(f"missing backend binary {BINARY} — run `make bootstrap`")

    spawn_env = {**os.environ, **{k: v for k, v in env.items() if isinstance(v, str)}}
    spawn_env["OA_ROOT"] = str(oa_root)

    server_cfg = ServerConfig(data_root=oa_root, binary=BINARY, port=BACKEND_PORT)
    try:
        ServerProcess(server_cfg).assert_port_free()
    except RuntimeError as e:
        die(str(e))

    children = _Children()

    def _handle_signal(signum: int, _frame: object) -> None:
        info(f"received signal {signum}")
        children.shutdown()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    info(f"backend  → {server_cfg.base_url}  ({oa_root})")
    backend = _spawn([str(BINARY), str(oa_root)], cwd=REPO_ROOT, env=spawn_env)
    children.add("be", backend)
    assert backend.stdout is not None
    threading.Thread(
        target=_stream_with_prefix, args=(backend.stdout, "[be]"), daemon=True
    ).start()

    try:
        wait_for_url(
            server_cfg.spec_url,
            max_attempts=BACKEND_WAIT_ATTEMPTS,
            desc="backend warmup",
            dead_check=lambda: backend.poll() is None,
        )
    except (RuntimeError, TimeoutError) as e:
        warn(str(e))
        children.shutdown()
        sys.exit(1)
    info("backend ready")

    info(f"frontend → http://127.0.0.1:{FRONTEND_PORT}")
    frontend = _spawn(
        ["bun", "run", "dev", "--port", str(FRONTEND_PORT)],
        cwd=REPO_ROOT,
        env=spawn_env,
    )
    children.add("fe", frontend)
    assert frontend.stdout is not None
    threading.Thread(
        target=_stream_with_prefix, args=(frontend.stdout, "[fe]"), daemon=True
    ).start()

    if args.open:
        time.sleep(2)
        webbrowser.open(f"http://127.0.0.1:{FRONTEND_PORT}")

    print(f"\nready → http://127.0.0.1:{FRONTEND_PORT}  (Ctrl-C to stop)\n", flush=True)

    while children.alive():
        time.sleep(0.5)
        if any(p.poll() is not None for _, p in children.procs):
            break

    for label, p in children.procs:
        rc = p.poll()
        if rc is not None and rc != 0 and not children._shutting_down:
            warn(f"{label} exited with code {rc}")

    children.shutdown()
    bad = [
        rc
        for _, p in children.procs
        for rc in [p.poll()]
        if rc not in (0, None, -signal.SIGTERM)
    ]
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
