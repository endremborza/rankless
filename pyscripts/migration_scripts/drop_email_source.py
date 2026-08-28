"""Drops `email_consents.email_source`, a column every row of which is 'manual'
since consent stopped having more than one source.

    python3 -m pyscripts.migration_scripts.drop_email_source
"""

import argparse

from . import columns, user_db

TABLE = "email_consents"
COLUMN = "email_source"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db", help="user DB (default: RANKLESS_DB_PATH or data/rankless.sqlite)"
    )
    con = user_db(ap.parse_args().db)
    try:
        if COLUMN not in columns(con, TABLE):
            print(f"{TABLE}.{COLUMN} already gone")
            return
        others = {
            r[0] for r in con.execute(f"SELECT DISTINCT {COLUMN} FROM {TABLE}")
        } - {"manual"}
        if others:
            raise SystemExit(
                f"refusing to drop: {TABLE}.{COLUMN} also holds {sorted(others)}"
            )
        with con:
            con.execute(f"ALTER TABLE {TABLE} DROP COLUMN {COLUMN}")
        print(f"dropped {TABLE}.{COLUMN}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
