"""Shared orchestration for the SQL-vs-Rust and branch-vs-branch comparisons.

Both compare two backends over the same sampled query set, diff the breakdown
trees, and emit an identical artifact set. This module owns the three stages
they share — backend preparation (rebuild dispatch), the sample → query → diff
loop, and the artifact/report tail — so each comparison only has to define its
backend pair and how a single (A, B) response pair is fetched.
"""

import subprocess
from pathlib import Path
from typing import Callable, Iterator, Optional

import pandas as pd
from tqdm import tqdm

from pyscripts import poster_figures
from pyscripts.cache_prompting import RTC
from pyscripts.comparison_report import (
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
    save_mem_samples,
)
from pyscripts.server_ops import DockerServer, build_server
from pyscripts.stow_ops import RebuildLevel, StowManager
from pyscripts.tree_diff import make_diff_df

FINAL_STEP = "rankless_rs/src/gen/derive_links5.rs"

# fetch_pair(row, tid, breakdowns) -> (children_a, children_b, time_a, time_b)
FetchPair = Callable[[pd.Series, int, list], tuple[dict, dict, float, float]]


def prepare_backend(
    level: RebuildLevel,
    server: DockerServer,
    *,
    stow: Optional[StowManager] = None,
    stash_label: Optional[str] = None,
) -> None:
    """Rebuild to the requested level, then (re)build the Docker image.

    ``binary`` clears the cache and rebuilds the server; ``pipeline`` reruns the
    pipeline to its final step; ``full`` rebuilds from the CSVs. When ``stow`` +
    ``stash_label`` are given (branch comparison), the rebuilt data root is
    stashed so the container can mount it.
    """
    if level == RebuildLevel.none:
        return
    match level:
        case RebuildLevel.binary:
            subprocess.run(["make", "clean-cache"], check=True)
            build_server()
        case RebuildLevel.pipeline:
            subprocess.run(["make", "-B", FINAL_STEP], check=True)
            build_server()
        case RebuildLevel.full:
            subprocess.run(["make", "build-data"], check=True)
            build_server()
    if stow is not None and stash_label is not None and level != RebuildLevel.binary:
        stow.stash(stash_label)
    server.build_image()


def sample_entities(
    sample_df: pd.DataFrame, bins: list[int], e_per_bin: int, random_state: int = 742
) -> pd.DataFrame:
    """Stratified sample of up to ``e_per_bin`` entities per (root_type, bin)."""
    return (
        sample_df.assign(ccut=lambda df: pd.cut(df["citations"], bins))
        .loc[lambda df: df["ccut"].notna()]
        .groupby([RTC, "ccut"], observed=True)
        .apply(
            lambda gdf: gdf.sample(min(e_per_bin, len(gdf)), random_state=random_state),
            include_groups=False,
        )
        .reset_index()
    )


def run_query_loop(
    sample_df: pd.DataFrame,
    specs: dict,
    fetch_pair: FetchPair,
    *,
    bd_filter: Optional[Callable[[list], bool]] = None,
) -> Iterator[CompResult]:
    """For each sampled entity × applicable tree spec, fetch both backends and diff."""
    for _, row in tqdm(list(sample_df.iterrows())):
        rt: str = row[RTC]
        for tid, tree_spec in enumerate(specs[rt]):
            bds = tree_spec["breakdowns"]
            if bd_filter is not None and not bd_filter(bds):
                continue
            bd_label = ";".join(
                f"{b['attributeType']}-{'S' if b['sourceSide'] else 'T'}" for b in bds
            )
            ccount = int(row["citations"])
            logger.debug("comparing %s/%s tid=%d ccount=%d", rt, bd_label, tid, ccount)
            try:
                children_a, children_b, time_a, time_b = fetch_pair(row, tid, bds)
                yield CompResult(
                    root_type=rt,
                    bd_label=bd_label,
                    citation_count=ccount,
                    time_a=time_a,
                    time_b=time_b,
                    diff_df=make_diff_df(children_a, "a", children_b, "b"),
                )
            except Exception as e:
                logger.warning("error for %s/%s tid=%d: %s", rt, bd_label, tid, e)
                yield CompResult(
                    rt, bd_label, ccount, 0.0, 0.0, pd.DataFrame(), error=str(e)
                )


def write_artifacts(
    results: list[CompResult],
    label_a: str,
    label_b: str,
    artifacts_dir: Path,
    *,
    mem_tracker: Optional[MemoryTracker] = None,
    mem_colors: Optional[dict[str, str]] = None,
    save_mem_csv: bool = False,
    poster: bool = False,
) -> None:
    """Write the shared artifact set: CSVs, plots, markdown + HTML report."""
    summary_df = build_summary_df(results)
    grouped_df = build_grouped_df(summary_df)
    totals = build_totals(results, summary_df)

    summary_df.to_csv(artifacts_dir / "summary.csv", index=False)
    grouped_df.to_csv(artifacts_dir / "grouped.csv", index=False)

    mem_stats = build_mem_stats(mem_tracker.samples) if mem_tracker else {}
    if mem_tracker and save_mem_csv:
        save_mem_samples(mem_tracker.samples, artifacts_dir / "memory_samples.csv")

    timing_plot = artifacts_dir / "timing_plot.png"
    accuracy_plot = artifacts_dir / "accuracy_plot.png"
    memory_plot = artifacts_dir / "memory_plot.png"
    plot_timing(results, label_a, label_b, timing_plot)
    plot_accuracy(grouped_df, label_a, label_b, accuracy_plot)
    if mem_tracker:
        plot_memory(mem_tracker.samples, memory_plot, colors=mem_colors)
    plot_paths = [p for p in [timing_plot, accuracy_plot, memory_plot] if p.exists()]

    if poster:
        for p in poster_figures.generate_from_artifacts(artifacts_dir):
            logger.info("poster figure → %s", p)

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
