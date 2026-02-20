import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(override=True)

import numpy as np
import pandas as pd
import requests
from ccl_science_data.common import EntC, load_map
from tqdm import tqdm

from pyscripts.cache_prompting import RTC, BatchRequester, get_specs_and_ys

FLASK_URL = "http://localhost:5000/impact-tree"
SNAPSHOT_PATH = Path(__file__).parent / "eval-snapshot.json"
PLOT_PATH = Path(__file__).parent / "timing-plot.png"
METRICS = ["linkCount", "sourceCount"]
SUPPORTED_ETYPES = {
    EntC.AUTHORS,
    EntC.INSTITUTIONS,
    EntC.COUNTRIES,
    EntC.SOURCES,
    EntC.SUBFIELDS,
    EntC.TOPICS,
    EntC.WORKS,
}
RELERR_MAX = 0.05


# ── tree / diff ───────────────────────────────────────────────────────────────


def _flatten(children: dict, prefix: tuple = ()) -> list[dict]:
    rows = []
    for k, v in children.items():
        path = (*prefix, k)
        if "children" in v:
            rows.extend(_flatten(v["children"], path))
        rows.append(
            {m: v.get(m, 0) for m in METRICS}
            | {"path": "-".join(map(str, path))}
            | {"topSourceId": v.get("topSourceId"), "topSourceLinks": v.get("topSourceLinks", 0)}
        )
    return rows


def make_diff_df(flask_dic: dict, rs_dic: dict) -> pd.DataFrame:
    flask_df = (
        pd.DataFrame(_flatten(flask_dic["children"]))
        .set_index("path")
        .add_prefix("flask_")
    )
    rs_rows = _flatten(rs_dic["tree"]["children"])
    rs_df = (
        pd.DataFrame(rs_rows).set_index("path")
        if rs_rows
        else pd.DataFrame(columns=METRICS, index=pd.Index([], name="path"))
    )
    return flask_df.join(rs_df, how="outer").fillna(0)


# ── metrics ───────────────────────────────────────────────────────────────────


def _metric_stats(df: pd.DataFrame, col: str) -> dict | None:
    """Stats on RS-present nodes (col > 0); symmetric rel error over all, pearson over matched."""
    rs_nodes = df.loc[df[col] > 0]
    flask_col = f"flask_{col}"
    matched = rs_nodes.loc[rs_nodes[flask_col] > 0]
    pearson = matched[col].corr(matched[flask_col]) if len(matched) >= 2 else np.nan
    mid = (rs_nodes[col] + rs_nodes[flask_col]) / 2.0
    relerr = (rs_nodes[col] - rs_nodes[flask_col]).abs() / mid.replace(0, np.nan)
    if relerr.mean() > RELERR_MAX:
        return None
    return {
        "pearson": float(pearson) if pd.notna(pearson) else None,
        "relerr": float(relerr.mean()) if len(relerr) > 0 else None,
        "n_missing": int((rs_nodes[flask_col] == 0).sum()),
    }


def _top_source_stats(df: pd.DataFrame) -> dict:
    """Match rate of topSourceId and rel error of topSourceLinks on nodes present on both sides."""
    both = df.loc[(df["topSourceLinks"] > 0) & (df["flask_topSourceLinks"] > 0)]
    if both.empty:
        return {"id_match_rate": None, "link_relerr": None}
    id_match_rate = float((both["topSourceId"] == both["flask_topSourceId"]).mean())
    mid = (both["topSourceLinks"] + both["flask_topSourceLinks"]) / 2.0
    link_relerr = float(
        ((both["topSourceLinks"] - both["flask_topSourceLinks"]).abs() / mid.replace(0, np.nan)).mean()
    )
    return {"id_match_rate": id_match_rate, "link_relerr": link_relerr}


# ── data model ────────────────────────────────────────────────────────────────


@dataclass
class CompResult:
    root_type: str
    bd_label: str
    citation_count: int
    flask_time: float
    rs_time: float
    diff_df: pd.DataFrame
    error: str | None = None


# ── fetching ──────────────────────────────────────────────────────────────────


