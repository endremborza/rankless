"""One-time migration: rewrite legacy `revoke` ledger payloads to reference their
target by merge-stable logical key instead of the renumberable target_event_id.

    old:  {"kind":"revoke","target_event_id":<id>, "reason"?:...}
    new:  {"kind":"revoke","target_key":"<orcid>|<kind>|<subject_hash>", "reason"?:...}

Each revoke's subject_hash column is recomputed too (subjectHash now keys on target_key).
Run once on the box whose DB still has the original event_ids (the live/source DB), before
the first export under the new pipeline.

    uv run -m pyscripts.migrate_revoke_targets [--db PATH]
"""

import argparse
import hashlib
import json
import sqlite3

from pyscripts import paths


def _revoke_subject_hash(target_key: str) -> str:
    # Mirror of subjectHash({kind:'revoke', ...}) in src/lib/server/ledger-hash.ts.
    return hashlib.sha1(f"target:{target_key}".encode()).hexdigest()


def migrate(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        rows = conn.execute(
            "SELECT event_id, payload FROM ledger_events WHERE kind = 'revoke'"
        ).fetchall()
        migrated = skipped = 0
        for event_id, payload_json in rows:
            payload = json.loads(payload_json)
            if "target_key" in payload:  # already migrated
                skipped += 1
                continue
            target = conn.execute(
                "SELECT orcid, kind, subject_hash FROM ledger_events WHERE event_id = ?",
                (payload.get("target_event_id"),),
            ).fetchone()
            if target is None:
                print(f"  warn: revoke {event_id} targets unknown event; left as-is")
                skipped += 1
                continue
            target_key = f"{target[0]}|{target[1]}|{target[2]}"
            new_payload: dict[str, str] = {"kind": "revoke", "target_key": target_key}
            if payload.get("reason"):
                new_payload["reason"] = payload["reason"]
            conn.execute(
                "UPDATE ledger_events SET payload = ?, subject_hash = ? WHERE event_id = ?",
                (
                    json.dumps(new_payload, separators=(",", ":")),
                    _revoke_subject_hash(target_key),
                    event_id,
                ),
            )
            migrated += 1
        conn.commit()
        print(f"migrated {migrated} revoke event(s); {skipped} already-new/unresolved")
    finally:
        conn.close()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=paths.DB_REL, help="SQLite DB path")
    args = p.parse_args()
    migrate(args.db)


if __name__ == "__main__":
    main()
