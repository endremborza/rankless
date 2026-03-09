"""Branch-to-branch comparison of Rankless server outputs.

Runs two Docker containers — one per branch — then evaluates correctness
(structural tree diff) and timing against the same query set.

Usage:
    python -m pyscripts.branch_comparison [options]

Options:
    --branch-a BRANCH    Branch A (default: current branch)
    --branch-b BRANCH    Branch B (default: rankless-main)
    --rebuild-a LEVEL    none | binary | pipeline | full  (default: pipeline)
    --rebuild-b LEVEL    none | binary | pipeline | full  (default: pipeline)
    --samples N          Entities per citation-count bin (default: 4)
    --artifacts PATH     Output directory (default: docs/comparison-artifacts)

See logs/comparisons-and-benchmarking.md for full explanation.
"""

import argparse
import datetime as dt
import re
import subprocess
from pathlib import Path
from typing import Iterator

import pandas as pd
import requests
from ccl_science_data.common import oa_root
from tqdm import tqdm

from pyscripts.cache_prompting import BatchRequester, RTC
from pyscripts.comparison_report import (
    ARTIFACTS_ROOT,
    CompResult,
    MemoryTracker,
    build_grouped_df,
    build_mem_stats,
    build_summary_df,
    build_totals,
    logger,
    open_report,
    plot_accuracy,
    plot_memory,
    plot_timing,
    print_report,
    save_html,
    save_markdown,
    setup_logging,
)
from pyscripts.server_ops import DockerServer, build_server, checkout, current_branch
from pyscripts.stow_ops import RebuildLevel, StowManager
from pyscripts.tree_diff import make_diff_df

MAIN_BRANCH = "rankless-main"
MAIN_BRANCH = "bring-on"
PORT_A = 3038
PORT_B = 3039
MEMORY_LIMIT = "10g"
CPU_LIMIT = "4"
FINAL_STEP = "rankless_rs/src/gen/derive_links5.rs"


# ── per-branch preparation ────────────────────────────────────────────────────


def _image_tag(branch: str) -> str:
    return "rankless-branch-" + re.sub(r"[^a-z0-9]", "-", branch.lower())


def _container_name(branch: str) -> str:
    return _image_tag(branch)


def _prepare_branch(branch: str, rebuild: RebuildLevel, stow: StowManager) -> None:
    """Checkout, build binary/pipeline per rebuild level, stash if needed, build Docker image."""
    checkout(branch)
    match rebuild:
        case RebuildLevel.none:
            pass
        case RebuildLevel.binary:
            subprocess.run(["make", "clean-cache"], check=True)
            build_server()
        case RebuildLevel.pipeline:
            subprocess.run(["make", "-B", FINAL_STEP], check=True)
            build_server()
            stow.stash(branch)
        case RebuildLevel.full:
            subprocess.run(["make", "complete"], check=True)
            build_server()
            stow.stash(branch)

    if rebuild != RebuildLevel.none:
        DockerServer(
            container=_container_name(branch),
            image=_image_tag(branch),
            host_port=PORT_A,
            data_root=oa_root,
        ).build_image()


# ── comparison ────────────────────────────────────────────────────────────────


