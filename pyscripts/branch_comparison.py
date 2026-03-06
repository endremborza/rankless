"""Branch-to-branch comparison of Rankless server outputs.

Runs two Docker containers — one per branch — on different ports, then
evaluates correctness (structural tree diff) and timing against the same
query set. Mirrors the sql_comparison_eval.py approach.

Usage:
    python -m pyscripts.branch_comparison [options]

Options:
    --branch-a BRANCH    Branch A (default: current branch)
    --branch-b BRANCH    Branch B (default: rankless-main)
    --rebuild-a LEVEL      none | binary | pipeline | full  (default: binary)
    --rebuild-b LEVEL      none | binary | pipeline | full  (default: binary)
    --samples N          Entities per citation-count bin (default: 4)
    --dump-root PATH     Output directory (default: /tmp/rankless-branch-cmp)

See docs/comparisons-and-benchmarking.md for full explanation.
"""

import argparse
import datetime as dt
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import pandas as pd
import requests
from ccl_science_data.common import oa_root
from tqdm import tqdm

from pyscripts.cache_prompting import BatchRequester, RTC, get_specs_and_ys
from pyscripts.server_ops import DockerServer, build_server, checkout, current_branch
from pyscripts.stow_ops import RebuildLevel, StowManager
from pyscripts.tree_diff import METRICS, make_diff_df, metric_stats, top_source_stats

DUMP_ROOT = Path("/tmp/rankless-branch-cmp")
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
            pass  # reuse existing Docker image; no build
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
            host_port=PORT_A,  # port irrelevant for image build
            data_root=oa_root,
        ).build_image()


# ── comparison ────────────────────────────────────────────────────────────────


@dataclass
class CompResult:
    root_type: str
    bd_label: str
    citation_count: int
    time_a: float
    time_b: float
    diff_df: pd.DataFrame
    error: str | None = None


class BranchComparator:
    def __init__(self, url_a: str, url_b: str, min_citations: int = 1_000) -> None:
        self.url_a = url_a
        self.url_b = url_b
        self.specs_dict, _ = get_specs_and_ys(url_a)
        self.sample_df = BatchRequester(
            min_citations=min_citations, addr=url_a
        ).urled_sample

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
                # derive URL for this tid, then swap base for branch B
                url_a = re.sub(r"tid=\d+", f"tid={tid}", row["url"])
                url_b = url_a.replace(self.url_a, self.url_b, 1)
                ccount = int(row["citations"])
                try:
                    resp_a = requests.get(url_a, timeout=120)
                    resp_b = requests.get(url_b, timeout=120)
                    resp_a.raise_for_status()
                    resp_b.raise_for_status()
                    json_a = resp_a.json()
                    json_b = resp_b.json()
                    diff = make_diff_df(
                        json_a["tree"]["children"],
                        "a",
                        json_b["tree"]["children"],
                        "b",
                    )
                    yield CompResult(
                        root_type=rt,
                        bd_label=bd_label,
                        citation_count=ccount,
                        time_a=resp_a.elapsed.total_seconds(),
                        time_b=resp_b.elapsed.total_seconds(),
                        diff_df=diff,
                    )
                except Exception as e:
                    yield CompResult(
                        rt, bd_label, ccount, 0.0, 0.0, pd.DataFrame(), error=str(e)
                    )


# ── analysis ──────────────────────────────────────────────────────────────────


def build_summary_df(results: list[CompResult]) -> pd.DataFrame:
    rows = []
    for cr in results:
        if cr.error:
            continue
        lc = metric_stats(cr.diff_df, METRICS[0], "a", "b")
        sc = metric_stats(cr.diff_df, METRICS[1], "a", "b")
        if lc is None or sc is None:
            continue
        ts = top_source_stats(cr.diff_df, "a", "b")
        rows.append(
            {
                "root_type": cr.root_type,
                "bd_label": cr.bd_label,
                "time_a": cr.time_a,
                "time_b": cr.time_b,
                "pearson_lc": lc["pearson"],
                "pearson_sc": sc["pearson"],
                "relerr_lc": lc["relerr"],
                "relerr_sc": sc["relerr"],
                "n_missing": lc["n_missing"],
                "ts_id_match": ts["id_match_rate"],
                "ts_link_relerr": ts["link_relerr"],
            }
        )
    return pd.DataFrame(rows)


