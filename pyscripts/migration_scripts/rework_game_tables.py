"""Brings a box's user DB to the geography quiz's run table: `country_game_results`
becomes `geo_game_runs`, scores count half-points, `lifelined_sem_ids` joins the
row, and the retired clue game's `game_results` + `game_daily` are dropped.

    python3 -m pyscripts.migration_scripts.rework_game_tables
"""

import argparse

from . import columns, user_db

OLD_TABLE = "country_game_results"
TABLE = "geo_game_runs"
COLUMN = "lifelined_sem_ids"
DROPPED = ("game_results", "game_daily")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--db", help="user DB (default: RANKLESS_DB_PATH or data/rankless.sqlite)"
    )
    con = user_db(ap.parse_args().db)
    try:
        tables = {
            r[0]
            for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        with con:
            if OLD_TABLE in tables and TABLE not in tables:
                con.execute(f"ALTER TABLE {OLD_TABLE} RENAME TO {TABLE}")
                con.execute("DROP INDEX IF EXISTS idx_cgr_day")
                print(f"renamed {OLD_TABLE} to {TABLE}")
            cols = columns(con, TABLE)
            if not cols:
                print(f"no {TABLE} table — the app creates it with {COLUMN}")
            elif COLUMN not in cols:
                # rows without the column scored whole cards; the new unit is halves
                con.execute(f"ALTER TABLE {TABLE} ADD COLUMN {COLUMN} TEXT")
                con.execute(f"UPDATE {TABLE} SET score = score * 2")
                print(f"added {TABLE}.{COLUMN}, scores doubled into half-points")
            for name in DROPPED:
                if name in tables:
                    con.execute(f"DROP TABLE {name}")
                    print(f"dropped {name}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
