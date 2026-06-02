"""Shared helpers for the dev-setup scripts.

Stdlib-only on purpose: bootstrap imports this before `uv sync` has run.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_PORT = 3038
FRONTEND_PORT = 5173


def header(msg: str) -> None:
    bar = "─" * max(8, min(60, len(msg) + 2))
    print(f"\n{bar}\n {msg}\n{bar}", flush=True)


def info(msg: str) -> None:
    print(f"  · {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"  ! {msg}", file=sys.stderr, flush=True)


def die(msg: str, code: int = 1) -> NoReturn:
    print(f"\nerror: {msg}", file=sys.stderr, flush=True)
    sys.exit(code)


def run(
    cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> None:
    """Run a command, streaming stdout/stderr; raise on non-zero exit."""
    pretty = " ".join(cmd)
    where = f" (in {cwd})" if cwd else ""
    info(f"$ {pretty}{where}")
    result = subprocess.run(cmd, cwd=cwd, env=env)
    if result.returncode != 0:
        die(f"command failed (exit {result.returncode}): {pretty}")


def read_env_file(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser; ignores blanks and `#`-comments, strips quotes."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        out[key] = value
    return out


def env_with_dotenv() -> dict[str, str]:
    """`os.environ` overlaid on `.env` (if present). Caller's environ wins."""
    merged = dict(read_env_file(REPO_ROOT / ".env"))
    merged.update(os.environ)
    return merged


def resolve_path(value: str) -> Path:
    """Resolve a path that may be relative to the repo root."""
    p = Path(value).expanduser()
    return p if p.is_absolute() else (REPO_ROOT / p).resolve()