class ReproEvaluator:
    def __init__(self) -> None:
        self.specs, _ = get_specs_and_ys()

    def iter_comparisons(self, df_to_comp: pd.DataFrame):

        for _, row in tqdm(list(df_to_comp.iterrows())):
            root_type: str = row[RTC]
            for tid, tree_spec in enumerate(self.specs[root_type]):
                bds = tree_spec["breakdowns"]
                bd_etypes = [b["attributeType"] for b in bds]
                if not all(et in SUPPORTED_ETYPES for et in bd_etypes):
                    continue
                bd_label = ";".join(
                    f'{b["attributeType"]}-{"S" if b["sourceSide"] else "T"}'
                    for b in bds
                )
                flask_bds = [
                    {"node": b["attributeType"], "sourceSide": b["sourceSide"]}
                    for b in bds
                ]
                payload = {
                    "root_type": root_type,
                    "root_id": row["oa_id"],
                    "breakdowns": flask_bds,
                }
                ccount: int = row["citations"]
                url = re.sub(r"tid=\d", f"tid={tid}", row["url"])

                try:
                    flask_resp = requests.post(FLASK_URL, json=payload)
                    flask_resp.raise_for_status()
                    rs_resp = requests.get(url)
                    yield CompResult(
                        root_type=root_type,
                        bd_label=bd_label,
                        citation_count=ccount,
                        flask_time=flask_resp.elapsed.total_seconds(),
                        rs_time=rs_resp.elapsed.total_seconds(),
                        diff_df=make_diff_df(flask_resp.json(), rs_resp.json()),
                    )
                except Exception as e:
                    yield CompResult(
                        root_type,
                        bd_label,
                        ccount,
                        0.0,
                        0.0,
                        pd.DataFrame(),
                        error=str(e),
                    )


# ── analysis ──────────────────────────────────────────────────────────────────


def build_summary_df(results: list[CompResult]) -> pd.DataFrame:
    rows = []
    for cr in results:
        if cr.error:
            continue
        lc = _metric_stats(cr.diff_df, METRICS[0])
        sc = _metric_stats(cr.diff_df, METRICS[1])
        if lc is None or sc is None:
            continue
        ts = _top_source_stats(cr.diff_df)
        rows.append(
            {
                "root_type": cr.root_type,
                "bd_label": cr.bd_label,
                "flask_time": cr.flask_time,
                "rs_time": cr.rs_time,
                "pearson_lc": lc["pearson"],
                "pearson_sc": sc["pearson"],
                "relerr_lc": lc["relerr"],
                "relerr_sc": sc["relerr"],
                "n_missing": lc["n_missing"],
                "ts_id_match_rate": ts["id_match_rate"],
                "ts_link_relerr": ts["link_relerr"],
            }
        )
    return pd.DataFrame(rows)


def build_grouped_df(summary_df: pd.DataFrame) -> pd.DataFrame:
    return (
        summary_df.groupby(["root_type", "bd_label"])
        .agg(
            n=("flask_time", "count"),
            flask_time=("flask_time", "sum"),
            rs_time=("rs_time", "sum"),
            pearson_lc=("pearson_lc", "mean"),
            pearson_sc=("pearson_sc", "mean"),
            relerr_lc=("relerr_lc", "mean"),
            relerr_sc=("relerr_sc", "mean"),
            n_missing=("n_missing", "sum"),
            ts_id_match_rate=("ts_id_match_rate", "mean"),
            ts_link_relerr=("ts_link_relerr", "mean"),
        )
        .reset_index()
        .assign(
            time_rate=lambda df: df["flask_time"] / df["rs_time"],
        )
        .sort_values("relerr_sc")
    )


def build_totals(results: list[CompResult], summary_df: pd.DataFrame) -> dict:
    rs_time, flask_time = (
        float(summary_df[k].sum()) for k in ["rs_time", "flask_time"]
    )
    return {
        "n_comparisons": len(summary_df),
        "n_errors": sum(1 for r in results if r.error),
        "total_flask_time": flask_time,
        "total_rs_time": rs_time,
        "total_duration_ratio": flask_time / rs_time,
        "mean_pearson_lc": float(summary_df["pearson_lc"].mean()),
        "mean_pearson_sc": float(summary_df["pearson_sc"].mean()),
        "mean_relerr_lc": float(summary_df["relerr_lc"].mean()),
        "mean_relerr_sc": float(summary_df["relerr_sc"].mean()),
        "total_n_missing": int(summary_df["n_missing"].sum()),
        "mean_ts_id_match_rate": float(summary_df["ts_id_match_rate"].mean()),
        "mean_ts_link_relerr": float(summary_df["ts_link_relerr"].mean()),
    }


