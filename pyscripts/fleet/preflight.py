"""Preflight gate: every fleet invariant asserted before a worker is trusted.

The failure classes this catches (each burned us or nearly did):
- worker checkout diverged or dirty → computes different trees (repo)
- .env pointing the backend at another root / other compile env (env)
- torn or stale data transfer serving subtly wrong trees (stamp, data)
- build-succeeded-but-old-process-still-bound (version — the /v1/specs
  handshake reflects the *running* process, not the checkout)
- band assignment the box cannot hold in RAM — the OOM class (memory)
- bigs box filling /tmp/dmove-parts or the data push filling the disk (disk)

Every check returns a named `Check` instead of raising, so one dead box
reports as a row in the gate table, and the run aborts before any compute.
"""

import json
import os
import subprocess
from dataclasses import dataclass

from pyscripts.fleet import manifest
from pyscripts.fleet.config import Model, Worker
from pyscripts.fleet.remote import Host

GB = 1024**3
DISK_MARGIN_GB = 5.0
# The pre-warm.toml band knobs — exactly these; other RL_* vars are live
# deploy config and must survive.
STALE_ENV_KNOBS = ("BIG_LIMIT", "RL_BINS", "RL_PROCS")


@dataclass(frozen=True)
class Check:
    worker: str
    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class Primary:
    """What every worker must agree with: the driver box's identity."""

    head: str
    rankless_env: str
    oa_root: str
    stamp: str
    digest: str
    data_size_gb: float

    @property
    def version(self) -> str:
        return f"{self.head}|{self.rankless_env}|{self.stamp}"

    @classmethod
    def capture(cls) -> "Primary":
        local = Host("primary", None)
        root = os.environ["OA_ROOT"]
        stamp = manifest.read_stamp(local, root)
        if not stamp:
            raise SystemExit(
                f"{root} is unstamped — `uv run -m pyscripts fleet stamp` "
                "(refresh-data stamps automatically)"
            )
        dig = manifest.digest(local, root)
        if manifest.stamp_digest(stamp) != dig[: manifest.DIGEST_LEN]:
            raise SystemExit(
                f"data root changed since it was stamped ({stamp}) — restamp with "
                "`uv run -m pyscripts fleet stamp` and `make restart-service`"
            )
        head = subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"], text=True
        ).strip()
        size_b = int(_du_cmd_out(local, root))
        return cls(
            head=head,
            rankless_env=os.environ.get("RANKLESS_ENV", "full"),
            oa_root=root,
            stamp=stamp,
            digest=dig,
            data_size_gb=size_b / GB,
        )


def pre_checks(w: Worker, host: Host, model: Model, primary: Primary) -> list[Check]:
    """Cheap assertions that must hold before pushing 50 GB at a box."""
    checks = [_check(w, "repo", _repo_detail, host, w)]
    if w.host is not None:
        checks += [
            _check(w, "env", _env_detail, host, w, primary),
            _check(w, "disk", _disk_detail, host, w, model, primary),
        ]
    checks.append(_check(w, "memory", _memory_detail, host, w, model))
    return checks


def post_checks(w: Worker, host: Host, primary: Primary) -> list[Check]:
    """After push + rebuild + restart: the box provably runs our build on our data."""
    checks = []
    if w.host is not None:
        checks += [
            _check(w, "stamp", _stamp_detail, host, w, primary),
            _check(w, "data", _data_detail, host, w, primary),
        ]
    checks.append(_check(w, "version", _version_detail, host, w, primary))
    return checks


def full_checks(w: Worker, host: Host, model: Model, primary: Primary) -> list[Check]:
    return pre_checks(w, host, model, primary) + post_checks(w, host, primary)


def gate(checks: list[Check]) -> None:
    """Print the check table; abort before compute if anything failed."""
    for c in checks:
        mark = "ok" if c.ok else "FAIL"
        print(f"  {c.worker:12} {c.name:8} {mark:4} {c.detail}")
    failed = [c for c in checks if not c.ok]
    if failed:
        names = ", ".join(f"{c.worker}/{c.name}" for c in failed)
        raise SystemExit(f"preflight gate: {len(failed)} check(s) failed: {names}")
    print(f"preflight gate: all {len(checks)} checks passed")


def est_peak_gb(w: Worker, model: Model) -> float:
    """Crude linear peak: baseline + the worst (procs × bin hi) product.

    The coefficients live in [model] (docs/deploy.md) and start uncalibrated —
    conservative on purpose; calibrate from a real run's MemoryPeak.
    """
    per_bin = [procs * hi * model.gb_per_mcut for hi, procs in w.bin_edges()]
    return model.mem_base_gb + max(per_bin)


def _check(w: Worker, name: str, fn, *args) -> Check:
    try:
        detail = fn(*args)
        return Check(w.name, name, True, detail)
    except AssertionError as e:
        return Check(w.name, name, False, str(e))
    except Exception as e:
        return Check(w.name, name, False, f"probe failed: {e}")


