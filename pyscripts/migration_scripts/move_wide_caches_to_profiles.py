"""Move every tree's `wide-<pid>.zst` first-level cut to the level-keyed profile path the
server reads and writes: `<cache>/<root>/<eid>/first/<entity>-<side>/<pid>.zst`. Trees that
open with the same level always held the same profile, so the first file wins and later
duplicates are deleted. Stdlib-only and idempotent: a second run finds nothing to move.

    python3 -m pyscripts.migration_scripts.move_wide_caches_to_profiles [--root OA_ROOT] [--specs URL]

The tid -> level table comes from the running backend's `/v1/specs`; the data root from
`--root`, `$OA_ROOT`, or the `OA_ROOT=` line of `.env` in the working directory.
"""

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

DEFAULT_SPECS_URL = "http://127.0.0.1:3038/v1/specs"


def data_root(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    if env := os.environ.get("OA_ROOT"):
        return Path(env)
    dotenv = Path(".env")
    if dotenv.exists():
        for line in dotenv.read_text().splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "OA_ROOT" and value.strip():
                return Path(value.strip())
    sys.exit("no data root: pass --root or set OA_ROOT")


def level_of(breakdown: dict) -> str:
    side = "refed" if breakdown["sourceSide"] else "citing"
    return f"{breakdown['attributeType']}-{side}"


def levels_by_tid(specs_url: str) -> dict[str, list[str]]:
    with urllib.request.urlopen(specs_url, timeout=30) as resp:
        specs = json.load(resp)["specs"]
    return {
        root: [level_of(spec["breakdowns"][0]) for spec in root_specs]
        for root, root_specs in specs.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root")
    parser.add_argument("--specs", default=DEFAULT_SPECS_URL)
    args = parser.parse_args()
    cache = data_root(args.root) / "cache"
    moved = dropped = 0
    for root, levels in levels_by_tid(args.specs).items():
        root_dir = cache / root
        if not root_dir.is_dir():
            continue
        for eid_dir in (d for d in root_dir.iterdir() if d.is_dir()):
            for tid, level in enumerate(levels):
                for src in (eid_dir / str(tid)).glob("wide-*.zst"):
                    dst = eid_dir / "first" / level / src.name.removeprefix("wide-")
                    if dst.exists():
                        src.unlink()
                        dropped += 1
                    else:
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        src.rename(dst)
                        moved += 1
    print(f"{cache}: moved {moved} profiles, dropped {dropped} duplicates")


if __name__ == "__main__":
    main()
