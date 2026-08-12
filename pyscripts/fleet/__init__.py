"""Cache-warm worker fleet: preflight-gated orchestration + calibration.

    uv run -m pyscripts fleet <action>

Actions:
    probe      per-machine facts (RAM/disk/cores/checkout/unit/tools) — the
               readiness checklist for a box; --host probes one not yet in the
               config (pair with --repo-dir/--data-root once it has them)
    suggest    draft complete warm.toml bands/procs/limits from probes + the
               actual worklist (needs the local backend up)
    preflight  run every invariant check against the current fleet, changing
               nothing — the same gate `deploy warm-caches` enforces
    stamp      (re)write the data-root stamp the backend echoes in /v1/specs
               (refresh-data stamps automatically; restart-service after)

The warm run itself is a release stage: `make warm-caches` → pyscripts/release.py
→ fleet.warm. Config is machine-local at data/warm.toml (docs/deploy.md).
"""

import os

from dotenv import load_dotenv

from pyscripts.fleet.config import DEFAULT_CONFIG, load_config
from pyscripts.fleet.drive import coverage_gate, warm  # noqa: F401 — package API

load_dotenv()

ACTIONS = ("probe", "suggest", "preflight", "stamp")


def add_arguments(parser) -> None:
    parser.add_argument("action", choices=ACTIONS)
    parser.add_argument(
        "--config", default=DEFAULT_CONFIG, help="fleet toml (machine-local)"
    )
    parser.add_argument(
        "--host", help="probe: an ssh alias not (yet) in the fleet config"
    )
    parser.add_argument("--repo-dir", default="", help="probe: checkout on --host")
    parser.add_argument("--data-root", default="", help="probe: data root on --host")
    parser.add_argument(
        "--min-citations", type=int, help="suggest: override the fleet worklist floor"
    )


def run(args) -> None:
    dispatch = {
        "probe": _probe,
        "suggest": _suggest,
        "preflight": _preflight,
        "stamp": _stamp,
    }
    assert set(dispatch) == set(ACTIONS)
    dispatch[args.action](args)


def _stamp(args) -> None:
    from pyscripts.fleet import manifest

    root = os.environ["OA_ROOT"]
    print(f"stamped {root}: {manifest.write_stamp(root, manifest.run_id(root))}")
    print("restart the backend so /v1/specs serves it: make restart-service")


def _probe(args) -> None:
    from pyscripts.fleet import calibrate

    if args.host:
        probes = {
            args.host: calibrate.probe(
                args.host, args.host, args.repo_dir, args.data_root
            )
        }
    else:
        fleet = load_config(args.config, require_bands=False)
        probes = calibrate.probe_fleet(fleet)
    calibrate.print_probes(probes)


def _suggest(args) -> None:
    from pyscripts.fleet import calibrate

    fleet = load_config(args.config, require_bands=False)
    probes = calibrate.probe_fleet(fleet)
    calibrate.print_probes(probes)
    cuts = calibrate.worklist_mcuts(args.min_citations or fleet.min_citations)
    workers = calibrate.suggest_workers(fleet, probes, cuts)
    print(calibrate.summarize(workers, cuts, fleet.model))
    print()
    print(calibrate.render_toml(fleet, workers))


def _preflight(args) -> None:
    from pyscripts.fleet import preflight

    fleet = load_config(args.config)
    primary = preflight.Primary.capture()
    checks = [
        c
        for w in fleet.workers
        for c in preflight.full_checks(w, w.conn(), fleet.model, primary)
    ]
    preflight.gate(checks)
