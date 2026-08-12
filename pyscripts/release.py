"""Release flow stages (`uv run -m pyscripts deploy <stage>`, see docs/deploy.md).

    refresh-data      pull user DB from live, rebuild the data + backend + showcase
                      (--from-snapshot to run to-csv first; --no-db-pull to skip AWS)
    commit-artifacts  commit + push exactly the generated files (gen/, assets/data)
    warm-caches       drive the data/warm.toml fleet (--config/--only/--no-push/--gate-only)
    ship-alpha        fresh large alpha box + smoke checks (branch must be pushed)
    promote           flip alpha to live + smoke checks

Stages are idempotent — rerunning resumes/verifies rather than redoing work.
`refresh-data` and `warm-caches` take the pipeline lock: /tmp/dmove-parts is
shared, two data pipelines on one box corrupt each other.
"""

import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv

from pyscripts import fleet
from pyscripts.fleet import manifest

load_dotenv()

STAGES = ("refresh-data", "commit-artifacts", "warm-caches", "ship-alpha", "promote")
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


def refresh_data(args) -> None:
    with pipeline_lock():
        if not args.no_db_pull:
            _pull_db()
        if args.from_snapshot:
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


def commit_artifacts(cwd: Path = Path(".")) -> None:
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


def warm_caches(args) -> None:
    if args.gate_only:
        cfg = fleet.load_config(args.config, require_bands=False)
        fleet.coverage_gate(os.environ["OA_ROOT"], cfg.min_citations)
        return
    with pipeline_lock():
        fleet.warm(args.config, only=args.only, push=not args.no_push)


def ship_alpha(args) -> None:
    _assert_released()
    from pyscripts import deploy

    deploy.new_large_alpha()
    smoke(live=False)
    print("alpha up — validate by hand, then `make promote`")


def promote(args) -> None:
    from pyscripts import deploy

    deploy.promote_alpha_to_live()
    smoke(live=True)
    print(
        "promoted — the old live box keeps running (DB safety net); "
        "once satisfied, run `make kill_dangling`"
    )


def smoke(live: bool) -> None:
    """FE + BE reachable and serving real data; per-FE-worker memory sane."""
    from pyscripts import deploy

    fe = deploy.LIVE_DOMAIN if live else deploy.ALPHA_DOMAIN
    be = deploy.LIVE_BACKEND if live else deploy.ALPHA_BACKEND
    _check_ok(f"https://{fe}/", "frontend root")
    specs = _check_json(f"https://{be}/v1/specs", "specs")["specs"]
    rt = next(iter(specs))
    rows = _check_json(f"https://{be}/v1/slice/{rt}/0/2", f"slice {rt}")
    sid = quote_plus(rows[0]["semanticId"])
    tree = _check_json(
        f"https://{be}/v1/trees/{rt}/{sid}?tid=0&year=1950", f"tree {rt}/{sid}"
    )
    if not tree:
        raise SystemExit("smoke: tree response empty")
    print(deploy.get_running_tpr(live).get_fe_memory_df().to_string())
    print(f"smoke checks passed for {fe}")


def add_arguments(parser) -> None:
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument(
        "--from-snapshot",
        action="store_true",
        help="refresh-data: run to-csv first (a new OpenAlex snapshot landed)",
    )
    parser.add_argument(
        "--no-db-pull",
        action="store_true",
        help="refresh-data: skip pulling the user DB from live (no AWS access)",
    )
    parser.add_argument(
        "--config",
        default=fleet.DEFAULT_CONFIG,
        help="warm-caches fleet (machine-local, gitignored)",
    )
    parser.add_argument("--only", help="warm-caches: run a single worker by name")
    parser.add_argument(
        "--no-push", action="store_true", help="warm-caches: skip the data push"
    )
    parser.add_argument(
        "--gate-only",
        action="store_true",
        help="warm-caches: only run the disk coverage gate",
    )


def run(args) -> None:
    dispatch = {
        "refresh-data": refresh_data,
        "commit-artifacts": lambda _: commit_artifacts(),
        "warm-caches": warm_caches,
        "ship-alpha": ship_alpha,
        "promote": promote,
    }
    assert set(dispatch) == set(STAGES)
    dispatch[args.stage](args)


def _pull_db() -> None:
    from pyscripts import deploy

    try:
        deploy.merge_db_from_live()
    except Exception as e:
        raise SystemExit(
            f"pulling the user DB from live failed ({e}) — the ledger export "
            "would miss recent claims; pass --no-db-pull to build without it"
        )


def _assert_released() -> None:
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


def _check_ok(url: str, desc: str) -> requests.Response:
    r = requests.get(url, timeout=300)
    if not r.ok:
        raise SystemExit(f"smoke: {desc} → {r.status_code} ({url})")
    print(f"smoke: {desc} ok")
    return r


def _check_json(url: str, desc: str):
    return _check_ok(url, desc).json()


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
