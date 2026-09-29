"""External data sources the pipeline reads but does not produce.

Everything from outside OpenAlex lives under one root, `$EXTERNAL_DATA_ROOT`, in a
directory per source, outside the repo, the snapshot and `$OA_ROOT` so it is never
published and a snapshot update or `make nuke` never purges it; unset, the root is the
repo's `data/external` (a dev box). A table the pipeline reads is required once the
variable names the root and optional under the default, the rule
`rankless_rs/src/derived_ledger.rs` applies to the same root. A download a box can
fetch again from its URL sits in its source's `raw/`. The root syncs with
`$EXTERNAL_DATA_REMOTE` (`host:/path`): `make external-push|external-pull`,
additive, never deleting on the far side, and never carrying a `raw/`: each box
fetches its own downloads. Stdlib-only.
"""

import argparse
import os
import subprocess
from pathlib import Path

ROOT_VAR = "EXTERNAL_DATA_ROOT"
REMOTE_VAR = "EXTERNAL_DATA_REMOTE"
DEFAULT_ROOT = "data/external"
RAW = "raw"


def root(override: Path | None = None) -> Path:
    if override is not None:
        return override
    return Path(os.environ.get(ROOT_VAR) or DEFAULT_ROOT)


def source_dir(source: str, override: Path | None = None) -> Path:
    d = root(override) / source
    d.mkdir(parents=True, exist_ok=True)
    return d


def raw_dir(source: str, override: Path | None = None) -> Path:
    d = source_dir(source, override) / RAW
    d.mkdir(exist_ok=True)
    return d


def table(source: str, name: str) -> Path | None:
    """The source's table, or None when it is missing under the default root."""
    path = root() / source / name
    if path.exists():
        return path
    if os.environ.get(ROOT_VAR):
        raise FileNotFoundError(f"{path} is missing under ${ROOT_VAR}")
    return None


def fetched(source: str, name: str, url: str, override: Path | None = None) -> Path:
    """The local copy of `url` in the source's `raw/`, downloaded once; an interrupted
    download resumes from its `.part`."""
    path = raw_dir(source, override) / name
    if not path.exists():
        part = path.with_suffix(path.suffix + ".part")
        subprocess.run(
            ["curl", "-fsSL", "--retry", "20", "--retry-all-errors"]
            + ["-C", "-", "-o", str(part), url],
            check=True,
        )
        part.rename(path)
    return path


def sync(direction: str, remote: str) -> None:
    local, far = f"{root()}/", f"{remote.rstrip('/')}/"
    src, dst = (local, far) if direction == "push" else (far, local)
    subprocess.run(
        ["rsync", "-a", "--itemize-changes", f"--exclude=/*/{RAW}/", src, dst],
        check=True,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Sync the external data root.")
    p.add_argument("direction", choices=("push", "pull"))
    p.add_argument("--remote", default=os.environ.get(REMOTE_VAR), help="host:/path")
    args = p.parse_args()
    if not os.environ.get(ROOT_VAR):
        raise SystemExit(f"${ROOT_VAR} is unset: only a named root syncs")
    if not args.remote:
        raise SystemExit(f"set ${REMOTE_VAR} (host:/path) or pass --remote")
    sync(args.direction, args.remote)


if __name__ == "__main__":
    main()
