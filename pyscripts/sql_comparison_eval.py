import json
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns
from dotenv import load_dotenv

load_dotenv(override=True)

import numpy as np
import pandas as pd
import requests
from ccl_science_data.common import EntC, load_map
from tqdm import tqdm

from pyscripts.cache_prompting import RTC, BatchRequester, get_specs_and_ys

FLASK_URL = "http://localhost:5000/impact-tree"
SQL_COMP_DIR = Path("sql-yardstick")
SNAPSHOT_PATH = SQL_COMP_DIR / "eval-snapshot.json"
REPORT_PATH = SQL_COMP_DIR / "eval-report.md"
PLOT_PATH = SQL_COMP_DIR / "timing-plot.png"
MEMORY_PLOT_PATH = SQL_COMP_DIR / "memory-plot.png"
RUST_CONTAINER = "rankless-rust"
PG_PYTHON_CONTAINER = "rankless-pg-python"
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


# ── memory tracking ──────────────────────────────────────────────────────────


def _parse_mem_mib(s: str) -> float:
    s = s.split("/")[0].strip()
    if "GiB" in s:
        return float(s.replace("GiB", "")) * 1024
    if "MiB" in s:
        return float(s.replace("MiB", ""))
    if "KiB" in s:
        return float(s.replace("KiB", "")) / 1024
    return 0.0


@dataclass
class MemSample:
    elapsed: float
    rust_mib: float
    flask_mib: float


class MemoryTracker:
    def __init__(self, interval: float = 2.0) -> None:
        self.samples: list[MemSample] = []
        self._interval = interval
        self._stop = threading.Event()
        self._t0 = 0.0
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._t0 = time.monotonic()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join()

    def _poll(self) -> MemSample:
        r = subprocess.run(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{.Name}}\t{{.MemUsage}}",
                RUST_CONTAINER,
                PG_PYTHON_CONTAINER,
            ],
            capture_output=True,
            text=True,
        )
        rust_mib = flask_mib = 0.0
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            name, usage = parts
            mib = _parse_mem_mib(usage)
            if RUST_CONTAINER in name:
                rust_mib = mib
            elif PG_PYTHON_CONTAINER in name:
                flask_mib = mib
        return MemSample(time.monotonic() - self._t0, rust_mib, flask_mib)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.samples.append(self._poll())
            self._stop.wait(self._interval)


# ── OA → DM mapping ─────────────────────────────────────────────────────────


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
            new_v["children"] = translate_tree(
                new_v["children"], breakdowns, maps, depth + 1
            )
        translated[dm_key] = new_v
    return translated


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
            | {
                "topSourceId": v.get("topSourceId"),
                "topSourceLinks": v.get("topSourceLinks", 0),
            }
        )
    return rows


_EMPTY_COLS = [*METRICS, "topSourceId", "topSourceLinks"]


def _rows_to_df(rows: list[dict]) -> pd.DataFrame:
    if rows:
        return pd.DataFrame(rows).set_index("path")
    return pd.DataFrame(columns=_EMPTY_COLS, index=pd.Index([], name="path"))


def make_diff_df(flask_dic: dict, rs_dic: dict) -> pd.DataFrame:
    flask_df = _rows_to_df(_flatten(flask_dic["children"])).add_prefix("flask_")
    rs_df = _rows_to_df(_flatten(rs_dic["tree"]["children"]))
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
        (
            (both["topSourceLinks"] - both["flask_topSourceLinks"]).abs()
            / mid.replace(0, np.nan)
        ).mean()
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
                    f'{b["attributeType"]}-{"S" if b["sourceSide"] else "T"}'
                    for b in bds
                )
                flask_bds = [
                    {"node": b["attributeType"], "sourceSide": b["sourceSide"]}
                    for b in bds
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

                try:
                    flask_resp = requests.post(FLASK_URL, json=payload)
                    flask_resp.raise_for_status()
                    rs_resp = requests.get(url)
                    flask_json = flask_resp.json()
                    flask_json["children"] = translate_tree(
                        flask_json["children"], bds, self.oa_dm_maps
                    )
                    yield CompResult(
                        root_type=root_type,
                        bd_label=bd_label,
                        citation_count=ccount,
                        flask_time=flask_resp.elapsed.total_seconds(),
                        rs_time=rs_resp.elapsed.total_seconds(),
                        diff_df=make_diff_df(flask_json, rs_resp.json()),
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
                "ts_id_match": ts["id_match_rate"],
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
            ts_id_match=("ts_id_match", "mean"),
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
        "mean_ts_id_match": float(summary_df["ts_id_match"].mean()),
        "mean_ts_link_relerr": float(summary_df["ts_link_relerr"].mean()),
    }


def build_mem_stats(samples: list[MemSample]) -> dict:
    if not samples:
        return {}
    rust = [s.rust_mib for s in samples]
    flask = [s.flask_mib for s in samples]
    return {
        "rust_peak_mib": max(rust),
        "rust_mean_mib": sum(rust) / len(rust),
        "flask_peak_mib": max(flask),
        "flask_mean_mib": sum(flask) / len(flask),
        "n_mem_samples": len(samples),
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
        "ts_id_match",
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
        "ts_id_match": "{:.1%}".format,
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
        elif "match" in k or "relerr" in k:
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


def plot_memory(samples: list[MemSample], out_path: Path) -> None:
    if not samples:
        return
    elapsed = [s.elapsed for s in samples]
    rust_mib = [s.rust_mib for s in samples]
    flask_mib = [s.flask_mib for s in samples]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(elapsed, rust_mib, color="#e45756", label="Rust")
    ax.plot(elapsed, flask_mib, color="#4c78a8", label="Flask (PG)")
    ax.set_xlabel("Elapsed time (s)")
    ax.set_ylabel("Memory usage (MiB)")
    ax.set_title("Container memory usage during evaluation")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nmemory plot → {out_path}")


# ── snapshot ──────────────────────────────────────────────────────────────────


def save_snapshot(grouped_df: pd.DataFrame, totals: dict) -> None:
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "grouped": grouped_df.to_dict(orient="records"),
        "totals": totals,
    }
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2))
    print(f"\nsnapshot saved → {SNAPSHOT_PATH}")


