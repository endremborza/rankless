"""Branch-to-branch comparison of Rankless server outputs.

Runs two Docker containers — one per branch — then evaluates correctness
(structural tree diff) and timing against the same query set.

Run via the unified CLI:
    uv run -m pyscripts compare-branch [options]

Options:
    --branch-a BRANCH    Branch A (default: current branch)
    --branch-b BRANCH    Branch B (default: rankless-main)
    --rebuild-a LEVEL    none | binary | pipeline | full  (default: pipeline)
    --rebuild-b LEVEL    none | binary | pipeline | full  (default: pipeline)
    --samples N          Entities per citation-count bin (default: 4)
    --artifacts PATH     Output directory (default: logs/comparison-artifacts)

See docs/benchmarking.md for the full explanation.
"""

import argparse
import datetime as dt
import re
from pathlib import Path

import requests
from ccl_science_data.common import oa_root

from pyscripts.cache_prompting import BatchRequester
from pyscripts.comparison_driver import (
    prepare_backend,
    run_query_loop,
    sample_entities,
    write_artifacts,
)
from pyscripts.comparison_report import (
    ARTIFACTS_ROOT,
    MemoryTracker,
    logger,
    setup_logging,
)
from pyscripts.server_ops import DockerServer, checkout, current_branch
from pyscripts.stow_ops import RebuildLevel, StowManager

MAIN_BRANCH = "rankless-main"
PORT_A = 3038
PORT_B = 3039
MEMORY_LIMIT = "10g"
CPU_LIMIT = "4"

SAMPLE_BINS = [1_000, 5_000, 10_000, 30_000, 100_000, 200_000]


def _slug(branch: str) -> str:
    return "rankless-branch-" + re.sub(r"[^a-z0-9]", "-", branch.lower())


def _server(branch: str, host_port: int, data_root: Path) -> DockerServer:
    return DockerServer(
        container=_slug(branch),
        image=_slug(branch),
        host_port=host_port,
        data_root=data_root,
        memory=MEMORY_LIMIT,
        cpus=CPU_LIMIT,
    )


def _prepare_branch(branch: str, rebuild: RebuildLevel, stow: StowManager) -> None:
    """Checkout the branch, build per rebuild level, stash data, build the image."""
    checkout(branch)
    prepare_backend(
        rebuild,
        _server(branch, PORT_A, oa_root),
        stow=stow,
        stash_label=branch,
    )


def _make_fetch_pair(url_a: str, url_b: str):
    def fetch_pair(row, tid, _bds):
        a = re.sub(r"tid=\d+", f"tid={tid}", row["url"])
        b = a.replace(url_a, url_b, 1)
        resp_a = requests.get(a, timeout=120)
        resp_b = requests.get(b, timeout=120)
        resp_a.raise_for_status()
        resp_b.raise_for_status()
        return (
            resp_a.json()["tree"]["children"],
            resp_b.json()["tree"]["children"],
            resp_a.elapsed.total_seconds(),
            resp_b.elapsed.total_seconds(),
        )

    return fetch_pair


# ── entry point ───────────────────────────────────────────────────────────────


def run_comparison(
    branch_a: str,
    branch_b: str,
    rebuild_a: RebuildLevel,
    rebuild_b: RebuildLevel,
    e_per_bin: int,
    artifacts_dir: Path,
) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(artifacts_dir / "comparison.log")
    logger.info("comparing A=%s vs B=%s", branch_a, branch_b)

    label_a = re.sub(r"[^a-zA-Z0-9._-]", "-", branch_a)
    label_b = re.sub(r"[^a-zA-Z0-9._-]", "-", branch_b)

    stow = StowManager()
    original_branch = current_branch()
    mem_tracker: MemoryTracker | None = None

    try:
        for branch, rb in [(branch_a, rebuild_a), (branch_b, rebuild_b)]:
            logger.info("preparing branch %s (rebuild=%s)", branch, rb.value)
            _prepare_branch(branch, rb, stow)
        checkout(original_branch)

        server_a = _server(branch_a, PORT_A, stow.data_root_for(branch_a))
        server_b = _server(branch_b, PORT_B, stow.data_root_for(branch_b))
        server_a.start()
        server_b.start()
        server_a.wait_ready()
        server_b.wait_ready()

        requester = BatchRequester(min_citations=SAMPLE_BINS[0], addr=server_a.base_url)
        sample_df = sample_entities(requester.urled_sample, SAMPLE_BINS, e_per_bin)
        fetch_pair = _make_fetch_pair(server_a.base_url, server_b.base_url)

        mem_tracker = MemoryTracker(
            {server_a.container: label_a, server_b.container: label_b}
        )
        mem_tracker.start()
        results = list(run_query_loop(sample_df, requester.specs, fetch_pair))
        mem_tracker.stop()

        server_a.stop()
        server_b.stop()
    finally:
        if current_branch() != original_branch:
            checkout(original_branch)

    write_artifacts(results, label_a, label_b, artifacts_dir, mem_tracker=mem_tracker)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    rvals = [r.value for r in RebuildLevel]
    parser.add_argument("--branch-a", default=None, help="Branch A (default: current)")
    parser.add_argument(
        "--branch-b", default=MAIN_BRANCH, help=f"Branch B (default: {MAIN_BRANCH})"
    )
    parser.add_argument(
        "--rebuild-a",
        default="pipeline",
        choices=rvals,
        help="Rebuild level for branch A (default: pipeline)",
    )
    parser.add_argument(
        "--rebuild-b",
        default="pipeline",
        choices=rvals,
        help="Rebuild level for branch B (default: pipeline)",
    )
    parser.add_argument(
        "--samples", type=int, default=4, help="Entities per citation-count bin"
    )
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=ARTIFACTS_ROOT,
        help=f"Output directory (default: {ARTIFACTS_ROOT})",
    )


def run(args: argparse.Namespace) -> None:
    branch_a = args.branch_a or current_branch()
    slug = (
        "branch-"
        + re.sub(r"[^a-z0-9]", "-", branch_a.lower())
        + "-vs-"
        + re.sub(r"[^a-z0-9]", "-", args.branch_b.lower())
    )
    ts = dt.datetime.now().strftime("%Y-%m-%d-%H-%M")
    run_comparison(
        branch_a=branch_a,
        branch_b=args.branch_b,
        rebuild_a=RebuildLevel(args.rebuild_a),
        rebuild_b=RebuildLevel(args.rebuild_b),
        e_per_bin=args.samples,
        artifacts_dir=args.artifacts / f"{ts}-{slug}",
    )
