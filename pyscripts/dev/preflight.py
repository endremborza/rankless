"""Verify required CLI tools are installed; print install hints when missing."""

from __future__ import annotations

import platform
import shutil
import sys

from ._common import die, header, info, warn


IS_MAC = platform.system() == "Darwin"

# (binary, friendly name, mac install, linux install)
TOOLS = [
    (
        "rustup",
        "Rust toolchain manager",
        "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh",
        "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh",
    ),
    (
        "cargo",
        "Cargo (Rust build)",
        "(installed by rustup; ensure ~/.cargo/bin is on PATH)",
        "(installed by rustup; ensure ~/.cargo/bin is on PATH)",
    ),
    (
        "bun",
        "Bun JS runtime / package manager",
        "brew install oven-sh/bun/bun",
        "curl -fsSL https://bun.sh/install | bash",
    ),
    (
        "uv",
        "uv (Python env/package manager)",
        "brew install uv",
        "curl -LsSf https://astral.sh/uv/install.sh | sh",
    ),
    (
        "git",
        "Git",
        "xcode-select --install",
        "sudo apt install git",
    ),
    (
        "zstd",
        "zstd compressor (used for the nano dataset archive)",
        "brew install zstd",
        "sudo apt install zstd",
    ),
]


def _python_ok() -> bool:
    return sys.version_info >= (3, 12)


def check() -> list[tuple[str, str, str]]:
    missing: list[tuple[str, str, str]] = []
    for binary, label, mac_cmd, linux_cmd in TOOLS:
        if shutil.which(binary):
            info(f"{binary:8} ✓  {label}")
            continue
        missing.append((binary, label, mac_cmd if IS_MAC else linux_cmd))
        warn(f"{binary:8} ✗  {label}")
    if _python_ok():
        info(f"python   ✓  {sys.version.split()[0]} (>=3.12 required)")
    else:
        warn(f"python   ✗  {sys.version.split()[0]} — need >=3.12")
        missing.append(
            (
                "python",
                "Python >= 3.12",
                "brew install python@3.12"
                if IS_MAC
                else "use deadsnakes/pyenv to install 3.12",
            )
        )
    return missing


def main() -> None:
    header("preflight: required tools")
    missing = check()
    if not missing:
        info("all prerequisites present")
        return
    print()
    warn(f"{len(missing)} missing — install with:")
    for name, label, cmd in missing:
        print(f"  # {label}", file=sys.stderr)
        print(f"  {cmd}", file=sys.stderr)
    die("re-run bootstrap once these are installed")


if __name__ == "__main__":
    main()
