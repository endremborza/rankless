"""Pipeline artifact stash for branch comparison.

Stash = full copy of OA_ROOT into stow_root/{label}/ via rsync.
The stash directory can then be mounted directly as a Docker data root,
so there is no copy-back step — just use data_root_for(label).

Stash is intentionally coarse: either the full data directory is stashed,
or nothing. This avoids partial state and makes the data root unambiguous.
"""

import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ccl_science_data.common import oa_root as _default_data_root

STOW_ROOT = Path("/tmp/rankless-stow")


class RebuildLevel(str, Enum):
    none = "none"  # no build; use existing Docker image + existing/stowed data
    binary = "binary"  # rebuild binary + Docker image; use existing data, clear cache
    pipeline = "pipeline"  # rebuild binary + run make filter; stash result; build image
    full = "full"  # rebuild binary + make to-csv + make filter; stash; build image


@dataclass
class StowManager:
    stow_root: Path = field(default_factory=lambda: STOW_ROOT)
    data_root: Path = field(default_factory=lambda: _default_data_root)

    def _label_path(self, label: str) -> Path:
        return self.stow_root / label

    def has_data(self, label: str) -> bool:
        p = self._label_path(label)
        return p.exists() and any(p.iterdir())

    def data_root_for(self, label: str) -> Path:
        """Return stash path if it exists, otherwise fall back to the live data root."""
        if self.has_data(label):
            return self._label_path(label)
        return self.data_root

    def stash(self, label: str) -> None:
        """Rsync full data_root into stow_root/{label}/."""
        dest = self._label_path(label)
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "rsync",
                "--exclude",
                "*.csv.gz",
                "--exclude",
                "cache",
                "-a",
                "--delete",
                f"{self.data_root}/",
                str(dest),
            ],
            check=True,
        )
        print(f"[stow] {label} ← {self.data_root}")

    def list_stashes(self) -> list[str]:
        if not self.stow_root.exists():
            return []
        return sorted(d.name for d in self.stow_root.iterdir() if d.is_dir())
