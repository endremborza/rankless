"""Pinned-cohort baseline: per-owner aggregates as currently served.

Retroactive, like recalc's filter_counts: run while the release is being
served, before the next recalc overwrites $OA_ROOT. Writes
`releases/<run_id>.cohort.json` next to the release record — the
release-over-release baseline for the works-through-filters attribution
feature. Per-user data: releases/ is push- and digest-excluded, so the file
never leaves the box.

Point `COHORT_BE` at a remote backend serving the same release when the local
one is down.
"""

import json
import os
import urllib.request
from pathlib import Path

BASE = os.environ.get("COHORT_BE", "http://127.0.0.1:3038/v1").rstrip("/")
AUTHOR_KEYS = ("semanticId", "name", "oaId", "papers", "citations")


def main() -> None:
    """Snapshot each pinned owner's served works/citations next to the
    release record ($OA_ROOT/releases/<run_id>.cohort.json)."""
    from pyscripts.recalc import documented_release

    root = Path(os.environ["OA_ROOT"])
    with urllib.request.urlopen(f"{BASE}/specs", timeout=60) as r:
        version = json.load(r)["version"]
    record = documented_release(version)
    assert record is not None

    pins_file = root / "user-ledger" / "owner_pins.txt"
    pins = [line for line in pins_file.read_text().splitlines() if line.strip()]
    authors = {orcid: _served_author(orcid) for orcid in pins}

    out = root / "releases" / f"{record['run_id']}.cohort.json"
    out.write_text(
        json.dumps({"run_id": record["run_id"], "authors": authors}, indent=1)
    )
    resolved = sum(1 for a in authors.values() if a is not None)
    print(f"cohort baseline: {out} ({resolved}/{len(pins)} pins resolved)")


def _served_author(orcid: str) -> dict | None:
    with urllib.request.urlopen(f"{BASE}/orcid/{orcid}", timeout=60) as r:
        res = json.load(r)
    return None if res is None else {k: res[k] for k in AUTHOR_KEYS}
