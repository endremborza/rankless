"""Data recalculation stages, run in order (see docs/deploy.md).

Shipping the recalculated data (`ship_alpha`, `promote`) lives in
pyscripts/deploy.py — those deploy the application; these rebuild its data.

Stages are idempotent — rerunning resumes/verifies rather than redoing work.
`refresh-data` and `warm-caches` take the pipeline lock: /tmp/dmove-parts is
shared, two data pipelines on one box corrupt each other.
"""

import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from protocli import Dispatcher

from pyscripts import fleet
from pyscripts.fleet import manifest

load_dotenv()
ARTIFACT_PATHS = ("rankless_rs/src/gen", "src/lib/assets/data")
LADDER_TOP = "rankless_rs/src/gen/derive_links5.rs"
LOCK_PATH = Path("/tmp/rankless-pipeline.lock")


@contextmanager
def pipeline_lock():
    if LOCK_PATH.exists():
        pid = int(LOCK_PATH.read_text().strip() or 0)
        if pid and _alive(pid):
            raise SystemExit(
                f"pipeline lock held by pid {pid} ({LOCK_PATH}) — "
                "/tmp/dmove-parts is shared, never run two pipelines at once"
            )
        print(f"stealing stale pipeline lock (pid {pid} is gone)")
        LOCK_PATH.unlink()
    fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode())
    os.close(fd)
    try:
        yield
    finally:
        LOCK_PATH.unlink(missing_ok=True)


def refresh_data(*, from_snapshot: bool = False, no_db_pull: bool = False) -> None:
    """Pull user DB from live, rebuild the data + backend + showcase
    (--from-snapshot runs to-csv first; --no-db-pull skips AWS)."""
    with pipeline_lock():
        if not no_db_pull:
            _pull_db()
        if from_snapshot:
            _make("to-csv")
        _make("filter", "extend_csvs")
        # The gen ladder's make deps only see steps/*.rs — it cannot know the
        # data changed under it, and after `filter` it always has. Force it,
        # and only it (this replaces the old blanket `make -B post-csvs`).
        _make("-B", LADDER_TOP)
        # Stamp before restart-service: the backend reads the stamp at startup
        # and echoes it in /v1/specs — the warm fleet's version handshake.
        root = os.environ["OA_ROOT"]
        print(f"stamped {root}: {manifest.write_stamp(root, manifest.run_id(root))}")
        _make("lib_data_generation", "restart-service", "homepage_showcase")
    print("refresh-data done — next: `make commit-artifacts`")


def commit_artifacts(*, cwd: Path = Path(".")) -> None:
    """Commit + push exactly the generated files (gen/, assets/data)."""
    branch = _git_out(cwd, "branch", "--show-current")
    staged = _git_lines(cwd, "diff", "--cached", "--name-only")
    if staged:
        raise SystemExit(
            f"index already has {len(staged)} staged file(s) — the artifact "
            "commit must contain only generated files; commit or unstage first"
        )
    if not _git_lines(cwd, "status", "--porcelain", "--", *ARTIFACT_PATHS):
        print("no artifact changes to commit")
        return
    _git(cwd, "fetch", "origin", branch)
    behind = _git_out(cwd, "rev-list", "--count", f"HEAD..origin/{branch}")
    if behind != "0":
        raise SystemExit(f"{behind} commit(s) behind origin/{branch} — pull first")
    _git(cwd, "add", "--", *ARTIFACT_PATHS)
    run_id = manifest.run_id(os.environ.get("OA_ROOT"))
    _git(cwd, "commit", "-m", f"data artifacts: {run_id}")
    _git(cwd, "push", "origin", branch)


def warm_caches(
    *,
    config: str = fleet.DEFAULT_CONFIG,
    only: str | None = None,
    no_push: bool = False,
    gate_only: bool = False,
) -> None:
    """Drive the data/warm.toml fleet (machine-local, gitignored config)."""
    if gate_only:
        cfg = fleet.load_config(config, require_bands=False)
        fleet.coverage_gate(os.environ["OA_ROOT"], cfg.min_citations)
        return
    with pipeline_lock():
        fleet.warm(config, only=only, push=not no_push)


_dispatcher = Dispatcher(
    "pyscripts recalc",
    {
        "refresh-data": refresh_data,
        "commit-artifacts": commit_artifacts,
        "warm-caches": warm_caches,
    },
)


def _pull_db() -> None:
    from pyscripts import deploy

    try:
        deploy.merge_db_from_live()
    except Exception as e:
        raise SystemExit(
            f"pulling the user DB from live failed ({e}) — the ledger export "
            "would miss recent claims; pass --no-db-pull to build without it"
        )


def assert_released() -> None:
    """Everything commit-artifacts owns is committed + pushed (used by ship_alpha)."""
    cwd = Path(".")
    dirty = _git_lines(cwd, "status", "--porcelain", "--", *ARTIFACT_PATHS)
    if dirty:
        raise SystemExit(
            f"{len(dirty)} uncommitted artifact file(s) — run commit-artifacts "
            "first, the box clones from origin"
        )
    branch = _git_out(cwd, "branch", "--show-current")
    _git(cwd, "fetch", "origin", branch)
    if _git_out(cwd, "rev-parse", "HEAD") != _git_out(
        cwd, "rev-parse", f"origin/{branch}"
    ):
        raise SystemExit(f"HEAD != origin/{branch} — push (or pull) first")


def _make(*goals: str) -> None:
    print(f"$ make {' '.join(goals)}", flush=True)
    subprocess.run(["make", *goals], check=True)


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True)


def _git_out(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _git_lines(cwd: Path, *args: str) -> list[str]:
    return [line for line in _git_out(cwd, *args).splitlines() if line.strip()]


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
