"""First-run setup for the designer flow (per machine, not per release).

Steps:
    1. preflight: check tools
    2. .env from .env.example (idempotent)
    3. ccl-science-data: clone outside repo + symlink in + regen reader
    4. uv sync + bun install
    5. download nano snapshot artifact → $OA_SNAPSHOT
    6. run pipeline (RANKLESS_ENV=nano) snapshot → $OA_ROOT
    7. cargo build --release -p rankless-server (RANKLESS_ENV=nano)

Run via `make bootstrap`. Idempotent — re-running skips finished steps.

Strict stdlib only at import-time: this script *is* what runs `uv sync`, so
we can't depend on uv-managed packages until after that.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import preflight
from ._common import (
    REPO_ROOT,
    die,
    header,
    info,
    read_env_file,
    resolve_path,
    run,
    warn,
)


CCL_REPO_URL = "https://github.com/CenterForCollectiveLearning/science-data.git"
DEFAULT_CCL_CLONE_DIR = Path.home() / ".cache" / "rankless" / "ccl-science-data"
CCL_LINK = REPO_ROOT / "libs" / "ccl-science-data"

# Designer flow is nano-only — binary's compile-time constants must match the
# dataset's dims (rankless_rs/build.rs reads RANKLESS_ENV at build time).
RANKLESS_ENV_NAME = "nano"

SNAPSHOT_STAMP = ".ready"  # in $OA_SNAPSHOT after download+extract
PIPELINE_STAMP = ".pipeline-done"  # in $OA_ROOT after make complete


# ── Step 1: env file ─────────────────────────────────────────────────────────


def _ensure_env_file() -> dict[str, str]:
    env_path = REPO_ROOT / ".env"
    example = REPO_ROOT / ".env.example"
    if not env_path.exists():
        if not example.exists():
            die(".env.example missing — repo is in a broken state")
        info(f"creating {env_path} from .env.example")
        shutil.copyfile(example, env_path)
    return read_env_file(env_path)


# ── Step 2: ccl-science-data clone + codegen ─────────────────────────────────


def _ensure_ccl() -> None:
    clone_dir = (
        Path(os.environ.get("CCL_CLONE_DIR") or DEFAULT_CCL_CLONE_DIR)
        .expanduser()
        .resolve()
    )

    if clone_dir.exists():
        info(f"ccl-science-data already cloned at {clone_dir}")
    else:
        clone_dir.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", CCL_REPO_URL, str(clone_dir)])

    CCL_LINK.parent.mkdir(parents=True, exist_ok=True)
    if CCL_LINK.is_symlink():
        if CCL_LINK.resolve() != clone_dir:
            CCL_LINK.unlink()
            CCL_LINK.symlink_to(clone_dir)
            info(f"updated symlink {CCL_LINK} → {clone_dir}")
        else:
            info(f"symlink {CCL_LINK} → {clone_dir} (ok)")
    elif CCL_LINK.exists():
        info(f"{CCL_LINK} is a real directory — leaving it alone")
    else:
        CCL_LINK.symlink_to(clone_dir)
        info(f"linked {CCL_LINK} → {clone_dir}")

    gen_reader = (CCL_LINK / "scripts" / "gen_reader.py").resolve()
    if not gen_reader.exists():
        die(f"ccl-science-data is missing scripts/gen_reader.py at {gen_reader}")
    info("regenerating ccl-science-data reader bindings for this snapshot")
    run(
        [sys.executable, str(gen_reader), "--gen-root", str(REPO_ROOT)],
        cwd=gen_reader.parent.parent,
    )


# ── Step 3: deps ─────────────────────────────────────────────────────────────


def _uv_sync() -> None:
    run(["uv", "sync"], cwd=REPO_ROOT)


def _bun_install() -> None:
    run(["bun", "install"], cwd=REPO_ROOT)


# ── Step 4: snapshot artifact ────────────────────────────────────────────────


def _read_stamp(path: Path, name: str) -> str | None:
    stamp = path / name
    return stamp.read_text().strip() if stamp.exists() else None


def _download(url: str, dest: Path) -> None:
    info(f"downloading {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=300) as r, dest.open("wb") as out:
            shutil.copyfileobj(r, out, length=1 << 20)
    except urllib.error.URLError as e:
        die(f"failed to download artifact: {e}")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_tar_zst(archive: Path, target: Path) -> None:
    """Pipe `archive` through `zstd -d`, untar into `target`, flatten top dir."""
    info(f"extracting {archive.name} → {target}")
    target.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(["zstd", "-d", "-c", str(archive)], stdout=subprocess.PIPE)
    assert proc.stdout is not None
    with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
        top: str | None = None
        for member in tar:
            if top is None:
                top = member.name.split("/", 1)[0]
            rel = member.name[len(top) + 1 :] if member.name != top else ""
            if not rel:
                continue
            member.name = rel
            tar.extract(member, path=target, filter="data")
    if proc.wait() != 0:
        die(f"zstd exited {proc.returncode}")


def _ensure_snapshot(env: dict[str, str]) -> Path:
    raw = env.get("OA_SNAPSHOT") or os.environ.get("OA_SNAPSHOT")
    if not raw:
        die("OA_SNAPSHOT not set in .env")
    snapshot = resolve_path(raw)

    url = env.get("NANO_ARTIFACT_URL") or os.environ.get("NANO_ARTIFACT_URL")
    if not url:
        die("NANO_ARTIFACT_URL not set in .env — set it or override via env")
    expected_sha = (
        env.get("NANO_ARTIFACT_SHA256") or os.environ.get("NANO_ARTIFACT_SHA256") or ""
    ).strip()

    fingerprint = expected_sha or url
    if _read_stamp(snapshot, SNAPSHOT_STAMP) == fingerprint:
        info(f"snapshot already present at {snapshot} (stamp matches)")
        return snapshot

    if snapshot.exists():
        warn(f"snapshot stamp differs from expected — re-extracting into {snapshot}")
        shutil.rmtree(snapshot)

    tmp = snapshot.parent / f"{snapshot.name}.tar.zst.partial"
    _download(url, tmp)
    if expected_sha:
        got = _sha256(tmp)
        if got != expected_sha:
            tmp.unlink(missing_ok=True)
            die(f"artifact SHA mismatch — expected {expected_sha}, got {got}")
        info("sha256 verified")

    _extract_tar_zst(tmp, snapshot)
    tmp.unlink(missing_ok=True)
    (snapshot / SNAPSHOT_STAMP).write_text(fingerprint)
    info(f"snapshot ready at {snapshot}")
    return snapshot


# ── Step 5: pipeline (snapshot → OA_ROOT) ────────────────────────────────────


def _force_pipeline_rebuild() -> None:
    """The per-step gen files (`rankless_rs/src/gen/*.rs`) are tracked in git,
    so on a fresh clone they have the same mtime as their step sources and
    `make` treats them as up-to-date — skipping the recipes that actually
    write the binary data into `$OA_ROOT`. Bumping the step mtimes a hair
    ahead invalidates each gen target without touching their content."""
    steps_dir = REPO_ROOT / "rankless_rs" / "src" / "steps"
    future = time.time() + 1.0  # +1s so make sees them as strictly newer
    for entry in steps_dir.rglob("*.rs"):
        os.utime(entry, (future, future))


def _ensure_pipeline(oa_root: Path, snapshot: Path) -> None:
    if _read_stamp(oa_root, PIPELINE_STAMP):
        info(f"pipeline already run (stamp at {oa_root / PIPELINE_STAMP})")
        return
    info(f"running pipeline {snapshot} → {oa_root} (slow on first run)")
    _force_pipeline_rebuild()
    pipeline_env = {**os.environ, "RANKLESS_ENV": RANKLESS_ENV_NAME}
    # Command-line VAR=val beats `include .env` in the Makefile, so we don't
    # touch the user's .env to flip env names.
    run(
        [
            "make",
            f"RANKLESS_ENV={RANKLESS_ENV_NAME}",
            f"OA_ROOT={oa_root}",
            f"OA_SNAPSHOT={snapshot}",
            "build-prep",
            "build-data",
        ],
        cwd=REPO_ROOT,
        env=pipeline_env,
    )
    oa_root.mkdir(parents=True, exist_ok=True)
    (oa_root / PIPELINE_STAMP).write_text("ok\n")
    info(f"pipeline complete → {oa_root}")


# ── Step 6: build the server binary ─────────────────────────────────────────


def _cargo_build_server() -> None:
    build_env = {**os.environ, "RANKLESS_ENV": RANKLESS_ENV_NAME}
    run(
        ["cargo", "build", "--release", "-p", "rankless-server"],
        cwd=REPO_ROOT,
        env=build_env,
    )


# ── Driver ───────────────────────────────────────────────────────────────────


def main() -> None:
    preflight.main()

    header("bootstrap 1/6 — config")
    env = _ensure_env_file()

    header("bootstrap 2/6 — ccl-science-data")
    _ensure_ccl()

    header("bootstrap 3/6 — deps")
    _uv_sync()
    _bun_install()

    header("bootstrap 4/6 — fetch nano snapshot")
    snapshot = _ensure_snapshot(env)

    raw_root = env.get("OA_ROOT") or os.environ.get("OA_ROOT")
    if not raw_root:
        die("OA_ROOT not set in .env")
    oa_root = resolve_path(raw_root)

    header("bootstrap 5/6 — run pipeline")
    _ensure_pipeline(oa_root, snapshot)

    header("bootstrap 6/6 — build server")
    _cargo_build_server()

    header("done")
    info("`make dev` to start the foreground dev environment")


if __name__ == "__main__":
    main()
