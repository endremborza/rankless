"""Flask/PostgreSQL vs Rust server comparison.

Runs both containers (docker-compose in sql-yardstick/), queries the same
entities via both backends, and evaluates correctness and timing.

Usage:
    python -m pyscripts.sql_comparison_eval

Artifacts are written to docs/comparison-artifacts/sql-{timestamp}/.
"""

import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from ccl_science_data.common import EntC, load_map
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(override=True)

from pyscripts.cache_prompting import RTC, BatchRequester, get_specs_and_ys
from pyscripts.comparison_report import (
    ARTIFACTS_ROOT,
    CompResult,
    MemoryTracker,
    build_grouped_df,
    build_mem_stats,
    build_summary_df,
    build_totals,
    logger,
    plot_accuracy,
    plot_memory,
    plot_timing,
    print_report,
    save_html,
    save_markdown,
    setup_logging,
)
from pyscripts.tree_diff import make_diff_df

FLASK_URL = "http://localhost:5000/impact-tree"
RUST_URL = "http://localhost:3038"

RUST_CONTAINER = "rankless-rust"
PG_PYTHON_CONTAINER = "rankless-pg-python"
CONTAINER_LABELS = {RUST_CONTAINER: "rs", PG_PYTHON_CONTAINER: "flask"}

SUPPORTED_ETYPES = {
    EntC.AUTHORS,
    EntC.INSTITUTIONS,
    EntC.COUNTRIES,
    EntC.SOURCES,
    EntC.SUBFIELDS,
    EntC.TOPICS,
    EntC.WORKS,
}


# ── OA → DM ID mapping ────────────────────────────────────────────────────────


def _id_to_cc(val: int) -> str:
    chars = []
    while val > 0:
        chars.append(chr(val & 0xFF))
        val >>= 8
    return "".join(chars)


def build_oa_to_dm_maps() -> dict[str, dict[str, str]]:
    maps: dict[str, dict[str, str]] = {}
    for ent in SUPPORTED_ETYPES:
        if ent == EntC.COUNTRIES:
            raw = load_map(ent)
            maps[ent] = {
                _id_to_cc(int(k)): str(v) for k, v in raw.items() if _id_to_cc(int(k))
            }
        else:
            maps[ent] = {str(k): str(v) for k, v in load_map(ent).items()}
    return maps


def translate_tree(
    children: dict, breakdowns: list[dict], maps: dict, depth: int = 0
) -> dict:
    if depth >= len(breakdowns):
        return children
    etype = breakdowns[depth]["attributeType"]
    oa_to_dm = maps.get(etype, {})
    translated = {}
    for k, v in children.items():
        dm_key = oa_to_dm.get(str(k), str(k))
        new_v = dict(v)
        if "children" in new_v:
            new_v["children"] = translate_tree(new_v["children"], breakdowns, maps, depth + 1)
        translated[dm_key] = new_v
    return translated


# ── comparison ────────────────────────────────────────────────────────────────


