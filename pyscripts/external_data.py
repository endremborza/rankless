"""External data sources the pipeline reads but does not produce, and the agent runs.

Everything from outside OpenAlex lives in two roots, a directory per source in each,
outside the repo, the snapshot and `$OA_ROOT` so it is never published and a snapshot
update or `make nuke` never purges it:

- `KEPT` (`$EXTERNAL_KEPT_ROOT`): what exists nowhere else, made by hand or by an agent:
  the curated ledger, the enrichment tables, the agent runs (`pyscripts/explore/runs.py`).
- `REGEN` (`$EXTERNAL_REGEN_ROOT`): what a box can fetch or derive again: the downloads,
  each in its source's `raw/`, and the tables reduced from them.

Unset, a root is its default under the repo (a dev box). A table the pipeline reads is
required once the variable names its root and optional under the default, the rule
`rankless_rs/src/derived_ledger.rs` applies to the regen root. Each root syncs with its
remote (`host:/path`, `$EXTERNAL_KEPT_REMOTE`, `$EXTERNAL_REGEN_REMOTE`):
`make external-push|external-pull`, additive, never deleting on the far side, and never
carrying a `raw/`: each box fetches its own downloads. Stdlib-only.
"""

import argparse
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from wire.rankless_rs.derived_ledger import (
    DEFAULT_EXTERNAL_REGEN_ROOT,
    EXTERNAL_REGEN_ROOT,
)

EXTERNAL_KEPT_ROOT = "EXTERNAL_KEPT_ROOT"
DEFAULT_EXTERNAL_KEPT_ROOT = "data/external/kept"
RAW = "raw"


@dataclass(frozen=True)
class Root:
    var: str
    default: str
    remote_var: str

    def named(self) -> bool:
        return bool(os.environ.get(self.var))

    def path(self, override: Path | None = None) -> Path:
        if override is not None:
            return override
        return Path(os.environ.get(self.var) or self.default)

    def source_dir(self, source: str, override: Path | None = None) -> Path:
        d = self.path(override) / source
        d.mkdir(parents=True, exist_ok=True)
        return d

    def table(self, source: str, name: str) -> Path | None:
        """The source's table, or None when it is missing under the default root."""
        path = self.path() / source / name
        if path.exists():
            return path
        if self.named():
            raise FileNotFoundError(f"{path} is missing under ${self.var}")
        return None


KEPT = Root(EXTERNAL_KEPT_ROOT, DEFAULT_EXTERNAL_KEPT_ROOT, "EXTERNAL_KEPT_REMOTE")
REGEN = Root(EXTERNAL_REGEN_ROOT, DEFAULT_EXTERNAL_REGEN_ROOT, "EXTERNAL_REGEN_REMOTE")
ROOTS = (KEPT, REGEN)


def raw_dir(source: str, override: Path | None = None) -> Path:
    d = REGEN.source_dir(source, override) / RAW
    d.mkdir(exist_ok=True)
    return d


def download(url: str, path: Path) -> Path:
    """`path`, downloaded from `url` once; an interrupted download resumes from its `.part`."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix(path.suffix + ".part")
        subprocess.run(
            ["curl", "-fsSL", "--retry", "20", "--retry-all-errors"]
            + ["-C", "-", "-o", str(part), url],
            check=True,
        )
        part.rename(path)
    return path


def fetched(source: str, name: str, url: str, override: Path | None = None) -> Path:
    """The local copy of `url` in the source's `raw/` under the regen root."""
    return download(url, raw_dir(source, override) / name)


def sync(direction: str, root: Root, remote: str) -> None:
    local, far = f"{root.path()}/", f"{remote.rstrip('/')}/"
    src, dst = (local, far) if direction == "push" else (far, local)
    subprocess.run(
        ["rsync", "-a", "--itemize-changes", f"--exclude=/*/{RAW}/", src, dst],
        check=True,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Sync both external data roots.")
    p.add_argument("direction", choices=("push", "pull"))
    direction = p.parse_args().direction
    for root in ROOTS:
        if not root.named():
            raise SystemExit(f"${root.var} is unset: only a named root syncs")
        if not os.environ.get(root.remote_var):
            raise SystemExit(f"set ${root.remote_var} (host:/path)")
    for root in ROOTS:
        sync(direction, root, os.environ[root.remote_var])


if __name__ == "__main__":
    main()