# ── reporting ─────────────────────────────────────────────────────────────────


def print_report(grouped_df: pd.DataFrame, totals: dict) -> None:
    print("\n" + "=" * 80)
    print("BY root_type × breakdown")
    print("=" * 80)
    display_cols = [
        "root_type",
        "bd_label",
        "n",
        "flask_time",
        "rs_time",
        "time_rate",
        "pearson_lc",
        "pearson_sc",
        "relerr_lc",
        "relerr_sc",
        "n_missing",
        "ts_id_match_rate",
        "ts_link_relerr",
    ]
    fmt = {
        "flask_time": "{:.1f}".format,
        "rs_time": "{:.1f}".format,
        "time_rate": "{:.1f}".format,
        "pearson_lc": "{:.3f}".format,
        "pearson_sc": "{:.3f}".format,
        "relerr_lc": "{:.1%}".format,
        "relerr_sc": "{:.1%}".format,
        "ts_id_match_rate": "{:.1%}".format,
        "ts_link_relerr": "{:.1%}".format,
    }
    with pd.option_context("display.max_rows", 100, "display.max_colwidth", 60):
        print(grouped_df[display_cols].to_string(index=False, formatters=fmt))

    print("\n" + "=" * 80)
    print("TOTALS")
    print("=" * 80)
    for k, v in totals.items():
        if not isinstance(v, float):
            print(f"  {k}: {v}")
        elif "time" in k:
            print(f"  {k}: {v:.1f}s")
        elif "pearson" in k:
            print(f"  {k}: {v:.3f}")
        elif "match_rate" in k or "relerr" in k:
            print(f"  {k}: {v:.1%}")
        else:
            print(f"  {k}: {v:.1f}")


def plot_timing(results: list[CompResult], out_path: Path) -> None:
    rows = []
    for r in results:
        if (
            r.error
            or r.flask_time <= 0
            or r.rs_time <= 0
            or _metric_stats(r.diff_df, METRICS[0]) is None
        ):
            continue
        bd_depth = len(r.bd_label.split(";"))
        for backend, t in [("flask", r.flask_time), ("rust", r.rs_time)]:
            rows.append(
                {
                    "backend": backend,
                    "bd_depth": bd_depth,
                    "citations": r.citation_count,
                    "time": t,
                }
            )

    df = pd.DataFrame(rows).assign(
        log_citations=lambda df: np.log2(df["citations"]),
        log_time=lambda df: np.log2(df["time"]),
    )

    palette = {"flask": "#4c78a8", "rust": "#e45756"}
    depth_order = sorted(df["bd_depth"].unique())
    g = sns.lmplot(
        data=df,
        x="log_citations",
        y="log_time",
        hue="backend",
        col="bd_depth",
        col_order=depth_order,
        palette=palette,
        markers=["o", "s"],
        scatter_kws={"alpha": 0.55, "s": 30},
        line_kws={"linewidth": 1.5},
        height=4,
        aspect=0.85,
    )

    g.set_axis_labels("Entity citation count (log₂)", "Response time, s (log₂)")
    g.set_titles("Breakdown depth: {col_name}")
    g.figure.suptitle(
        "Flask (PostgreSQL) vs Rust backend: response time scaling",
        y=1.03,
        fontsize=12,
    )
    g.tight_layout()
    g.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\ntiming plot → {out_path}")


# ── snapshot ──────────────────────────────────────────────────────────────────


def save_snapshot(grouped_df: pd.DataFrame, totals: dict) -> None:
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "grouped": grouped_df.to_dict(orient="records"),
        "totals": totals,
    }
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2))
    print(f"\nsnapshot saved → {SNAPSHOT_PATH}")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # inst_oa_ids = [78577930]
    comper = ReproEvaluator()
    bins = [5_000, 10_000, 30_000, 100_000, 200_000][:2]
    e_per_g = 2
    sample_df = BatchRequester(min_citations=bins[0]).urled_sample
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

    results = list(comper.iter_comparisons(decorated_df))

    summary_df = build_summary_df(results)
    grouped_df = build_grouped_df(summary_df)
    totals = build_totals(results, summary_df)
    print_report(grouped_df, totals)
    save_snapshot(grouped_df, totals)
    plot_timing(results, PLOT_PATH)