def _repo_detail(host: Host, w: Worker) -> str:
    # Clean-tree only: the worker may be *behind* here (drive pulls right
    # after), but a dirty tree breaks --ff-only and means hand-edits on a box
    # that must be a pure origin mirror. On the local worker it guards the
    # handshake's blind spot: a dirty driver runs code no commit describes,
    # while still reporting a matching GIT_COMMIT (so: commit-artifacts before
    # warm-caches). Commit equality of the running build is asserted by the
    # post-restart version handshake.
    cd = f"cd {w.repo_dir} && " if w.repo_dir else ""
    dirty = host.out(f"{cd}git status --porcelain --untracked-files=no").strip()
    assert not dirty, f"dirty checkout: {dirty.splitlines()[0]} …"
    head = host.out(f"{cd}git rev-parse --short=12 HEAD").strip()
    return f"clean at {head}"


def _env_detail(host: Host, w: Worker, primary: Primary) -> str:
    remote = _parse_env(host.out(f"cat {w.repo_dir}/.env"))
    stale = [k for k in STALE_ENV_KNOBS if k in remote]
    assert not stale, (
        f"stale cache knob(s) {', '.join(stale)} in .env — bands live in data/warm.toml"
    )
    root = remote.get("OA_ROOT", "").rstrip("/")
    assert root == w.data_root.rstrip("/"), f"OA_ROOT={root} != {w.data_root}"
    renv = remote.get("RANKLESS_ENV", "full")
    assert renv == primary.rankless_env, (
        f"RANKLESS_ENV {renv} != primary {primary.rankless_env}"
    )
    return f"OA_ROOT + RANKLESS_ENV={renv} agree"


def _parse_env(text: str) -> dict[str, str]:
    pairs = {}
    for line in text.splitlines():
        line = line.strip().removeprefix("export ")
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        pairs[k.strip()] = v.strip().strip("'\"")
    return pairs


def _disk_detail(host: Host, w: Worker, model: Model, primary: Primary) -> str:
    avail_gb = _df_avail_gb(host, w.data_root)
    have_gb = int(_du_cmd_out(host, w.data_root, check=False) or 0) / GB
    need_gb = max(0.0, primary.data_size_gb - have_gb) + DISK_MARGIN_GB
    assert avail_gb >= need_gb, (
        f"{w.data_root}: {avail_gb:.0f}G free < {need_gb:.0f}G needed for the push"
    )
    detail = f"{avail_gb:.0f}G free for a {need_gb:.0f}G push"
    if w.bigs:
        tmp_gb = _df_avail_gb(host, "/tmp")
        tmp_need = w.big_chunk * model.parts_gb_per_big
        assert tmp_gb >= tmp_need, (
            f"/tmp: {tmp_gb:.0f}G free < {tmp_need:.0f}G for big_chunk={w.big_chunk} "
            f"(lower big_chunk or clear /tmp/dmove-parts)"
        )
        detail += f"; /tmp {tmp_gb:.0f}G ≥ {tmp_need:.0f}G for bigs"
    return detail


def _memory_detail(host: Host, w: Worker, model: Model) -> str:
    total_gb = int(host.out("free -b | awk '/Mem:/ {print $2}'")) / GB
    need = est_peak_gb(w, model) + model.headroom_gb
    assert total_gb >= need, (
        f"{total_gb:.0f}G RAM < {need:.0f}G modeled peak for band {w.band} — "
        "shrink the band/procs or recalibrate [model]"
    )
    return f"{total_gb:.0f}G RAM ≥ {need:.0f}G modeled peak"


def _stamp_detail(host: Host, w: Worker, primary: Primary) -> str:
    stamp = manifest.read_stamp(host, w.data_root)
    assert stamp == primary.stamp, f"stamp {stamp!r} != primary {primary.stamp!r}"
    return stamp


def _data_detail(host: Host, w: Worker, primary: Primary) -> str:
    dig = manifest.digest(host, w.data_root)
    assert dig == primary.digest, (
        f"data digest {dig[:12]} != primary {primary.digest[:12]} — torn/stale push"
    )
    return f"digest {dig[:12]} matches"


def _version_detail(host: Host, w: Worker, primary: Primary) -> str:
    out = host.out(f"curl -s localhost:{w.port}/v1/specs")
    version = json.loads(out).get("version", "<absent>")
    assert version == primary.version, (
        f"running backend reports {version!r} != expected {primary.version!r} — "
        "stale process, stale build, or stale data at startup"
    )
    return version


def _df_avail_gb(host: Host, path: str) -> float:
    return int(host.out(f"df --output=avail -B1 {path} | tail -1")) / GB


def _du_cmd_out(host: Host, root: str, check: bool = True) -> str:
    excl = " ".join(f"--exclude={e}" for e in manifest.DATA_EXCLUDES)
    return host.out(f"du -sb {excl} {root} 2>/dev/null | cut -f1", check=check).strip()
