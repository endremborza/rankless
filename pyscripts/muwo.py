"""Build muwo's search library and ship it to the checkouts that build the backend.

`install` runs `make dist` in the muwo checkout linked at `MUWO_SRC` and installs the
library into this checkout's `MUWO_LIB_DIR` (`.cargo/config.toml`); `push` also sends it
into the primary data box's checkout (`$DATA_BOX_CHECKOUT`, host:path), where the
backend loads it at its next start. A library speaking another ABI than this checkout's
binding (`rankless_server/src/muwo.rs`) is refused before it is installed. `push_lib` is
the one definition of sending it into another checkout, which the warm fleet and the box
deploy run before each backend build there.
"""

import argparse
import ctypes
import os
import shutil
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path

from wire.rankless_server.muwo import ABI

REPO = Path(__file__).resolve().parents[1]
MUWO_SRC = REPO / "libs/muwo"
DIST_LIB = MUWO_SRC / "target/dist/libmuwo.so"
DATA_BOX_CHECKOUT = "DATA_BOX_CHECKOUT"


class _Bytes(ctypes.Structure):
    _fields_ = [("ptr", ctypes.POINTER(ctypes.c_char)), ("len", ctypes.c_size_t)]


def lib_dir() -> Path:
    env = tomllib.loads((REPO / ".cargo/config.toml").read_text())["env"]
    return REPO / env["MUWO_LIB_DIR"]["value"]


def push_lib(rsync: Callable[[str, str], None], checkout: str) -> str:
    """Send this checkout's library directory into the same directory of `checkout`
    (a path or `host:path` on the transport's far side) and return that directory.
    rsync replaces each file by rename, so a running backend there keeps the library
    it mapped."""
    lib = lib_dir()
    far = f"{checkout.rstrip('/')}/{lib.relative_to(REPO)}/"
    rsync(f"{lib}/", far)
    return far


def checked_version(lib_path: Path) -> str:
    lib = ctypes.CDLL(str(lib_path))
    lib.muwo_abi.restype = ctypes.c_uint32
    lib.muwo_version.restype = _Bytes
    if (abi := lib.muwo_abi()) != ABI:
        raise SystemExit(f"{lib_path} speaks ABI {abi}, this checkout's binding {ABI}")
    version = lib.muwo_version()
    return ctypes.string_at(version.ptr, version.len).decode()


def install() -> Path:
    if not MUWO_SRC.is_dir():
        raise SystemExit(f"link the muwo checkout at {MUWO_SRC}")
    subprocess.run(["make", "-C", str(MUWO_SRC), "dist"], check=True)
    version = checked_version(DIST_LIB)
    dst = lib_dir() / DIST_LIB.name
    dst.parent.mkdir(exist_ok=True)
    tmp = dst.with_name(f".{dst.name}.tmp")
    shutil.copy2(DIST_LIB, tmp)
    # a new inode: a running backend keeps the library it mapped
    os.replace(tmp, dst)
    print(f"muwo {version} installed at {dst}")
    return dst


def push() -> None:
    if not (remote := os.environ.get(DATA_BOX_CHECKOUT)):
        raise SystemExit(
            f"set ${DATA_BOX_CHECKOUT} (host:path of its rankless checkout)"
        )
    far = push_lib(
        lambda src, dst: subprocess.run(
            ["rsync", "-a", "--mkpath", "--itemize-changes", src, dst], check=True
        ),
        remote,
    )
    print(f"pushed to {far}; the backend there loads it at its next start")


def main() -> None:
    p = argparse.ArgumentParser(description="Build, install and push muwo's library.")
    p.add_argument("action", choices=("install", "push"))
    action = p.parse_args().action
    install()
    if action == "push":
        push()


if __name__ == "__main__":
    main()
