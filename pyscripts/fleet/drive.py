"""Phased fleet orchestration for the cache warm (`pyscripts recalc warm-caches`).

Phases, with a hard barrier before any compute:

1. **prepare** (all workers, parallel): pre-checks → push data + seed cache →
   pull + rebuild + restart → wait ready → post-checks (identity handshake).
   The local worker rebuilds + restarts too — `commit-artifacts` moves HEAD
   after `refresh-data` built the running binary, so without a restart the
   version handshake would fail on every real release.
2. **gate**: every check from every worker on one table; any failure — including
   a worker whose whole prepare raised — is a row here, and aborts before hours
   of compute, while the run is still free to rerun.
3. **compute** (all workers, parallel): banded `cache bigs`/`cache rest`,
   with periodic cache sync-back from remotes.
4. **verify**: final sync-back + the disk-only coverage gate over the full
   warm worklist on the primary root.

The cache directory is the state — workers skip already-cached trees — so the
whole flow is resumable by rerunning it. Run from tmux on the primary data box.
`pyscripts fleet prepare` runs phases 1–2 standalone (converge + gate, no compute).
"""

import shlex
import threading
import time

from pyscripts import gitutil, services
from pyscripts.fleet import manifest, preflight
from pyscripts.fleet.config import Fleet, Worker, load_config
from pyscripts.fleet.preflight import Check, Primary
from pyscripts.fleet.remote import log, rsync

SYNC_BACK_S = 600
READY_ATTEMPTS = 240  # × 15s: a large box can take a while to load
# Workers can sit outside the /mnt/data sync network, where the science-data
# editable cannot resolve and psycopg2 cannot build (libpq) — neither is needed
# to serve trees or run the cache CLI. Frozen = exactly the pulled lock; the
# compute phase then runs `uv run --no-sync` against this env.
WORKER_SYNC = (
    "uv sync --frozen"
    " --no-install-package ccl-science-data --no-install-package psycopg2"
)


def prepare(config: str, only: str | None = None, push: bool = True) -> None:
    """Phases 1–2 without compute: converge every worker to ready and gate.

    Fixes what the read-only preflight can only report — pushes data + stamp,
    pulls + rebuilds + restarts backends (the local one too) — then re-checks.
    Only worth running once the primary data is final; before `refresh-data`
    it would push soon-to-be-stale data.
    """
    fleet = load_config(config)
    workers = _select(fleet, only)
    _prepare_gate(workers, fleet, push)


def warm(config: str, only: str | None = None, push: bool = True) -> None:
    fleet = load_config(config)
    workers = _select(fleet, only)
    primary = _prepare_gate(workers, fleet, push)

    errors = _phase(workers, lambda w: _compute(w, fleet, primary.oa_root))
    failed = [name for name, e in errors.items() if e]
    if failed:
        raise SystemExit(f"workers failed: {', '.join(failed)} — rerun to resume")
    coverage_gate(primary.oa_root, fleet.min_citations)


def coverage_gate(local_root: str, min_citations: int) -> None:
    """Every tree of the warm worklist must be fully cached on the primary root.

    Disk-only apart from the /v1/specs period count — no tree requests — so a
    missing big can never trigger an out-of-memory compute on this box.
    """
    from pyscripts.cache_prompting import BatchRequester, tree_cached

    br = BatchRequester(min_citations=min_citations)
    sample = br.urled_sample
    missing = [
        s for _, s in sample.iterrows() if not tree_cached(s, br.n_periods, local_root)
    ]
    if missing:
        for s in missing[:20]:
            print(f"  missing: {s['rt']}/{s['dmId']}/{s['tid']} ({s['semanticId']})")
        raise SystemExit(
            f"coverage gate: {len(missing)}/{len(sample)} trees uncached or torn — "
            "check worker bands cover [0, ∞) and rerun"
        )
    print(f"coverage gate: all {len(sample)} trees cached")


def _prepare_gate(workers: list[Worker], fleet: Fleet, push: bool) -> Primary:
    if any(w.host for w in workers):
        # Workers pull from origin; anything not pushed cannot reach them and
        # would only surface later as a version-handshake failure.
        gitutil.assert_pushed()
    primary = Primary.capture()
    checks = _phase(
        workers,
        lambda w: _prepare(w, fleet, primary, push),
        on_error=lambda w, e: [Check(w.name, "prepare", False, str(e))],
    )
    preflight.gate([c for cs in checks.values() for c in cs])
    return primary


