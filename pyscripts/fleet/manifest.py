"""Data-version manifest: what "same data" means, checkably.

Two artifacts:
- **digest** — sha256 over the sorted `path<TAB>size` listing of every file
  rsync pushes (same exclude set). Metadata-only, so it is cheap on a 50 GB
  root, and rsync-stable: a complete transfer reproduces it bit-for-bit, a
  torn one cannot. mtimes are deliberately not part of it.
- **stamp** — one line, `<run_id>:<digest12>`, written into the data root when
  the data is (re)built. The backend reads it at startup and echoes it inside
  `/v1/specs.version`, which is what lets preflight assert that the *running
  process* serves this exact data, not merely that the disk holds it.
"""

import datetime as dt
import json
import shlex
from pathlib import Path

from pyscripts.fleet.remote import Host

STAMP_NAME = "stamp"
# Per-box state, never pushed. Digest equality is meaningful only over pushed
# files, so the digest excludes exactly this set plus the stamp itself (the
# stamp IS pushed — the worker backend reads it — but it describes the data
# rather than being part of it, and the stamp check compares it separately).
PUSH_EXCLUDES = (
    "entity-csvs",
    "cache",
    "search-cache",
    "filter-steps",
    "source-pairs-by-path",
)
DATA_EXCLUDES = (*PUSH_EXCLUDES, STAMP_NAME)
DIGEST_LEN = 12


def digest(host: Host, root: str) -> str:
    prunes = " -o ".join(f"-name {shlex.quote(e)}" for e in DATA_EXCLUDES)
    return host.out(
        f"cd {shlex.quote(root)} && find . \\( {prunes} \\) -prune -o "
        "-type f -printf '%P\\t%s\\n' | LC_ALL=C sort | sha256sum | cut -d' ' -f1"
    ).strip()


def read_stamp(host: Host, root: str) -> str:
    """The stamp line, or '' when the root is unstamped."""
    return host.out(f"cat {shlex.quote(root)}/{STAMP_NAME} 2>/dev/null || true").strip()


def write_stamp(root: str, run_id: str) -> str:
    line = f"{run_id}:{digest(Host('local', None), root)[:DIGEST_LEN]}"
    (Path(root) / STAMP_NAME).write_text(line + "\n")
    return line


def stamp_digest(stamp: str) -> str:
    return stamp.rsplit(":", 1)[-1]


def run_id(root: str | None) -> str:
    """The ledger snapshot run_id when present, else today — names data builds
    (the stamp line here, the artifact commit message in recalc.py)."""
    snap = Path(root or ".") / "user-ledger" / "snapshot_manifest.json"
    if root and snap.exists():
        return json.loads(snap.read_text())["run_id"]
    return dt.date.today().isoformat()
