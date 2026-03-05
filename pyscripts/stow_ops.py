"""Pipeline artifact stash/restore for branch comparison.

Stashes are stored under stow_root/{label}/ and contain:
  - rankless-server   — compiled binary
  - filter_steps/     — OA_ROOT/filter-steps/
  - entity_mapping/   — OA_ROOT/entity_mapping/
"""

import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ccl_science_data.common import oa_root as _default_data_root

STOW_ROOT = Path("/tmp/rankless-stow")

# Maps artifact name → subdir of data_root
PIPELINE_ARTIFACT_DIRS: dict[str, str] = {
    "filter_steps": "filter-steps",
    "entity_mapping": "entity_mapping",
}


class RebuildLevel(str, Enum):
    none = "none"          # restore all from stow, no build at all
    binary = "binary"      # rebuild binary, restore pipeline outputs from stow
    pipeline = "pipeline"  # rebuild binary + pipeline (make filter), clear cache
    full = "full"          # rebuild everything (make to-csv + make filter + binary)


@dataclass
class StowManager:
    stow_root: Path = field(default_factory=lambda: STOW_ROOT)
    data_root: Path = field(default_factory=lambda: _default_data_root)

    def _label_path(self, label: str) -> Path:
        return self.stow_root / label

    def _binary_dest(self, label: str) -> Path:
        return self._label_path(label) / "rankless-server"

    def _artifact_dest(self, label: str, name: str) -> Path:
        return self._label_path(label) / name

    def has_binary(self, label: str) -> bool:
        return self._binary_dest(label).exists()

    def has_pipeline(self, label: str) -> bool:
        return all(
            self._artifact_dest(label, name).exists()
            for name in PIPELINE_ARTIFACT_DIRS
        )

    def stash_binary(
        self, label: str, binary: Path = Path("target/release/rankless-server")
    ) -> None:
        dest = self._binary_dest(label)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, dest)
        print(f"[stow] binary → {dest}")

    def restore_binary(
        self, label: str, binary: Path = Path("target/release/rankless-server")
    ) -> None:
        src = self._binary_dest(label)
        if not src.exists():
            raise FileNotFoundError(f"No stashed binary for {label!r} at {src}")
        binary.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, binary)
        print(f"[stow] restored binary ← {src}")

    def stash_pipeline(self, label: str) -> None:
        dest_root = self._label_path(label)
        dest_root.mkdir(parents=True, exist_ok=True)
        for name, subdir in PIPELINE_ARTIFACT_DIRS.items():
            src = self.data_root / subdir
            if not src.exists():
                print(f"[stow] skip {name} (not found at {src})")
                continue
            dest = dest_root / name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            print(f"[stow] {name} → {dest}")

    def restore_pipeline(self, label: str) -> None:
        for name, subdir in PIPELINE_ARTIFACT_DIRS.items():
            src = self._artifact_dest(label, name)
            if not src.exists():
                raise FileNotFoundError(
                    f"No stashed pipeline artifact {name!r} for {label!r} at {src}"
                )
            dest = self.data_root / subdir
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            print(f"[stow] restored {name} ← {src}")

    def list_stashes(self) -> dict[str, dict[str, bool]]:
        if not self.stow_root.exists():
            return {}
        return {
            d.name: {
                "binary": (d / "rankless-server").exists(),
                **{name: (d / name).exists() for name in PIPELINE_ARTIFACT_DIRS},
            }
            for d in sorted(self.stow_root.iterdir())
            if d.is_dir()
        }
