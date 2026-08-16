"""Export user ledger to $OA_ROOT/user-ledger/ for pipeline consumption.

Reads ledger_events and owner_pins from SQLite, writes:
  user-ledger/active.jsonl           — active events ready for the pipeline
  user-ledger/snapshot_manifest.json — run_id (ISO ts) + exported event_ids + per-source counts
  user-ledger/owner_pins.txt         — one ORCID per line

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
from pyscripts.ledger_ids import logical_key

from .deploy import OA_ROOT_VAR


DEFAULT_DATA_ROOT = os.environ.get(OA_ROOT_VAR)

if DEFAULT_DATA_ROOT is None:
    try:
        from ccl_science_data.common import oa_root as _DEFAULT_DATA_ROOT

        DEFAULT_DATA_ROOT = _DEFAULT_DATA_ROOT
    except ImportError:
        pass

DEFAULT_DB = paths.DB_REL
OK_MODERATION = ("auto_ok", "accepted")
SOURCE = "site"


def _fetch_active_events(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    try:
        placeholders = ",".join("?" * len(OK_MODERATION))
        rows = conn.execute(
            f"SELECT event_id, orcid, kind, payload, subject_hash, moderation, created_at "
            f"FROM ledger_events "
            f"WHERE revoked_at IS NULL AND moderation IN ({placeholders}) "
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
    out_dir = data_root / "user-ledger"
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        all_events = _fetch_active_events(conn)
        active = _collapse_revokes(all_events)
        pins = _fetch_owner_pins(conn)
    finally:
        conn.close()

    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    exported_ids = [e["event_id"] for e in active]

    with open(out_dir / "active.jsonl", "w") as f:
        for event in active:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")

    with open(out_dir / "snapshot_manifest.json", "w") as f:
        json.dump(
            {
                "run_id": run_id,
                "event_ids": exported_ids,
                "sources": {SOURCE: len(active)},
            },
            f,
        )

    with open(out_dir / "owner_pins.txt", "w") as f:
        f.write("\n".join(pins))
        if pins:
            f.write("\n")

    print(f"exported {len(active)} event(s), {len(pins)} owner pin(s) → {out_dir}")
    print(f"run_id: {run_id}")


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
