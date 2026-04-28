"""Export user ledger to $OA_ROOT/user_ledger/ for pipeline consumption.

Reads ledger_events and owner_pins from SQLite, writes:
  active.jsonl           — active events ready for the pipeline
  snapshot_manifest.json — run_id (ISO ts) + exported event_ids
  owner_pins.txt         — one ORCID per line

Counter-event collapse:
  revoke whose target is in the active non-revoke set → both dropped
  revoke whose target is NOT in that set → kept with target_inlined
    (Rust applies the inverse effect without touching SQLite)

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

from .deploy import OA_ROOT_VAR


DEFAULT_DATA_ROOT = os.environ.get(OA_ROOT_VAR)

if DEFAULT_DATA_ROOT is None:
    try:
        from ccl_science_data.common import oa_root as _DEFAULT_DATA_ROOT

        DEFAULT_DATA_ROOT = _DEFAULT_DATA_ROOT
    except ImportError:
        pass

DEFAULT_DB = "data/rankless.sqlite"
OK_MODERATION = ("auto_ok", "accepted")


def _fetch_active_events(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    placeholders = ",".join("?" * len(OK_MODERATION))
    rows = conn.execute(
        f"SELECT event_id, orcid, kind, payload, moderation, created_at "
        f"FROM ledger_events "
        f"WHERE revoked_at IS NULL AND moderation IN ({placeholders}) "
        f"ORDER BY event_id",
        OK_MODERATION,
    ).fetchall()
    return [
        {
            "event_id": r[0],
            "orcid": r[1],
            "kind": r[2],
            "payload": json.loads(r[3]),
            "moderation": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]


def _fetch_event_by_id(
    conn: sqlite3.Connection, event_id: int
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT event_id, kind, payload FROM ledger_events WHERE event_id = ?",
        (event_id,),
    ).fetchone()
    if row is None:
        return None
    return {"event_id": row[0], "kind": row[1], "payload": json.loads(row[2])}


def _fetch_owner_pins(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT orcid FROM owner_pins").fetchall()]


def _collapse_revokes(
    all_events: list[dict[str, Any]],
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    non_revoke = {e["event_id"]: e for e in all_events if e["kind"] != "revoke"}
    revoke_events = [e for e in all_events if e["kind"] == "revoke"]

    dropped_ids: set[int] = set()
    extra_revokes: list[dict[str, Any]] = []

    for rev in revoke_events:
        target_id: int = rev["payload"]["target_event_id"]
        if target_id in non_revoke:
            dropped_ids.add(target_id)
        else:
            target = _fetch_event_by_id(conn, target_id)
            if target is None:
                print(
                    f"  warn: revoke event {rev['event_id']} targets unknown event_id {target_id}; skipped",
                    file=sys.stderr,
                )
                continue
            extra_revokes.append({**rev, "target_inlined": target})

    result = [e for eid, e in non_revoke.items() if eid not in dropped_ids]
    result.extend(extra_revokes)
    result.sort(key=lambda e: e["event_id"])
    return result


def export(data_root: Path, db_path: str) -> None:
    out_dir = data_root / "user_ledger"
    out_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        all_events = _fetch_active_events(conn)
        active = _collapse_revokes(all_events, conn)
        pins = _fetch_owner_pins(conn)
    finally:
        conn.close()

    run_id = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    exported_ids = [e["event_id"] for e in active]

    with open(out_dir / "active.jsonl", "w") as f:
        for event in active:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")

    with open(out_dir / "snapshot_manifest.json", "w") as f:
        json.dump({"run_id": run_id, "event_ids": exported_ids}, f)

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