def _select(fleet: Fleet, only: str | None) -> list[Worker]:
    if not only:
        return fleet.workers
    workers = [w for w in fleet.workers if w.name == only]
    if not workers:
        raise SystemExit(f"no worker named {only!r} in the fleet config")
    return workers


def _phase(workers: list[Worker], fn, on_error=lambda w, e: e) -> dict:
    """Run fn per worker in parallel; a raised exception maps through on_error."""
    results: dict[str, object] = {}

    def _one(w: Worker) -> None:
        try:
            results[w.name] = fn(w)
        except Exception as e:
            results[w.name] = on_error(w, e)
            log(w.name, f"FAILED: {e}")

    threads = [threading.Thread(target=_one, args=(w,)) for w in workers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def _prepare(w: Worker, fleet: Fleet, primary: Primary, push: bool) -> list[Check]:
    host = w.conn()
    checks = preflight.pre_checks(w, host, fleet.model, primary)
    if any(not c.ok for c in checks):
        return checks  # don't push 50 GB at a box that already failed
    if w.host is None:
        log(w.name, "rebuild + restart backend")
        host.stream("make restart-service")
    else:
        if push:
            _invalidate_stale_cache(w, host, primary)
            _push_data(w, primary.oa_root)
        log(w.name, "pull + sync + build + restart backend")
        host.stream(
            f"cd {w.repo_dir} && git pull --ff-only && {WORKER_SYNC} && "
            "make restart-service"
        )
    _wait_ready(w, host)
    return checks + preflight.post_checks(w, host, primary)


def _compute(w: Worker, fleet: Fleet, local_root: str) -> None:
    if w.host is None:
        return _run_actions(w, fleet)
    stop_sync = threading.Event()
    syncer = threading.Thread(target=_sync_back_loop, args=(w, local_root, stop_sync))
    syncer.start()
    try:
        _run_actions(w, fleet)
    finally:
        stop_sync.set()
        syncer.join()
    _sync_back(w, local_root)


def _run_actions(w: Worker, fleet: Fleet) -> None:
    for action in w.actions():
        log(w.name, f"cache {action} band={w.band}")
        flags = shlex.join(w.cache_flags(fleet.min_citations))
        if w.host is None:  # the driver box has the full, auto-synced env
            w.conn().stream(f"uv run -m pyscripts cache {action} {flags}")
        else:
            w.conn().stream(
                f"cd {w.repo_dir} && uv run --no-sync -m pyscripts cache "
                f"{action} {flags}"
            )


def _invalidate_stale_cache(w: Worker, host, primary: Primary) -> None:
    stamp = manifest.read_stamp(host, w.data_root)
    if stamp != primary.stamp:
        log(w.name, f"data stamp changed ({stamp or 'none'}) — wiping tree cache")
        host.out(f"rm -rf {shlex.quote(w.data_root)}/cache")


def _push_data(w: Worker, local_root: str) -> None:
    log(w.name, "pushing data + seeding cache")
    # --delete makes the worker root a true mirror (mod the excluded per-box
    # dirs, which rsync protects) — the manifest check depends on it.
    rsync(
        f"{local_root}/",
        f"{w.host}:{w.data_root}/",
        w.name,
        excludes=manifest.PUSH_EXCLUDES,
        delete=True,
    )
    rsync(f"{local_root}/cache/", f"{w.host}:{w.data_root}/cache/", w.name)


def _sync_back(w: Worker, local_root: str) -> None:
    rsync(f"{w.host}:{w.data_root}/cache/", f"{local_root}/cache/", w.name)


def _sync_back_loop(w: Worker, local_root: str, stop: threading.Event) -> None:
    while not stop.wait(SYNC_BACK_S):
        try:
            _sync_back(w, local_root)
        except Exception as e:
            log(w.name, f"periodic sync-back failed (will retry): {e}")


def _wait_ready(w: Worker, host) -> None:
    probe = f"curl -s -o /dev/null -w '%{{http_code}}' localhost:{w.port}/v1/specs"
    for _ in range(READY_ATTEMPTS):
        if host.out(probe, check=False).strip() == "200":
            log(w.name, "backend ready")
            return
        state = host.out(
            f"systemctl --user is-active {services.BACKEND_UNIT}", check=False
        ).strip()
        if state == "failed":
            raise RuntimeError(
                f"[{w.name}] backend unit failed — journalctl on the box"
            )
        time.sleep(15)
    raise TimeoutError(f"[{w.name}] backend not ready — journalctl on the box")