class ReproEvaluator:
    def __init__(self) -> None:
        self.specs, _ = get_specs_and_ys(RUST_URL)
        self.oa_dm_maps = build_oa_to_dm_maps()

    def iter_comparisons(self, df_to_comp: pd.DataFrame):
        for _, row in tqdm(list(df_to_comp.iterrows())):
            root_type: str = row[RTC]
            for tid, tree_spec in enumerate(self.specs[root_type]):
                bds = tree_spec["breakdowns"]
                bd_etypes = [b["attributeType"] for b in bds]
                if not all(et in SUPPORTED_ETYPES for et in bd_etypes):
                    continue
                bd_label = ";".join(
                    f"{b['attributeType']}-{'S' if b['sourceSide'] else 'T'}" for b in bds
                )
                flask_bds = [
                    {"node": b["attributeType"], "sourceSide": b["sourceSide"]} for b in bds
                ]
                root_id = (
                    _id_to_cc(int(row["oa_id"]))
                    if root_type == EntC.COUNTRIES
                    else row["oa_id"]
                )
                payload = {
                    "root_type": root_type,
                    "root_id": root_id,
                    "breakdowns": flask_bds,
                }
                ccount: int = row["citations"]
                url = re.sub(r"tid=\d", f"tid={tid}", row["url"])
                logger.debug("comparing %s/%s tid=%d ccount=%d", root_type, bd_label, tid, ccount)

                try:
                    flask_resp = requests.post(FLASK_URL, json=payload)
                    flask_resp.raise_for_status()
                    rs_resp = requests.get(url)
                    rs_resp.raise_for_status()
                    flask_json = flask_resp.json()
                    flask_json["children"] = translate_tree(
                        flask_json["children"], bds, self.oa_dm_maps
                    )
                    rs_json = rs_resp.json()
                    logger.debug(
                        "  flask=%.3fs rs=%.3fs",
                        flask_resp.elapsed.total_seconds(),
                        rs_resp.elapsed.total_seconds(),
                    )
                    yield CompResult(
                        root_type=root_type,
                        bd_label=bd_label,
                        citation_count=ccount,
                        time_a=flask_resp.elapsed.total_seconds(),
                        time_b=rs_resp.elapsed.total_seconds(),
                        diff_df=make_diff_df(
                            flask_json["children"], "a",
                            rs_json["tree"]["children"], "b",
                        ),
                    )
                except Exception as e:
                    logger.warning("error for %s/%s tid=%d: %s", root_type, bd_label, tid, e)
                    yield CompResult(
                        root_type, bd_label, ccount, 0.0, 0.0, pd.DataFrame(), error=str(e)
                    )


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ts = datetime.now().strftime("%Y-%m-%d-%H-%M")
    artifacts_dir = ARTIFACTS_ROOT / f"{ts}-sql-vs-rust"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(artifacts_dir / "comparison.log")
    logger.info("SQL (Flask/PG) vs Rust comparison")

    bins = [5_000, 10_000, 30_000, 100_000, 200_000]
    e_per_g = 4
    sample_df = BatchRequester(min_citations=bins[0], addr=RUST_URL).urled_sample
    decorated_df = (
        pd.concat(
            pd.DataFrame(
                [{"dmId": v, "oa_id": k2} for k2, v in load_map(k).items()]
            ).assign(**{RTC: k})
            for k in sample_df[RTC].unique()
        )
        .merge(sample_df)
        .assign(ccut=lambda df: pd.cut(df["citations"], bins))
        .loc[lambda df: df["ccut"].notna()]
        .groupby([RTC, "ccut"], observed=True)
        .apply(
            lambda gdf: gdf.sample(min(e_per_g, len(gdf)), random_state=742),
            include_groups=False,
        )
        .reset_index()
        .drop_duplicates([RTC, "oa_id"])
    )

    mem_tracker = MemoryTracker(CONTAINER_LABELS)
    mem_tracker.start()
    results = list(ReproEvaluator().iter_comparisons(decorated_df))
    mem_tracker.stop()
    mem_stats = build_mem_stats(mem_tracker.samples)

    summary_df = build_summary_df(results)
    grouped_df = build_grouped_df(summary_df)
    totals = build_totals(results, summary_df)

    summary_df.to_csv(artifacts_dir / "summary.csv", index=False)
    grouped_df.to_csv(artifacts_dir / "grouped.csv", index=False)

    timing_plot = artifacts_dir / "timing_plot.png"
    accuracy_plot = artifacts_dir / "accuracy_plot.png"
    memory_plot = artifacts_dir / "memory_plot.png"
    plot_timing(results, "flask", "rs", timing_plot)
    plot_accuracy(grouped_df, "flask", "rs", accuracy_plot)
    plot_memory(mem_tracker.samples, memory_plot)
    plot_paths = [p for p in [timing_plot, accuracy_plot, memory_plot] if p.exists()]

    print_report(grouped_df, totals, "flask", "rs")
    save_markdown(
        grouped_df, totals, "flask", "rs", artifacts_dir / "report.md", plot_paths,
        mem_stats=mem_stats,
    )
    save_html(
        grouped_df, totals, "flask", "rs", artifacts_dir / "report.html", plot_paths,
        mem_stats=mem_stats,
    )
