"""Drops the `mcp_sessions` table and the `mcp-sessions/` dir beside the user DB:
agent runs live under `$EXTERNAL_DATA_ROOT/runs/`, never on a serving box.

    python3 -m pyscripts.migration_scripts.drop_mcp_sessions [--db PATH]
"""

import argparse
import shutil
from pathlib import Path

from . import user_db

TABLE = "mcp_sessions"
DIR = "mcp-sessions"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db", help="user DB (default: RANKLESS_DB_PATH or data/rankless.sqlite)"
    )
    db = ap.parse_args().db
    con = user_db(db)
    try:
        with con:
            con.execute(f"DROP TABLE IF EXISTS {TABLE}")
        db_file = con.execute("PRAGMA database_list").fetchone()[2]
    finally:
        con.close()
    print(f"{TABLE} dropped (or already gone)")
    sessions = Path(db_file).parent / DIR
    if sessions.exists():
        shutil.rmtree(sessions)
        print(f"removed {sessions}")


if __name__ == "__main__":
    main()
