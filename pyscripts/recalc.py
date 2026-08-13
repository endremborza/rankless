"""Data recalculation stages, run in order (see docs/deploy.md).

Shipping the recalculated data (`ship_alpha`, `promote`) lives in
pyscripts/deploy.py — those deploy the application; these rebuild its data.

Stages are idempotent — rerunning resumes/verifies rather than redoing work.
`refresh-data` and `warm-caches` take the pipeline lock: /tmp/dmove-parts is
shared, two data pipelines on one box corrupt each other.
"""

import json
import os
import re
import subprocess
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from protocli import Dispatcher

from pyscripts import fleet, gitutil
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
        # After the stamp: the manifest records it (and releases/ is
        # digest-excluded, so writing it keeps the stamp valid).
        write_release_manifest(Path(root))
        _make("lib_data_generation", "restart-service", "homepage_showcase")
    print("refresh-data done — next: `make commit-artifacts`")


def commit_artifacts(*, cwd: Path = Path(".")) -> None:
    """Commit + push exactly the generated files (gen/, assets/data)."""
    branch = gitutil.current_branch(cwd)
    staged = gitutil.git_lines(cwd, "diff", "--cached", "--name-only")
    if staged:
        raise SystemExit(
            f"index already has {len(staged)} staged file(s) — the artifact "
            "commit must contain only generated files; commit or unstage first"
        )
    if not gitutil.git_lines(cwd, "status", "--porcelain", "--", *ARTIFACT_PATHS):
        print("no artifact changes to commit")
        return
    gitutil.git(cwd, "fetch", "origin", branch)
    behind = gitutil.git_out(cwd, "rev-list", "--count", f"HEAD..origin/{branch}")
    if behind != "0":
        raise SystemExit(f"{behind} commit(s) behind origin/{branch} — pull first")
    gitutil.git(cwd, "add", "--", *ARTIFACT_PATHS)
    run_id = manifest.run_id(os.environ.get("OA_ROOT"))
    gitutil.git(cwd, "commit", "-m", f"data artifacts: {run_id}")
    gitutil.git(cwd, "push", "origin", branch)


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


def build_release_manifest(root: Path) -> dict:
    """Aggregate the sidecars a refresh-data run leaves behind (per-source
    detail and event keys stay in the internal manifests)."""
    ul = root / "user-ledger"
    snap = json.loads((ul / "snapshot_manifest.json").read_text())
    applied = json.loads((ul / "applied_manifest.json").read_text())
    stamp = (root / manifest.STAMP_NAME).read_text().strip()

    run_id = snap["run_id"]
    for label, other in (("applied_manifest", applied["run_id"]), ("stamp", stamp)):
        if not other.startswith(run_id):
            raise SystemExit(
                f"release manifest: {label} run_id {other!r} != snapshot {run_id!r} "
                "— torn state, rerun refresh-data"
            )

    snapshot_name = Path(os.environ["OA_SNAPSHOT"]).name
    date_m = re.search(r"\d{4}-\d{2}(-\d{2})?", snapshot_name)

    return {
        "run_id": run_id,
        "stamp": stamp,
        "git_commit": gitutil.head_commit(),
        "rankless_env": manifest.rankless_env(),
        "snapshot": {"name": snapshot_name, "date": date_m[0] if date_m else None},
        "ledger": snap.get("sources", {}),
        "filter_counts": _filter_counts(root / "filter-steps"),
        "applied": dict(Counter(k.split("|")[1] for k in applied["applied_keys"])),
        "skipped": dict(Counter(s["reason"] for s in applied["skipped"])),
    }


def write_release_manifest(root: Path | None = None) -> Path:
    """Assemble $OA_ROOT/releases/<run_id>.json (+ latest copy at release.json)."""
    root = root or Path(os.environ["OA_ROOT"])
    built = build_release_manifest(root)
    rdir = root / "releases"
    rdir.mkdir(exist_ok=True)
    text = json.dumps(built, indent=1)
    out = rdir / f"{built['run_id']}.json"
    out.write_text(text)
    (rdir / "release.json").write_text(text)
    print(f"release manifest: {out}")
    return out


def documented_release(version: str, *, warn_missing: bool = False) -> dict | None:
    """releases/release.json, asserted to document the served version
    (warn_missing: warn-only while the root predates release manifests)."""
    path = Path(os.environ["OA_ROOT"]) / "releases" / "release.json"
    if warn_missing and not path.exists():
        print(
            "WARNING — no release manifest for this root; "
            "run `uv run -m pyscripts recalc manifest`"
        )
        return None
    built = json.loads(path.read_text())
    run_id = built["run_id"]
    if not version.rsplit("|", 1)[-1].startswith(run_id):
        raise SystemExit(
            f"served version {version!r} is not the documented release "
            f"{run_id!r} ({path})"
        )
    print(f"serving documented release {run_id}")
    return built


def _filter_counts(steps_dir: Path) -> dict:
    """Entity type → (in, kept) per filter step, from the id files (8-byte
    ids, so kept = size/8; `in` = the previous step's kept, None at first)."""
    counts: dict[str, dict] = {}
    last_kept: dict[str, int] = {}
    if not steps_dir.is_dir():
        raise SystemExit(f"release manifest: {steps_dir} missing — run `make filter`")
    for step in sorted(steps_dir.iterdir(), key=lambda p: int(p.name)):
        counts[step.name] = {}
        for f in sorted(step.iterdir()):
            kept = f.stat().st_size // 8
            counts[step.name][f.name] = {"in": last_kept.get(f.name), "kept": kept}
            last_kept[f.name] = kept
    return counts


_dispatcher = Dispatcher(
    "pyscripts recalc",
    {
        "refresh-data": refresh_data,
        "commit-artifacts": commit_artifacts,
        "warm-caches": warm_caches,
        "manifest": write_release_manifest,
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
    dirty = gitutil.git_lines(cwd, "status", "--porcelain", "--", *ARTIFACT_PATHS)
    if dirty:
        raise SystemExit(
            f"{len(dirty)} uncommitted artifact file(s) — run commit-artifacts "
            "first, the box clones from origin"
        )
    gitutil.assert_pushed(cwd)


def _make(*goals: str) -> None:
    print(f"$ make {' '.join(goals)}", flush=True)
    subprocess.run(["make", *goals], check=True)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
