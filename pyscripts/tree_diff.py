"""Shared tree response diffing and structural metrics.

Used by sql_comparison_eval.py (Rust vs Flask/PG) and
branch_comparison.py (Rust branch A vs Rust branch B).

`make_diff_df` produces a DataFrame with columns prefixed by the caller-supplied
labels; `metric_stats` and `top_source_stats` then use those same labels.

Example (SQL comparison):
    diff = make_diff_df(flask_json["children"], "flask", rs_json["tree"]["children"], "rs")
    lc   = metric_stats(diff, "linkCount", "rs", "flask")

Example (branch comparison):
    diff = make_diff_df(resp_a["tree"]["children"], "a", resp_b["tree"]["children"], "b")
    lc   = metric_stats(diff, "linkCount", "a", "b")
"""

import numpy as np
import pandas as pd

METRICS = ["linkCount", "sourceCount"]
RELERR_MAX = 0.05

_EMPTY_COLS = [*METRICS, "topSourceId", "topSourceLinks"]


def flatten_tree(children: dict, prefix: tuple = ()) -> list[dict]:
    rows = []
    for k, v in children.items():
        path = (*prefix, k)
        if "children" in v:
            rows.extend(flatten_tree(v["children"], path))
        rows.append(
            {m: v.get(m, 0) for m in METRICS}
            | {"path": "-".join(map(str, path))}
            | {
                "topSourceId": v.get("topSourceId"),
                "topSourceLinks": v.get("topSourceLinks", 0),
            }
        )
    return rows


def rows_to_df(rows: list[dict]) -> pd.DataFrame:
    if rows:
        return pd.DataFrame(rows).set_index("path")
    return pd.DataFrame(columns=_EMPTY_COLS, index=pd.Index([], name="path"))


def make_diff_df(
    children_a: dict, label_a: str, children_b: dict, label_b: str
) -> pd.DataFrame:
    """Flatten both tree children dicts and outer-join on path with prefixed columns."""
    df_a = rows_to_df(flatten_tree(children_a)).add_prefix(f"{label_a}_")
    df_b = rows_to_df(flatten_tree(children_b)).add_prefix(f"{label_b}_")
    return df_a.join(df_b, how="outer").fillna(0)


def metric_stats(df: pd.DataFrame, col: str, label_a: str, label_b: str) -> dict | None:
    """Compute stats scoped to label_a-present nodes; None if mean rel-error > RELERR_MAX."""
    col_a = f"{label_a}_{col}"
    col_b = f"{label_b}_{col}"
    nodes_a = df.loc[df[col_a] > 0]
    matched = nodes_a.loc[nodes_a[col_b] > 0]
    pearson = matched[col_a].corr(matched[col_b]) if len(matched) >= 2 else np.nan
    mid = (nodes_a[col_a] + nodes_a[col_b]) / 2.0
    relerr = (nodes_a[col_a] - nodes_a[col_b]).abs() / mid.replace(0, np.nan)
    if relerr.mean() > RELERR_MAX:
        return None
    return {
        "pearson": float(pearson) if pd.notna(pearson) else None,
        "relerr": float(relerr.mean()) if len(relerr) > 0 else None,
        "n_missing": int((nodes_a[col_b] == 0).sum()),
    }


def top_source_stats(df: pd.DataFrame, label_a: str, label_b: str) -> dict:
    col_links_a = f"{label_a}_topSourceLinks"
    col_links_b = f"{label_b}_topSourceLinks"
    col_id_a = f"{label_a}_topSourceId"
    col_id_b = f"{label_b}_topSourceId"
    both = df.loc[(df[col_links_a] > 0) & (df[col_links_b] > 0)]
    if both.empty:
        return {"id_match_rate": None, "link_relerr": None}
    id_match_rate = float((both[col_id_a] == both[col_id_b]).mean())
    mid = (both[col_links_a] + both[col_links_b]) / 2.0
    link_relerr = float(
        ((both[col_links_a] - both[col_links_b]).abs() / mid.replace(0, np.nan)).mean()
    )
    return {"id_match_rate": id_match_rate, "link_relerr": link_relerr}
