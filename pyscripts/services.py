"""Unified service setup from the deploy/ unit templates.

    uv run -m pyscripts.services --profile dev [--mcp-backend alpha]  # make setup-services

One template system for every machine: `deploy/*.service` holds the unit
shape with `{{ var }}` placeholders, this module renders them with real values
(actual repo root, data root, MCP backend URL, ...) and installs them into
`~/.config/systemd/user` on the current machine. `pyscripts/deploy.py` renders
the same templates for cloud instances over SSH.

Profiles = which services a box runs:
- dev:         backend + mcp-server + mcp-worker
- small-alpha: frontend (blue+green) + mcp-server + mcp-worker
- live:        frontend + backend + mcp-server + mcp-worker

The MCP server's backend is a parameter (`--mcp-backend local|alpha|live|<url>`),
defaulting per profile; re-run with a different value to re-point it.
"""

import argparse
import os
import re
import subprocess
from pathlib import Path

from dotenv import load_dotenv

from pyscripts import paths

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "deploy"

BACKEND_UNIT = "rankless-backend.service"
MCP_SERVER_UNIT = "rankless-mcp-server.service"
MCP_WORKER_UNIT = "rankless-mcp-worker.service"
FE_UNIT_FRAME = "rankless-frontend-{}@.service"
FE_BUILD_NAMES = ["blue", "green"]

MCP_PORT = 8100
MCP_BACKENDS = {
    "local": "http://127.0.0.1:3038/v1",
    "alpha": "https://alpha-api.rankless.org/v1",
    "live": "https://api.rankless.org/v1",
}
DEFAULT_WORKER_MODEL = "claude-sonnet-5"
DEFAULT_WORKER_RUNNER = "claude-cli"

PROFILES = {
    "dev": ("backend", "mcp-server", "mcp-worker"),
    "small-alpha": ("frontend", "mcp-server", "mcp-worker"),
    "live": ("frontend", "backend", "mcp-server", "mcp-worker"),
}
# Where the MCP server points by default: a dev box mines real data from the
# alpha API; a small alpha (no local backend) uses the live API; a full box
# uses its own backend.
DEFAULT_MCP_BACKEND = {"dev": "alpha", "small-alpha": "live", "live": "local"}

# Per-FE-process memory backstop (cgroup v2). A healthy SvelteKit SSR bun worker
# sits ~150-300 MB, so this only bites a runaway/leak. Hard wall ONLY — no
# MemoryHigh: on a swapless box a leaky (anon-heavy) worker pinned at a soft cap
# cannot be reclaimed, so the kernel throttles it into a permanent stall that
# radiates PSI into user@ (the 2026-07-10 outage trigger). MemoryMax +
# OOMPolicy=kill + Restart=always turn the same state into a seconds-long
# self-healing blip contained to one cgroup. TimeoutStopSec=5 for the same
# reason: a wedged worker can't run a graceful shutdown, and SSR is stateless.
FE_MEMORY_MAX = "1280M"
# Proactively recycle each FE worker on a jittered, per-instance schedule so a
# slow uniform leak never lets the whole pool reach MemoryMax together.
# RuntimeRandomizedExtraSec redraws an independent random extra per cycle, so
# restarts scatter in time. SSR is stateless and nginx retries other upstreams.
FE_RUNTIME_MAX = "6h"
FE_RUNTIME_JITTER = "3h"
# Same hard-wall logic for the backend (~41 GB fresh working set on full data):
# die and reload in minutes instead of dragging the box into reclaim thrash.
# Percentage of physical RAM so the same template fits every box size.
BE_MEMORY_MAX = "85%"

_VAR_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render(template: str, **values: object) -> str:
    text = (TEMPLATE_DIR / template).read_text()

    def sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"{template}: no value for {{{{ {key} }}}}")
        return str(values[key])

    return _VAR_RE.sub(sub, text)


def resolve_mcp_backend(arg: str) -> str:
    if arg in MCP_BACKENDS:
        return MCP_BACKENDS[arg]
    if arg.startswith("http"):
        return arg.rstrip("/")
    raise SystemExit(f"--mcp-backend must be one of {list(MCP_BACKENDS)} or a URL.")


def render_backend(repo_root: str, data_root: str) -> str:
    return render(
        BACKEND_UNIT,
        repo_root=repo_root,
        data_root=data_root,
        memory_max=BE_MEMORY_MAX,
    )


def render_frontend(
    repo_root: str, domain: str, suffix: str, build_dir: str, bun: str
) -> str:
    return render(
        "rankless-frontend@.service",
        repo_root=repo_root,
        domain=domain,
        suffix=suffix,
        build_dir=build_dir,
        bun=bun,
        memory_max=FE_MEMORY_MAX,
        runtime_max=FE_RUNTIME_MAX,
        runtime_jitter=FE_RUNTIME_JITTER,
    )


