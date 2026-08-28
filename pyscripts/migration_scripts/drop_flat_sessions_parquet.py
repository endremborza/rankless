"""Removes the pre-partition flat `aggregates/sessions/data.parquet` left by the
reporting store before sessions were partitioned by start date.

    REPORTS_V2_ROOT=... python3 -m pyscripts.migration_scripts.drop_flat_sessions_parquet
"""

import argparse
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--root", default="reports-v2", help="reports root (REPORTS_V2_ROOT)"
    )
    flat = (
        Path(ap.parse_args().root).resolve()
        / "aggregates"
        / "sessions"
        / "data.parquet"
    )
    if not flat.exists():
        print(f"no {flat}")
        return
    flat.unlink()
    print(f"removed {flat}")


if __name__ == "__main__":
    main()