class BranchComparator:
    def __init__(self, url_a: str, url_b: str, min_citations: int = 1_000) -> None:
        self.url_a = url_a
        self.url_b = url_b
        requester = BatchRequester(min_citations=min_citations, addr=url_a)
        self.specs_dict = requester.specs
        self.sample_df = requester.urled_sample

    def iter_comparisons(self, e_per_bin: int = 4) -> Iterator[CompResult]:
        bins = [1_000, 5_000, 10_000, 30_000, 100_000, 200_000]
        df = (
            self.sample_df.assign(ccut=lambda df: pd.cut(df["citations"], bins))
            .loc[lambda df: df["ccut"].notna()]
            .groupby([RTC, "ccut"], observed=True)
            .apply(
                lambda gdf: gdf.sample(min(e_per_bin, len(gdf)), random_state=742),
                include_groups=False,
            )
            .reset_index()
        )
        for _, row in tqdm(list(df.iterrows())):
            rt: str = row[RTC]
            for tid, tree_spec in enumerate(self.specs_dict[rt]):
                bds = tree_spec["breakdowns"]
                bd_label = ";".join(
                    f"{b['attributeType']}-{'S' if b['sourceSide'] else 'T'}"
                    for b in bds
                )
                url_a = re.sub(r"tid=\d+", f"tid={tid}", row["url"])
                url_b = url_a.replace(self.url_a, self.url_b, 1)
                ccount = int(row["citations"])
                logger.debug(
                    "comparing %s/%s tid=%d ccount=%d", rt, bd_label, tid, ccount
                )
                try:
                    resp_a = requests.get(url_a, timeout=120)
                    resp_b = requests.get(url_b, timeout=120)
                    resp_a.raise_for_status()
                    resp_b.raise_for_status()
                    json_a = resp_a.json()
                    json_b = resp_b.json()
                    logger.debug(
                        "  time_a=%.3fs time_b=%.3fs nodes_a=%d nodes_b=%d",
                        resp_a.elapsed.total_seconds(),
                        resp_b.elapsed.total_seconds(),
                        len(json_a.get("tree", {}).get("children", {})),
                        len(json_b.get("tree", {}).get("children", {})),
                    )
                    yield CompResult(
                        root_type=rt,
                        bd_label=bd_label,
                        citation_count=ccount,
                        time_a=resp_a.elapsed.total_seconds(),
                        time_b=resp_b.elapsed.total_seconds(),
                        diff_df=make_diff_df(
                            json_a["tree"]["children"],
                            "a",
                            json_b["tree"]["children"],
                            "b",
                        ),
                    )
                except Exception as e:
                    logger.warning("error for %s/%s tid=%d: %s", rt, bd_label, tid, e)
                    yield CompResult(
                        rt, bd_label, ccount, 0.0, 0.0, pd.DataFrame(), error=str(e)
                    )


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

        server_a = DockerServer(
            container=_container_name(branch_a),
            image=_image_tag(branch_a),
            host_port=PORT_A,
            data_root=stow.data_root_for(branch_a),
            memory=MEMORY_LIMIT,
            cpus=CPU_LIMIT,
        )
        server_b = DockerServer(
            container=_container_name(branch_b),
            image=_image_tag(branch_b),
            host_port=PORT_B,
            data_root=stow.data_root_for(branch_b),
            memory=MEMORY_LIMIT,
            cpus=CPU_LIMIT,
        )

        server_a.start()
        server_b.start()
        server_a.wait_ready()
        server_b.wait_ready()

        comparator = BranchComparator(url_a=server_a.base_url, url_b=server_b.base_url)
        mem_tracker = MemoryTracker(
            {server_a.container: label_a, server_b.container: label_b}
        )
        mem_tracker.start()
        results = list(comparator.iter_comparisons(e_per_bin))
        mem_tracker.stop()

        server_a.stop()
        server_b.stop()

    finally:
        if current_branch() != original_branch:
            checkout(original_branch)

    summary_df = build_summary_df(results)
    grouped_df = build_grouped_df(summary_df)
    totals = build_totals(results, summary_df)

    summary_df.to_csv(artifacts_dir / "summary.csv", index=False)
    grouped_df.to_csv(artifacts_dir / "grouped.csv", index=False)

    mem_stats = build_mem_stats(mem_tracker.samples) if mem_tracker else {}

    timing_plot = artifacts_dir / "timing_plot.png"
    accuracy_plot = artifacts_dir / "accuracy_plot.png"
    memory_plot = artifacts_dir / "memory_plot.png"
    plot_timing(results, label_a, label_b, timing_plot)
    plot_accuracy(grouped_df, label_a, label_b, accuracy_plot)
    if mem_tracker:
        plot_memory(mem_tracker.samples, memory_plot)
    plot_paths = [p for p in [timing_plot, accuracy_plot, memory_plot] if p.exists()]

    print_report(grouped_df, totals, label_a, label_b)
    save_markdown(
        grouped_df,
        totals,
        label_a,
        label_b,
        artifacts_dir / "report.md",
        plot_paths,
        mem_stats=mem_stats,
    )
    html_path = artifacts_dir / "report.html"
    save_html(
        grouped_df,
        totals,
        label_a,
        label_b,
        html_path,
        plot_paths,
        mem_stats=mem_stats,
    )
    open_report(html_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare two Rankless git branches")
    parser.add_argument("--branch-a", default=None, help="Branch A (default: current)")
    parser.add_argument(
        "--branch-b", default=MAIN_BRANCH, help=f"Branch B (default: {MAIN_BRANCH})"
    )
    rvals = [r.value for r in RebuildLevel]
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
    args = parser.parse_args()

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
