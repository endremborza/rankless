"""Off-box backups of the user DB + its artifact stores.

One run snapshots the source's `data/rankless.sqlite` (SQLite online backup —
safe against a live WAL writer) into a dated zstd file and additively mirrors
its artifact dirs (`data/mcp-sessions/`, `data/mcp-objects/`), landing
everything under `<dest>/<source>/`. The box being backed up keeps nothing:
the snapshot exists there only as a transient temp file. Bundles are
immutable, so the single growing mirror serves every DB snapshot — restoring
day N is that day's DB plus the mirror.

Retention on the dated DB snapshots: the last --keep-days daily ones, plus
every 1st-of-the-month one permanently.

    uv run -m pyscripts backup --source live            # pull from the live box
    uv run -m pyscripts backup --source local           # this checkout's data/

`pyscripts/services.py --backup-source live` installs the daily systemd timer
(deploy/rankless-backup.{service,timer}) on the machine that should hold the
backups (an always-on box that is not the one being backed up).
"""

import re
import subprocess
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import zstandard

from pyscripts import mcp_db, paths

ZSTD_LEVEL = 19
BKP_TMP = f"{paths.DATA_DIR}/_bkxfer"
SNAP_RE = re.compile(r"rankless-(\d{8})\.sqlite\.zst")


def main(
    *, source: str = "live", dest: str = "data/backups", keep_days: int = 7
) -> None:
    """Back up a source's user DB + artifact dirs into <dest>/<source>/
    (--source local|live|alpha; live/alpha resolve the running box via deploy).
    Prunes dated DB snapshots to --keep-days, keeping 1st-of-month ones forever."""
    root = Path(dest) / source
    db_dir = root / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    out = db_dir / f"rankless-{datetime.now(UTC).strftime('%Y%m%d')}.sqlite.zst"
    if source == "local":
        _backup_local(root, out)
    else:
        _backup_box(source, root, out)
    removed = prune(db_dir, keep_days)
    kept = len(list(db_dir.glob("rankless-*.sqlite.zst")))
    print(
        f"[backup] {out.name} ({out.stat().st_size // 1024} KiB) -> {root}; "
        f"{kept} snapshot(s) kept, {len(removed)} pruned"
    )


def prune(db_dir: Path, keep_days: int) -> list[str]:
    """Delete dated snapshots older than keep_days, except 1st-of-month ones."""
    cutoff = datetime.now(UTC).date() - timedelta(days=keep_days)
    removed = []
    for f in sorted(db_dir.iterdir()):
        m = SNAP_RE.fullmatch(f.name)
        if m is None:
            continue
        day = datetime.strptime(m.group(1), "%Y%m%d").date()
        if day.day == 1 or day >= cutoff:
            continue
        f.unlink()
        removed.append(f.name)
    if removed:
        print(f"[backup] pruned {', '.join(removed)}")
    return removed


def _backup_local(root: Path, out: Path) -> None:
    if not Path(paths.DB_REL).exists():
        raise SystemExit(f"no {paths.DB_REL} in this checkout")
    with tempfile.TemporaryDirectory() as td:
        snap = Path(td) / "rankless.sqlite"
        mcp_db.snapshot(paths.DB_REL, str(snap))
        _compress(snap, out)
    for rel in paths.MCP_ARTIFACT_RELS:
        if Path(rel).exists():
            subprocess.run(["rsync", "-ra", rel, f"{root}/"], check=True)


def _backup_box(source: str, root: Path, out: Path) -> None:
    # Lazy import: --source local must work on machines without the cloud
    # dependencies deploy.py pulls in (boto3 etc.).
    from pyscripts import deploy

    if source not in ("live", "alpha"):
        raise SystemExit("--source must be local, live, or alpha")
    tpr = deploy.get_running_tpr(live=source == "live")
    remote_db = f"{tpr.deploy_dir}/{paths.DB_REL}"
    if not tpr.ssh.remote_exists(remote_db):
        raise SystemExit(f"no DB at {remote_db} on the {source} box")
    remote_tmp = f"{tpr.deploy_dir}/{BKP_TMP}"
    tpr.ssh.run(f"rm -rf {remote_tmp} && mkdir -p {remote_tmp}")
    tpr._run_mcp_db(f"snapshot {paths.DB_REL} {BKP_TMP}/rankless.sqlite")
    with tempfile.TemporaryDirectory() as td:
        tpr.ssh.rsync_from(f"{remote_tmp}/rankless.sqlite", td)
        tpr.ssh.run(f"rm -rf {remote_tmp}")
        _compress(Path(td) / "rankless.sqlite", out)
    for rel in paths.MCP_ARTIFACT_RELS:
        remote_dir = f"{tpr.deploy_dir}/{rel}"
        if tpr.ssh.remote_exists(remote_dir):
            tpr.ssh.rsync_from(remote_dir, str(root))


def _compress(src: Path, out: Path) -> None:
    out.write_bytes(zstandard.compress(src.read_bytes(), ZSTD_LEVEL))
