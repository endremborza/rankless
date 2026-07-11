"""Scrub all report history and start fresh.

Run before promoting a new live instance: wipes the local `reports-v2/` archive,
aggregates, sites, run logs and state, and (unless ``--local-only``) force-pushes an
empty `gh-pages` branch so no previously published report survives in history. The
next hourly run rebuilds everything from the promoted box's log (alpha rows dropped).
"""

import argparse
import shutil
import sys
from pathlib import Path

from . import config, publish


def wipe_local() -> None:
    for d in (
        config.ARCHIVE_DIR,
        config.ARCHIVE_COLD_DIR,
        config.AGGREGATES_DIR,
        config.SITE_LOCAL_DIR,
        config.SITE_PUBLIC_DIR,
        config.RUN_LOGS_DIR,
    ):
        if d.exists():
            shutil.rmtree(d)
    for f in (config.STATE_PATH, config.SALTS_PATH):
        f.unlink(missing_ok=True)
    config.ensure_dirs()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pyscripts.reporting.reset")
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Only wipe local reports-v2 data; leave the published gh-pages site.",
    )
    parser.add_argument(
        "--yes", action="store_true", help="Skip the interactive confirmation."
    )
    args = parser.parse_args(argv)

    scope = (
        "local reports-v2 data"
        if args.local_only
        else "local reports-v2 data AND the entire gh-pages history (force-push)"
    )
    if not args.yes:
        resp = input(f"Permanently erase {scope}. Type 'scrub' to proceed: ")
        if resp.strip() != "scrub":
            print("aborted", file=sys.stderr)
            return 1

    wipe_local()
    print("local report history wiped")
    if not args.local_only:
        publish.reset_ghpages_history(Path("."))
        print("gh-pages history reset to a single empty commit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
