"""Cache-warm worker fleet: preflight-gated orchestration + calibration.

The warm run itself is a recalc stage: `make warm-caches` → pyscripts/recalc.py
→ fleet.warm. Config is machine-local at data/warm.toml (docs/deploy.md).
"""

import os

from dotenv import load_dotenv
from protocli import Dispatcher

from pyscripts.fleet.config import DEFAULT_CONFIG, load_config
from pyscripts.fleet.drive import coverage_gate, warm  # noqa: F401 — package API

load_dotenv()


def probe(
    *,
    host: str | None = None,
    repo_dir: str = "",
    data_root: str = "",
    config: str = DEFAULT_CONFIG,
) -> None:
    """Per-machine facts (RAM/disk/cores/checkout/unit/tools) — the readiness
    checklist for a box; --host probes one not yet in the config."""
    from pyscripts.fleet import calibrate

    if host:
        probes = {host: calibrate.probe(host, host, repo_dir, data_root)}
    else:
        fleet = load_config(config, require_bands=False)
        probes = calibrate.probe_fleet(fleet)
    calibrate.print_probes(probes)


def suggest(*, min_citations: int | None = None, config: str = DEFAULT_CONFIG) -> None:
    """Draft complete warm.toml bands/procs/limits from probes + the actual
    worklist (needs the local backend up)."""
    from pyscripts.fleet import calibrate

    fleet = load_config(config, require_bands=False)
    probes = calibrate.probe_fleet(fleet)
    calibrate.print_probes(probes)
    cuts = calibrate.worklist_mcuts(min_citations or fleet.min_citations)
    workers = calibrate.suggest_workers(fleet, probes, cuts)
    print(calibrate.summarize(workers, cuts, fleet.model))
    print()
    print(calibrate.render_toml(fleet, workers))


def run_preflight(*, config: str = DEFAULT_CONFIG) -> None:
    """Run every invariant check against the current fleet, changing nothing —
    the same gate `warm-caches` enforces."""
    # Named to keep the pyscripts.fleet.preflight MODULE reachable as a package
    # attribute — a same-named function would rebind it after import.
    from pyscripts.fleet import preflight

    fleet = load_config(config)
    primary = preflight.Primary.capture()
    checks = [
        c
        for w in fleet.workers
        for c in preflight.full_checks(w, w.conn(), fleet.model, primary)
    ]
    preflight.gate(checks)


def prepare(
    *, only: str | None = None, no_push: bool = False, config: str = DEFAULT_CONFIG
) -> None:
    """Converge the fleet to ready and gate, without computing: push data +
    stamp, pull + rebuild + restart every backend (the local one too), re-check.
    Run only once the primary data is final — see `warm-caches` for the full run."""
    from pyscripts.fleet import drive

    drive.prepare(config, only=only, push=not no_push)


def stamp() -> None:
    """(Re)write the data-root stamp the backend echoes in /v1/specs
    (refresh-data stamps automatically; restart-service after)."""
    from pyscripts.fleet import manifest

    root = os.environ["OA_ROOT"]
    print(f"stamped {root}: {manifest.write_stamp(root, manifest.run_id(root))}")
    print("restart the backend so /v1/specs serves it: make restart-service")


_dispatcher = Dispatcher(
    "pyscripts fleet",
    {
        "probe": probe,
        "suggest": suggest,
        "preflight": run_preflight,
        "prepare": prepare,
        "stamp": stamp,
    },
)