def build_grouped_df(summary_df: pd.DataFrame) -> pd.DataFrame:
    return (
        summary_df.groupby(["root_type", "bd_label"])
        .agg(
            n=("time_a", "count"),
            time_a=("time_a", "sum"),
            time_b=("time_b", "sum"),
            pearson_lc=("pearson_lc", "mean"),
            pearson_sc=("pearson_sc", "mean"),
            relerr_lc=("relerr_lc", "mean"),
            relerr_sc=("relerr_sc", "mean"),
            n_missing=("n_missing", "sum"),
            ts_id_match=("ts_id_match", "mean"),
            ts_link_relerr=("ts_link_relerr", "mean"),
        )
        .reset_index()
        .assign(time_rate=lambda df: df["time_a"] / df["time_b"])
        .sort_values("relerr_sc")
    )


def build_totals(results: list[CompResult], summary_df: pd.DataFrame) -> dict:
    time_a, time_b = (float(summary_df[k].sum()) for k in ["time_a", "time_b"])
    return {
        "n_comparisons": len(summary_df),
        "n_errors": sum(1 for r in results if r.error),
        "total_time_a": time_a,
        "total_time_b": time_b,
        "time_ratio_a_over_b": time_a / time_b if time_b else float("nan"),
        "mean_pearson_lc": float(summary_df["pearson_lc"].mean()),
        "mean_pearson_sc": float(summary_df["pearson_sc"].mean()),
        "mean_relerr_lc": float(summary_df["relerr_lc"].mean()),
        "mean_relerr_sc": float(summary_df["relerr_sc"].mean()),
        "total_n_missing": int(summary_df["n_missing"].sum()),
        "mean_ts_id_match": float(summary_df["ts_id_match"].mean()),
        "mean_ts_link_relerr": float(summary_df["ts_link_relerr"].mean()),
    }


# ── reporting ─────────────────────────────────────────────────────────────────


def print_report(
    grouped_df: pd.DataFrame, totals: dict, branch_a: str, branch_b: str
) -> None:
    print(f"\n{'=' * 80}")
    print(f"BY root_type × breakdown  |  A={branch_a}  B={branch_b}")
    print("=" * 80)
    cols = [
        "root_type",
        "bd_label",
        "n",
        "time_a",
        "time_b",
        "time_rate",
        "pearson_lc",
        "pearson_sc",
        "relerr_lc",
        "relerr_sc",
        "n_missing",
        "ts_id_match",
        "ts_link_relerr",
    ]
    fmt = {
        "time_a": "{:.1f}".format,
        "time_b": "{:.1f}".format,
        "time_rate": "{:.2f}".format,
        "pearson_lc": "{:.3f}".format,
        "pearson_sc": "{:.3f}".format,
        "relerr_lc": "{:.1%}".format,
        "relerr_sc": "{:.1%}".format,
        "ts_id_match": "{:.1%}".format,
        "ts_link_relerr": "{:.1%}".format,
    }
    with pd.option_context("display.max_rows", 100, "display.max_colwidth", 60):
        print(grouped_df[cols].to_string(index=False, formatters=fmt))

    print(f"\n{'=' * 80}\nTOTALS\n{'=' * 80}")
    for k, v in totals.items():
        if not isinstance(v, float):
            print(f"  {k}: {v}")
        elif "time" in k and "ratio" not in k:
            print(f"  {k}: {v:.1f}s")
        elif "pearson" in k:
            print(f"  {k}: {v:.3f}")
        elif "match" in k or "relerr" in k:
            print(f"  {k}: {v:.1%}")
        else:
            print(f"  {k}: {v:.2f}")


