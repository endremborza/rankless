"""External data sources the pipeline reads but does not produce.

Everything fetched from outside OpenAlex lives under one root, `$EXTERNAL_DATA_ROOT`,
in a directory per source, outside the snapshot and `$OA_ROOT` trees so a snapshot
update or `make nuke` never purges it; unset, the root is the repo's `data/external`
(a dev box). `rankless_rs/src/derived_ledger.rs` resolves the same root. Stdlib-only.
"""

import os
import subprocess
from pathlib import Path

ROOT_VAR = "EXTERNAL_DATA_ROOT"
DEFAULT_ROOT = "data/external"


def root(override: Path | None = None) -> Path:
    if override is not None:
        return override
    return Path(os.environ.get(ROOT_VAR) or DEFAULT_ROOT)


def source_dir(source: str, override: Path | None = None) -> Path:
    d = root(override) / source
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetched(source: str, name: str, url: str) -> Path:
    """The local copy of `url` under the source's dir, downloaded once."""
    path = source_dir(source) / name
    if not path.exists():
        part = path.with_suffix(path.suffix + ".part")
        subprocess.run(
            ["curl", "-fsSL", "--retry", "5", "-o", str(part), url], check=True
        )
        part.rename(path)
    return path
