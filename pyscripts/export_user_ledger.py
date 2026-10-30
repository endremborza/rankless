"""Export user ledger to $OA_ROOT/`USER_LEDGER_DIR`/ for pipeline consumption.

Reads ledger_events and owner_pins from SQLite, writes:
  ACTIVE_JSONL       — active events ready for the pipeline
  CURATED_JSONL      — the team's curated ledger: the occasion files in
                       $EXTERNAL_KEPT_ROOT/ledger/`CURATED_DIR`/, joined in name order;
                       absent when the default root has none
  SNAPSHOT_MANIFEST  — run_id (ISO ts) + exported event_ids + per-source counts + the
                       lines each curated occasion file gave
  OWNER_PINS         — one ORCID per line: the site's logged-in owners, then the curated
                       ledger's own `OWNER_PINS` (people the team pins without a login)

Every event carries a `source` (this exporter always writes "site" — the site
SQLite DB is the "site" source). Future feeds (institutions, OA-API deltas)
arrive as parallel files with their own snapshot manifests and source tags;
they never enter the site DB.

Every event carries its merge-stable logical `key` (`orcid|kind|subject_hash`); the
pipeline and admin reference events by that, never by the renumberable event_id.

Counter-event collapse (revokes are resolved here; the pipeline never sees them):
  revoke whose target is in the active non-revoke set → both dropped (the undo takes effect)
  revoke whose target is NOT in that set → dropped (target isn't applied, nothing to undo)

Usage:
    uv run -m pyscripts.export_user_ledger [--db PATH]
"""

import argparse
import os
import datetime
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from pyscripts import paths
from pyscripts.external_data import KEPT
from pyscripts.ledger_ids import OK_MODERATION, OK_MODERATION_SQL, logical_key
from wire.rankless_rs.user_ledger import (
    ACTIVE_JSONL,
    CURATED_JSONL,
    OWNER_PINS,
    SNAPSHOT_MANIFEST,
)

from .deploy import OA_ROOT_VAR


DEFAULT_DATA_ROOT = os.environ.get(OA_ROOT_VAR)

if DEFAULT_DATA_ROOT is None:
    try:
        from ccl_science_data.common import oa_root as _DEFAULT_DATA_ROOT

        DEFAULT_DATA_ROOT = _DEFAULT_DATA_ROOT
    except ImportError:
        pass

DEFAULT_DB = paths.DB_REL
SOURCE = "site"
CURATED_SOURCE = "curated"
# Under the external root's `ledger/`: one JSONL per curation occasion.
CURATED_DIR = "curated"


def _fetch_active_events(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            f"SELECT event_id, orcid, kind, payload, subject_hash, moderation, created_at "
            f"FROM ledger_events "
            f"WHERE revoked_at IS NULL AND {OK_MODERATION_SQL} "
            f"ORDER BY event_id",
            OK_MODERATION,
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [
        {
            "event_id": r[0],
            "key": logical_key(r[1], r[2], r[4]),
            "orcid": r[1],
            "kind": r[2],
            "source": SOURCE,
            "payload": json.loads(r[3]),
            "moderation": r[5],
            "created_at": r[6],
        }
        for r in rows
    ]


def _fetch_owner_pins(conn: sqlite3.Connection) -> list[str]:
    try:
        return [r[0] for r in conn.execute("SELECT orcid FROM owner_pins").fetchall()]
    except sqlite3.OperationalError:
        return []


def _collapse_revokes(all_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Non-revoke events are unique by logical key (the DB's dedup identity). A revoke
    # names its target by that key; if the target is active, both are removed (the undo
    # takes effect). Revokes never flow to the pipeline — a target that isn't active
    # isn't applied either, so there is nothing left to reverse.
    non_revoke = {e["key"]: e for e in all_events if e["kind"] != "revoke"}
    reverted_keys = {
        e["payload"]["target_key"]
        for e in all_events
        if e["kind"] == "revoke" and e["payload"]["target_key"] in non_revoke
    }
    result = [e for k, e in non_revoke.items() if k not in reverted_keys]
    result.sort(key=lambda e: e["event_id"])
    return result


def export(data_root: Path, db_path: str) -> None:
    out_dir = data_root / paths.USER_LEDGER_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        all_events = _fetch_active_events(conn)
        active = _collapse_revokes(all_events)
        site_pins = _fetch_owner_pins(conn)
    finally:
        conn.close()
    curated_pins = _curated_pins()
    pins = list(dict.fromkeys(site_pins + curated_pins))

    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    exported_ids = [e["event_id"] for e in active]

    with open(out_dir / ACTIVE_JSONL, "w") as f:
        for event in active:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")

    sources = {SOURCE: len(active)}
    curated = _export_curated(out_dir)
    if curated is not None:
        sources[CURATED_SOURCE] = sum(curated.values())

    with open(out_dir / SNAPSHOT_MANIFEST, "w") as f:
        json.dump(
            {
                "run_id": run_id,
                "event_ids": exported_ids,
                "sources": sources,
                "curated_files": curated or {},
            },
            f,
        )

    with open(out_dir / OWNER_PINS, "w") as f:
        f.write("\n".join(pins))
        if pins:
            f.write("\n")

    print(
        f"exported {sources} event(s), {len(pins)} owner pin(s) "
        f"({len(curated_pins)} curated) → {out_dir}"
    )
    print(f"run_id: {run_id}")


def _export_curated(out_dir: Path) -> dict[str, int] | None:
    """The curated occasion files joined in name order beside the site's events, by file
    the lines each gave; None, and no stale copy left, when the default root holds none.
    An event key on two lines stops the export, since the pipeline would apply the event
    in whichever file sorts last."""
    dest = out_dir / CURATED_JSONL
    src = KEPT.table("ledger", CURATED_DIR)
    if src is None:
        dest.unlink(missing_ok=True)
        return None
    counts: dict[str, int] = {}
    lines: list[str] = []
    owners: dict[str, list[str]] = {}
    for path in sorted(src.glob("*.jsonl")):
        own = [line for line in path.read_text().splitlines() if line.strip()]
        counts[path.name] = len(own)
        lines += own
        for line in own:
            owners.setdefault(json.loads(line)["key"], []).append(path.name)
    repeated = {k: files for k, files in owners.items() if len(files) > 1}
    if repeated:
        raise SystemExit(f"{src}: event keys on more than one line: {repeated}")
    dest.write_text("".join(line + "\n" for line in lines))
    return counts


def _curated_pins() -> list[str]:
    """The ORCIDs the team pins without a login: the curated ledger's `OWNER_PINS`, one per
    line."""
    src = KEPT.table("ledger", CURATED_DIR)
    if src is None or not (src / OWNER_PINS).exists():
        return []
    return [
        line.strip()
        for line in (src / OWNER_PINS).read_text().splitlines()
        if line.strip()
    ]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=DEFAULT_DB, help="SQLite DB path")
    args = p.parse_args()

    if DEFAULT_DATA_ROOT is not None:
        data_root = Path(DEFAULT_DATA_ROOT)
    else:
        sys.exit(f"{OA_ROOT_VAR} env required (ccl_science_data not available)")

    export(data_root, args.db)


if __name__ == "__main__":
    main()