def save_report(
    dump_root: Path,
    branch_a: str,
    branch_b: str,
    grouped_df: pd.DataFrame,
    totals: dict,
) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Branch Comparison Report",
        "",
        f"**{ts}** | A=`{branch_a}` vs B=`{branch_b}`",
        "",
        "Time ratio = A / B (>1 means A is slower).",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
    ]
    for k, v in totals.items():
        if not isinstance(v, float):
            lines.append(f"| {k} | {v} |")
        elif "time" in k and "ratio" not in k:
            lines.append(f"| {k} | {v:.1f}s |")
        elif "pearson" in k:
            lines.append(f"| {k} | {v:.3f} |")
        elif "match" in k or "relerr" in k:
            lines.append(f"| {k} | {v:.1%} |")
        else:
            lines.append(f"| {k} | {v:.2f} |")

    cols = [
        ("root_type", "Root", None),
        ("bd_label", "Breakdown", None),
        ("n", "N", None),
        ("time_rate", "A/B time", lambda v: f"{v:.2f}x"),
        ("pearson_lc", "r(LC)", lambda v: f"{v:.3f}"),
        ("pearson_sc", "r(SC)", lambda v: f"{v:.3f}"),
        ("relerr_lc", "err(LC)", lambda v: f"{v:.1%}"),
        ("relerr_sc", "err(SC)", lambda v: f"{v:.1%}"),
        ("n_missing", "Miss", None),
        ("ts_id_match", "TopID%", lambda v: f"{v:.0%}"),
        ("ts_link_relerr", "TopLnkErr", lambda v: f"{v:.1%}"),
    ]
    header = "| " + " | ".join(c[1] for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    lines += ["", "## By root type × breakdown", "", header, sep]

    for _, row in grouped_df.iterrows():
        cells = []
        for key, _, fmt_fn in cols:
            val = row[key]
            if fmt_fn and pd.notna(val):
                cells.append(fmt_fn(val))
            elif pd.isna(val):
                cells.append("-")
            else:
                cells.append(str(val))
        lines.append("| " + " | ".join(cells) + " |")

    out = dump_root / "report.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"\nreport → {out}")


def run_comparison(
    branch_a: str,
    branch_b: str,
    rebuild_a: RebuildLevel,
    rebuild_b: RebuildLevel,
    e_per_bin: int,
    dump_root: Path,
) -> None:
    dump_root.mkdir(parents=True, exist_ok=True)
    stow = StowManager()
    original_branch = current_branch()

    try:
        # Build both branches sequentially
        for branch, rb in [(branch_a, rebuild_a), (branch_b, rebuild_b)]:
            _prepare_branch(branch, rb, stow)

        # Both images built; restore original branch before starting comparison
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

        comparator = BranchComparator(
            url_a=server_a.base_url,
            url_b=server_b.base_url,
        )
        results = list(comparator.iter_comparisons(e_per_bin))

        server_a.stop()
        server_b.stop()

    finally:
        if current_branch() != original_branch:
            checkout(original_branch)

    summary_df = build_summary_df(results)
    grouped_df = build_grouped_df(summary_df)
    totals = build_totals(results, summary_df)

    print_report(grouped_df, totals, branch_a, branch_b)
    summary_df.to_csv(dump_root / "summary.csv", index=False)
    grouped_df.to_csv(dump_root / "grouped.csv", index=False)
    save_report(dump_root, branch_a, branch_b, grouped_df, totals)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare two Rankless git branches")
    parser.add_argument("--branch-a", default=None, help="Branch A (default: current)")
    parser.add_argument(
        "--branch-b", default=MAIN_BRANCH, help=f"Branch B (default: {MAIN_BRANCH})"
    )
    rvals = [r.value for r in RebuildLevel]

    default_a = "pipeline"
    parser.add_argument(
        "--rebuild-a",
        default=default_a,
        choices=rvals,
        help=f"Rebuild branch A level (default: {default_a})",
    )
    default_b = "pipeline"
    parser.add_argument(
        "--rebuild-b",
        default=default_b,
        choices=rvals,
        help=f"Rebuild branch B level (default: {default_b})",
    )
    parser.add_argument(
        "--samples", type=int, default=4, help="Entities per citation-count bin"
    )
    parser.add_argument(
        "--dump-root", type=Path, default=DUMP_ROOT, help="Output directory"
    )
    args = parser.parse_args()

    ts = dt.datetime.now().strftime("%Y-%m-%d-%H-%M")
    run_comparison(
        branch_a=args.branch_a or current_branch(),
        branch_b=args.branch_b,
        rebuild_a=RebuildLevel(args.rebuild_a),
        rebuild_b=RebuildLevel(args.rebuild_b),
        e_per_bin=args.samples,
        dump_root=args.dump_root / ts,
    )
