import subprocess
import sys
from pathlib import Path

import ccl_science_data
from ccl_science_data.common import oa_root

MEMORY_LIMIT = "8g"
CPU_LIMIT = "4"

# Derive the ccl-science-data source tree from the installed package location
CCL_LIB = Path(ccl_science_data.__file__).parent.parent

RUST_BINARY = Path("target/release/rankless-server")

PG_PYTHON_IMAGE = "rankless-pg-python"
RUST_IMAGE = "rankless-rust"
PG_PYTHON_CONTAINER = "rankless-pg-python"
RUST_CONTAINER = "rankless-rust"


def run(cmd: list) -> None:
    print("$", " ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True)


def build_images() -> None:
    run(
        [
            "docker",
            "build",
            "-f",
            "sql-yardstick/docker/Dockerfile.pg-python",
            "-t",
            PG_PYTHON_IMAGE,
            ".",
        ]
    )
    run(
        [
            "docker",
            "build",
            "-f",
            "sql-yardstick/docker/Dockerfile.rust",
            "-t",
            RUST_IMAGE,
            ".",
        ]
    )


def stop_containers() -> None:
    subprocess.run(
        ["docker", "rm", "-f", PG_PYTHON_CONTAINER, RUST_CONTAINER],
        capture_output=True,
    )


def start_containers() -> None:
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            RUST_CONTAINER,
            "--network",
            "host",
            "--memory",
            MEMORY_LIMIT,
            "--cpus",
            CPU_LIMIT,
            "-v",
            f"{oa_root}:/data/oa-root:ro",
            RUST_IMAGE,
        ]
    )
    run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            PG_PYTHON_CONTAINER,
            "--memory",
            MEMORY_LIMIT,
            "--cpus",
            CPU_LIMIT,
            "-p",
            "5000:5000",
            "-v",
            f"{oa_root}:/data/oa-root:ro",
            "-v",
            f"{CCL_LIB}:/ccl-science-data:ro",
            PG_PYTHON_IMAGE,
        ]
    )


if __name__ == "__main__":
    if not RUST_BINARY.exists():
        print(
            f"ERROR: {RUST_BINARY} not found — build it first with: make run-server",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"oa_root  : {oa_root}")
    print(f"ccl_lib  : {CCL_LIB}")
    print(f"memory   : {MEMORY_LIMIT} per container")
    print(f"cpus     : {CPU_LIMIT} per container")
    print()

    build_images()
    stop_containers()
    start_containers()

    print()
    print(f"rust server  → http://127.0.0.1:3038  (host network)")
    print(f"flask + pg   → http://localhost:5000   (loading data, not ready yet)")
    print()
    print(f"follow pg-python logs:  docker logs -f {PG_PYTHON_CONTAINER}")
    print(f"follow rust logs:       docker logs -f {RUST_CONTAINER}")
