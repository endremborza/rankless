import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

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


# ── tree / diff ───────────────────────────────────────────────────────────────


def _flatten(children: dict, prefix: tuple = ()) -> list[dict]:
    rows = []
    for k, v in children.items():
        path = (*prefix, k)
        if "children" in v:
            rows.extend(_flatten(v["children"], path))
        rows.append(
            {m: v.get(m, 0) for m in METRICS} | {"path": "-".join(map(str, path))}
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


def _metric_stats(df: pd.DataFrame, col: str) -> dict:
    """Stats on RS-present nodes (col > 0); symmetric rel error over all, pearson over matched."""
    rs_nodes = df.loc[df[col] > 0]
    flask_col = f"flask_{col}"
    matched = rs_nodes.loc[rs_nodes[flask_col] > 0]
    pearson = matched[col].corr(matched[flask_col]) if len(matched) >= 2 else np.nan
    mid = (rs_nodes[col] + rs_nodes[flask_col]) / 2.0
    relerr = (rs_nodes[col] - rs_nodes[flask_col]).abs() / mid.replace(0, np.nan)
    return {
        "pearson": float(pearson) if pd.notna(pearson) else None,
        "relerr": float(relerr.mean()) if len(relerr) > 0 else None,
        "n_missing": int((rs_nodes[flask_col] == 0).sum()),
    }


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
    def __init__(self, upper_bound: int = 20_000 * 4) -> None:
        self.br = BatchRequester(min_citations=1000, big_limit=upper_bound)
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
    for cr in (r for r in results if not r.error):
        lc = _metric_stats(cr.diff_df, "linkCount")
        sc = _metric_stats(cr.diff_df, "sourceCount")
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
    ]
    fmt = {
        "flask_time": "{:.1f}".format,
        "rs_time": "{:.1f}".format,
        "time_rate": "{:.1f}".format,
        "pearson_lc": "{:.3f}".format,
        "pearson_sc": "{:.3f}".format,
        "relerr_lc": "{:.1%}".format,
        "relerr_sc": "{:.1%}".format,
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
        else:
            print(f"  {k}: {v:.1f}")


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
    inst_oa_ids = [78577930]
    comper = ReproEvaluator()
    bins = [0, 10_000, 30_000, 100_000]
    labels = [1, 10, 30]
    e_per_g = 4
    sample_df = comper.br.urled_sample
    decorated_df = (
        pd.concat(
            pd.DataFrame(
                [{"dmId": v, "oa_id": k2} for k2, v in load_map(k).items()]
            ).assign(**{RTC: k})
            for k in sample_df[RTC].unique()
        )
        .merge(sample_df)
        .assign(ccut=lambda df: pd.cut(df["citations"], bins, labels=labels))
        .loc[lambda df: df["ccut"].notna()]
        .groupby([RTC, "ccut"], observed=True)
        .apply(lambda gdf: gdf.sample(min(e_per_g, len(gdf)), random_state=742))
        .drop_duplicates([RTC, "oa_id"])
    )

    results = list(comper.iter_comparisons(decorated_df))

    summary_df = build_summary_df(results)
    grouped_df = build_grouped_df(summary_df)
    totals = build_totals(results, summary_df)
    print_report(grouped_df, totals)
    save_snapshot(grouped_df, totals)
