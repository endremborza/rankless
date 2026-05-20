"""Package the nano OpenAlex *snapshot* (filtered raw JSON) for the designer flow.

Maintainer-only. Tars + zstds `$OA_TEST_ROOT/nano-snapshot/` so collaborators
can download it and run the pipeline themselves — bootstrap does that.

Why the snapshot and not OA_ROOT?
  - The snapshot is small and portable filtered raw JSON
  - The pipeline + cargo builds must happen on the designer's machine so the
    binary's compile-time constants (see rankless_rs/build.rs) match the
    dataset's dims; shipping a pre-built OA_ROOT couples those.

Usage:
    uv run -m pyscripts.dev.build_nano_artifact
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from ._common import REPO_ROOT, die, env_with_dotenv, header, info


ENV_NAME = "nano"
DEFAULT_OUTPUT = REPO_ROOT / f"{ENV_NAME}-snapshot.tar.zst"
ZSTD_LEVEL = "19"


def _which_zstd() -> str:
    path = shutil.which("zstd")
    if not path:
        die(
            "`zstd` binary not found — install it (`brew install zstd` / `apt install zstd`)"
        )
    return path


def _resolve_test_root() -> Path:
    env = env_with_dotenv()
    raw = env.get("OA_TEST_ROOT") or os.environ.get("OA_TEST_ROOT")
    if not raw:
        die(
            "OA_TEST_ROOT not set. It points at the parent dir holding "
            "{nano,micro,mini}-snapshot/ — see .env.example."
        )
    p = Path(raw).expanduser()
    return p if p.is_absolute() else (REPO_ROOT / p).resolve()


def _tar_to_zst(source: Path, output: Path) -> None:
    info(f"archiving {source} → {output} (zstd -{ZSTD_LEVEL})")
    zstd = _which_zstd()
    proc = subprocess.Popen(
        [zstd, "-T0", f"-{ZSTD_LEVEL}", "-o", str(output), "-f"],
        stdin=subprocess.PIPE,
    )
    assert proc.stdin is not None
    with tarfile.open(fileobj=proc.stdin, mode="w|") as tar:
        tar.add(source, arcname=source.name)
    proc.stdin.close()
    if proc.wait() != 0:
        die(f"zstd exited {proc.returncode}")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"destination tar.zst (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args(argv)

    header(f"package {ENV_NAME} snapshot")
    test_root = _resolve_test_root()
    snapshot = test_root / f"{ENV_NAME}-snapshot"
    info(f"OA_TEST_ROOT  = {test_root}")
    info(f"nano-snapshot = {snapshot}")

    if not snapshot.is_dir():
        die(
            f"nano snapshot missing at {snapshot}\n"
            f"build it once with:  uv run -m pyscripts.make_test_dataset"
        )

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    _tar_to_zst(snapshot, output)

    digest = _sha256(output)
    sidecar = output.with_suffix(output.suffix + ".sha256")
    sidecar.write_text(f"{digest}  {output.name}\n")
    size_mb = output.stat().st_size / (1 << 20)
    info(f"sha256 {digest}")
    info(f"size   {size_mb:.1f} MiB")
    info(f"wrote  {output}")
    info(f"wrote  {sidecar}")
    print(
        f"\nServe `{output.parent}` (e.g. `python -m http.server 8000`)\n"
        f"and set in collaborators' .env:\n"
        f"  NANO_ARTIFACT_URL=http://<host>:8000/{output.name}\n"
        f"  NANO_ARTIFACT_SHA256={digest}"
    )


if __name__ == "__main__":
    main(sys.argv[1:])