# ── markdown report ──────────────────────────────────────────────────────────


def _fmt_val(k: str, v) -> str:
    if not isinstance(v, float):
        return str(v)
    if "time" in k and "ratio" not in k:
        return f"{v:.1f}s"
    if "pearson" in k:
        return f"{v:.3f}"
    if "match" in k or "relerr" in k:
        return f"{v:.1%}"
    if "ratio" in k:
        return f"{v:.1f}x"
    return f"{v:.2f}"


def save_markdown(
    grouped_df: pd.DataFrame,
    totals: dict,
    results: list[CompResult],
    mem_stats: dict,
) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Reproduction Eval Report",
        f"",
        f"**{ts}** | {totals['n_comparisons']} comparisons, {totals['n_errors']} errors",
        f"",
        f"## Summary",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
    ]
    for k, v in totals.items():
        lines.append(f"| {k} | {_fmt_val(k, v)} |")

    lines += [
        f"",
        f"## By root type x breakdown",
        f"",
    ]

    cols = [
        ("root_type", "Root", None),
        ("bd_label", "Breakdown", None),
        ("n", "N", None),
        ("time_rate", "PG/RS", lambda v: f"{v:.1f}x"),
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
    lines += [header, sep]

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

    lines += [
        f"",
        f"## Timing",
        f"",
        f"| Backend | Total (s) |",
        f"|---------|-----------|",
        f"| Flask (PG) | {totals['total_flask_time']:.1f} |",
        f"| Rust | {totals['total_rs_time']:.1f} |",
        f"| Ratio (PG/RS) | {totals['total_duration_ratio']:.1f}x |",
        f"",
        f"![Response time scaling]({PLOT_PATH.name})",
        f"",
    ]

    if mem_stats:
        lines += [
            f"## Memory Usage",
            f"",
            f"| Metric | Rust | Flask (PG) |",
            f"|--------|------|------------|",
            f"| Peak (MiB) | {mem_stats['rust_peak_mib']:.0f} | {mem_stats['flask_peak_mib']:.0f} |",
            f"| Mean (MiB) | {mem_stats['rust_mean_mib']:.0f} | {mem_stats['flask_mean_mib']:.0f} |",
            f"| Samples | {mem_stats['n_mem_samples']} | — |",
            f"",
            f"![Memory usage over time]({MEMORY_PLOT_PATH.name})",
            f"",
        ]

    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(f"\nmarkdown report → {REPORT_PATH}")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    comper = ReproEvaluator()
    bins = [5_000, 10_000, 30_000, 100_000, 200_000]
    e_per_g = 4
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

    tracker = MemoryTracker()
    tracker.start()
    results = list(comper.iter_comparisons(decorated_df))
    tracker.stop()

    summary_df = build_summary_df(results)
    grouped_df = build_grouped_df(summary_df)
    totals = build_totals(results, summary_df)
    mem_stats = build_mem_stats(tracker.samples)
    print_report(grouped_df, totals)
    save_snapshot(grouped_df, totals)
    plot_timing(results, PLOT_PATH)
    plot_memory(tracker.samples, MEMORY_PLOT_PATH)
    save_markdown(grouped_df, totals, results, mem_stats)