def render_mcp_server(
    repo_root: str, python: str, be_url: str, port: int = MCP_PORT
) -> str:
    return render(
        MCP_SERVER_UNIT,
        repo_root=repo_root,
        python=python,
        mcp_be_url=be_url,
        mcp_port=port,
    )


def render_mcp_worker(
    repo_root: str,
    python: str,
    model: str = DEFAULT_WORKER_MODEL,
    runner: str = DEFAULT_WORKER_RUNNER,
) -> str:
    return render(
        MCP_WORKER_UNIT,
        repo_root=repo_root,
        python=python,
        db_path=f"{repo_root}/{paths.DB_REL}",
        sessions_root=f"{repo_root}/{paths.MCP_SESSIONS_REL}",
        worker_model=model,
        worker_runner=runner,
    )


def render_nginx_mcp(port: int = MCP_PORT) -> str:
    return render("nginx-mcp-location.conf", mcp_port=port)


def main() -> int:
    load_dotenv()
    args = _build_parser().parse_args()
    units = _render_units(args)
    if args.print:
        for name, text in units.items():
            print(f"### {name}\n{text}")
        return 0
    _install(units, start=not args.no_start)
    if MCP_SERVER_UNIT in units:
        print(
            "\nTo expose the MCP endpoint publicly, add this to the backend "
            f"nginx server block:\n{render_nginx_mcp(args.mcp_port)}"
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Set up rankless systemd --user services.")
    p.add_argument("--profile", required=True, choices=list(PROFILES))
    p.add_argument(
        "--mcp-backend",
        default=None,
        help=f"backend for the MCP server: {list(MCP_BACKENDS)} or a /v1 URL "
        f"(default per profile: {DEFAULT_MCP_BACKEND}).",
    )
    p.add_argument("--mcp-port", type=int, default=MCP_PORT)
    p.add_argument("--worker-model", default=DEFAULT_WORKER_MODEL)
    p.add_argument(
        "--worker-runner",
        default=DEFAULT_WORKER_RUNNER,
        help="mining engine for the worker (see pyscripts/explore/runner.py).",
    )
    p.add_argument(
        "--domain", default=None, help="frontend ORIGIN domain (fe profiles)."
    )
    p.add_argument(
        "--print", action="store_true", help="print rendered units, install nothing."
    )
    p.add_argument(
        "--no-start", action="store_true", help="install + enable, do not (re)start."
    )
    return p


def _render_units(args: argparse.Namespace) -> dict[str, str]:
    repo = str(REPO_ROOT)
    python = f"{repo}/.venv/bin/python"
    wanted = PROFILES[args.profile]
    be_url = resolve_mcp_backend(args.mcp_backend or DEFAULT_MCP_BACKEND[args.profile])

    units: dict[str, str] = {}
    if "backend" in wanted:
        data_root = os.environ.get("OA_ROOT")
        if not data_root:
            raise SystemExit("backend service needs OA_ROOT (env or .env).")
        units[BACKEND_UNIT] = render_backend(repo, data_root)
    if "frontend" in wanted:
        if not args.domain:
            raise SystemExit("frontend services need --domain.")
        bun = str(Path.home() / ".bun" / "bin" / "bun")
        for suffix in FE_BUILD_NAMES:
            units[FE_UNIT_FRAME.format(suffix)] = render_frontend(
                repo, args.domain, suffix, f"built-{suffix}", bun
            )
    if "mcp-server" in wanted:
        units[MCP_SERVER_UNIT] = render_mcp_server(repo, python, be_url, args.mcp_port)
    if "mcp-worker" in wanted:
        units[MCP_WORKER_UNIT] = render_mcp_worker(
            repo, python, args.worker_model, args.worker_runner
        )
    return units


def _install(units: dict[str, str], start: bool) -> None:
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    for name, text in units.items():
        (unit_dir / name).write_text(text)
        print(f"[services] wrote {unit_dir / name}")
    _systemctl("daemon-reload")
    for name in units:
        # Template units (fe blue/green) are enabled per instance by the
        # blue/green deploy flow (deploy.py), not here.
        if "@" in name:
            continue
        _systemctl("enable", name)
        if start:
            _systemctl("restart", name)
            print(f"[services] restarted {name}")


def _systemctl(*args: str) -> None:
    subprocess.run(["systemctl", "--user", *args], check=True)


if __name__ == "__main__":
    raise SystemExit(main())
