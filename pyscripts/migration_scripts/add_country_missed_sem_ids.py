"""Adds `country_game_results.missed_sem_ids` on a box whose table was created
before the country game logged its misses.

    python3 -m pyscripts.migration_scripts.add_country_missed_sem_ids
"""

import argparse

from . import columns, user_db

TABLE = "country_game_results"
COLUMN = "missed_sem_ids"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db", help="user DB (default: RANKLESS_DB_PATH or data/rankless.sqlite)"
    )
    con = user_db(ap.parse_args().db)
    try:
        cols = columns(con, TABLE)
        if not cols:
            print(f"no {TABLE} table — the app creates it with {COLUMN}")
        elif COLUMN in cols:
            print(f"{TABLE}.{COLUMN} already present")
        else:
            with con:
                con.execute(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} TEXT")
            print(f"added {TABLE}.{COLUMN}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
