"""Shared analysis and report generation for server comparison scripts.

CompResult.diff_df always uses "a_" / "b_" prefixed columns (from make_diff_df
called with label_a="a", label_b="b"). Display labels (e.g. "rs", "flask",
branch names) are passed separately to reporting functions.

Used by branch_comparison.py (branch A vs branch B) and
sql_comparison.py (Flask/PG vs Rust).
"""

import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from pyscripts.tree_diff import METRICS, metric_stats, top_source_stats

ARTIFACTS_ROOT = Path("logs/comparison-artifacts")

logger = logging.getLogger("rankless.comparison")


@dataclass
class CompResult:
    root_type: str
    bd_label: str
    citation_count: int
    time_a: float
    time_b: float
    diff_df: pd.DataFrame
    error: str | None = None


@dataclass
class MemSample:
    elapsed: float
    values: dict[str, float]  # display_label -> MiB


def _parse_mem_mib(s: str) -> float:
    s = s.split("/")[0].strip()
    if "GiB" in s:
        return float(s.replace("GiB", "")) * 1024
    if "MiB" in s:
        return float(s.replace("MiB", ""))
    if "KiB" in s:
        return float(s.replace("KiB", "")) / 1024
    return 0.0


class MemoryTracker:
    """Poll docker container memory usage at a fixed interval.

    containers: {container_name: display_label}
    """

    def __init__(self, containers: dict[str, str], interval: float = 2.0) -> None:
        self.containers = containers
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
                *self.containers.keys(),
            ],
            capture_output=True,
            text=True,
        )
        values: dict[str, float] = {label: 0.0 for label in self.containers.values()}
        for line in r.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            name, usage = parts
            for cname, label in self.containers.items():
                if cname in name:
                    values[label] = _parse_mem_mib(usage)
                    break
        return MemSample(time.monotonic() - self._t0, values)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.samples.append(self._poll())
            self._stop.wait(self._interval)


def build_mem_stats(samples: list[MemSample]) -> dict:
    if not samples:
        return {}
    labels = list(samples[0].values.keys())
    stats: dict = {"n_mem_samples": len(samples)}
    for label in labels:
        vals = [s.values[label] for s in samples]
        stats[f"{label}_peak_mib"] = max(vals)
        stats[f"{label}_mean_mib"] = sum(vals) / len(vals)
    return stats


def setup_logging(log_path: Path) -> None:
    """Attach file (DEBUG) and console (INFO) handlers to the module logger."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    logger.addHandler(ch)


# ── analysis ──────────────────────────────────────────────────────────────────

_EMPTY_SUMMARY_COLS = [
    "root_type",
    "bd_label",
    "citation_count",
    "time_a",
    "time_b",
    "pearson_lc",
    "pearson_sc",
    "relerr_lc",
    "relerr_sc",
    "missing_in_b",
    "ts_id_match",
    "ts_link_relerr",
]


def build_summary_df(results: list[CompResult]) -> pd.DataFrame:
    rows = []
    for cr in results:
        if cr.error:
            continue
        lc = metric_stats(cr.diff_df, METRICS[0], "a", "b")
        sc = metric_stats(cr.diff_df, METRICS[1], "a", "b")
        if lc is None or sc is None:
            logger.debug("skipped %s/%s (empty diff)", cr.root_type, cr.bd_label)
            continue
        ts = top_source_stats(cr.diff_df, "a", "b")
        rows.append(
            {
                "root_type": cr.root_type,
                "bd_label": cr.bd_label,
                "citation_count": cr.citation_count,
                "time_a": cr.time_a,
                "time_b": cr.time_b,
                "pearson_lc": lc["pearson"],
                "pearson_sc": sc["pearson"],
                "relerr_lc": lc["relerr"],
                "relerr_sc": sc["relerr"],
                "missing_in_b": lc["missing_in_b"],
                "ts_id_match": ts["id_match_rate"],
                "ts_link_relerr": ts["link_relerr"],
            }
        )
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=_EMPTY_SUMMARY_COLS)


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
            missing_in_b=("missing_in_b", "sum"),
            ts_id_match=("ts_id_match", "mean"),
            ts_link_relerr=("ts_link_relerr", "mean"),
        )
        .reset_index()
        .assign(time_rate=lambda df: df["time_a"] / df["time_b"])
        .sort_values("relerr_sc")
    )


def build_totals(results: list[CompResult], summary_df: pd.DataFrame) -> dict:
    time_a = float(summary_df["time_a"].sum())
    time_b = float(summary_df["time_b"].sum())
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
        "total_missing_in_b": int(summary_df["missing_in_b"].sum()),
        "mean_ts_id_match": float(summary_df["ts_id_match"].mean()),
        "mean_ts_link_relerr": float(summary_df["ts_link_relerr"].mean()),
    }


# ── display specs ─────────────────────────────────────────────────────────────


def _totals_spec(label_a: str, label_b: str) -> list[tuple]:
    return [
        ("n_comparisons", "Comparisons", str),
        ("n_errors", "Errors", str),
        ("total_time_a", f"Total time ({label_a})", lambda v: f"{v:.1f}s"),
        ("total_time_b", f"Total time ({label_b})", lambda v: f"{v:.1f}s"),
        (
            "time_ratio_a_over_b",
            f"Time ratio ({label_a}/{label_b})",
            lambda v: f"{v:.2f}×",
        ),
        ("mean_pearson_lc", "Mean Pearson (link count)", lambda v: f"{v:.4f}"),
        ("mean_pearson_sc", "Mean Pearson (source count)", lambda v: f"{v:.4f}"),
        ("mean_relerr_lc", "Mean rel-error (link count)", lambda v: f"{v:.2%}"),
        ("mean_relerr_sc", "Mean rel-error (source count)", lambda v: f"{v:.2%}"),
        ("total_missing_in_b", f"Nodes only in {label_a}", str),
        ("mean_ts_id_match", "Top-source ID match rate", lambda v: f"{v:.1%}"),
        ("mean_ts_link_relerr", "Top-source link rel-error", lambda v: f"{v:.2%}"),
    ]


def _col_spec(label_a: str, label_b: str) -> list[tuple]:
    return [
        ("root_type", "Root", None),
        ("bd_label", "Breakdown", None),
        ("n", "N", None),
        ("time_rate", f"{label_a}/{label_b}", lambda v: f"{v:.2f}×"),
        ("pearson_lc", "r(LC)", lambda v: f"{v:.3f}"),
        ("pearson_sc", "r(SC)", lambda v: f"{v:.3f}"),
        ("relerr_lc", "err(LC)", lambda v: f"{v:.2%}"),
        ("relerr_sc", "err(SC)", lambda v: f"{v:.2%}"),
        ("missing_in_b", f"only-{label_a}", None),
        ("ts_id_match", "TopID%", lambda v: f"{v:.0%}"),
        ("ts_link_relerr", "TopLnkErr", lambda v: f"{v:.2%}"),
    ]


# ── console report ────────────────────────────────────────────────────────────


def print_report(
    grouped_df: pd.DataFrame, totals: dict, label_a: str, label_b: str
) -> None:
    cols = _col_spec(label_a, label_b)
    df_cols = [c[0] for c in cols]
    fmt = {c[0]: c[2] for c in cols if c[2] is not None}
    print(f"\n{'=' * 80}")
    print(f"BY root_type × breakdown  |  A={label_a}  B={label_b}")
    print("=" * 80)
    with pd.option_context("display.max_rows", 100, "display.max_colwidth", 60):
        print(grouped_df[df_cols].to_string(index=False, formatters=fmt))
    print(f"\n{'=' * 80}\nTOTALS\n{'=' * 80}")
    for key, label, fmt_fn in _totals_spec(label_a, label_b):
        val = totals.get(key)
        print(f"  {label}: {fmt_fn(val) if val is not None else '—'}")


# ── plots ─────────────────────────────────────────────────────────────────────


def plot_timing(
    results: list[CompResult], label_a: str, label_b: str, out_path: Path
) -> None:
    rows = []
    for r in results:
        if r.error or r.time_a <= 0 or r.time_b <= 0:
            continue
        bd_depth = len(r.bd_label.split(";"))
        for label, t in [(label_a, r.time_a), (label_b, r.time_b)]:
            rows.append(
                {
                    "backend": label,
                    "bd_depth": bd_depth,
                    "citations": r.citation_count,
                    "time_s": t,
                }
            )
    if not rows:
        return
    df = pd.DataFrame(rows).assign(
        log_citations=lambda df: np.log2(df["citations"]),
        log_time=lambda df: np.log2(df["time_s"]),
    )
    depth_order = sorted(df["bd_depth"].unique())
    g = sns.lmplot(
        data=df,
        x="log_citations",
        y="log_time",
        hue="backend",
        hue_order=[label_a, label_b],
        col="bd_depth",
        col_order=depth_order,
        palette=["#e45756", "#4c78a8"],
        markers=["o", "s"],
        scatter_kws={"alpha": 0.55, "s": 30},
        line_kws={"linewidth": 1.5},
        height=4,
        aspect=0.85,
    )
    g.set_axis_labels("Entity citation count (log₂)", "Response time, s (log₂)")
    g.set_titles("Breakdown depth: {col_name}")
    g.figure.suptitle(
        f"{label_a} vs {label_b}: response time by entity size and breakdown depth",
        y=1.03,
        fontsize=12,
    )
    g.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    g.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("timing plot → %s", out_path)


def plot_accuracy(
    grouped_df: pd.DataFrame, label_a: str, label_b: str, out_path: Path
) -> None:
    by_type = (
        grouped_df.groupby("root_type")[["relerr_lc", "relerr_sc"]]
        .mean()
        .sort_values("relerr_sc")
    )
    fig, axes = plt.subplots(1, 2, figsize=(12, max(4, len(by_type) * 0.6 + 1)))
    for ax, col, title in [
        (axes[0], "relerr_lc", "Link count rel-error"),
        (axes[1], "relerr_sc", "Source count rel-error"),
    ]:
        vals = by_type[col] * 100
        colors = [
            "#54a24b" if v < 1 else "#f58518" if v < 5 else "#e45756"
            for v in vals.values
        ]
        ax.barh(by_type.index, vals, color=colors)
        ax.set_xlabel("Mean relative error (%)")
        ax.set_title(title)
        ax.axvline(1, color="#54a24b", linestyle="--", linewidth=0.8, alpha=0.7)
        ax.axvline(5, color="#e45756", linestyle="--", linewidth=0.8, alpha=0.7)
        ax.set_xlim(left=0)
    fig.suptitle(
        f"{label_a} vs {label_b}: structural accuracy by entity type", fontsize=12
    )
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("accuracy plot → %s", out_path)


def plot_memory(samples: list[MemSample], out_path: Path) -> None:
    if not samples:
        return
    labels = list(samples[0].values.keys())
    elapsed = [s.elapsed for s in samples]
    palette = ["#e45756", "#4c78a8", "#54a24b", "#f58518"]

    fig, ax = plt.subplots(figsize=(9, 4))
    for i, label in enumerate(labels):
        ax.plot(
            elapsed,
            [s.values[label] for s in samples],
            color=palette[i % len(palette)],
            label=label,
        )
    ax.set_xlabel("Elapsed time (s)")
    ax.set_ylabel("Memory usage (MiB)")
    ax.set_title("Container memory usage during evaluation")
    ax.legend()
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("memory plot → %s", out_path)


# ── markdown ──────────────────────────────────────────────────────────────────


def save_markdown(
    grouped_df: pd.DataFrame,
    totals: dict,
    label_a: str,
    label_b: str,
    out_path: Path,
    plot_paths: list[Path] | None = None,
    mem_stats: dict | None = None,
) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    cols = _col_spec(label_a, label_b)

    lines = [
        "# Comparison Report",
        "",
        f"**{ts}** | A=`{label_a}` vs B=`{label_b}`",
        "",
        f"> Time ratio = {label_a}/{label_b}. Values >1 mean {label_a} is slower.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
    ]
    for key, label, fmt_fn in _totals_spec(label_a, label_b):
        val = totals.get(key)
        lines.append(f"| {label} | {fmt_fn(val) if val is not None else '—'} |")

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
                cells.append("—")
            else:
                cells.append(str(val))
        lines.append("| " + " | ".join(cells) + " |")

    if mem_stats:
        labels = [
            k.removesuffix("_peak_mib") for k in mem_stats if k.endswith("_peak_mib")
        ]
        header = "| Metric | " + " | ".join(labels) + " |"
        sep = "|--------|" + "|".join("---" for _ in labels) + "|"
        peak_row = (
            "| Peak (MiB) | "
            + " | ".join(f"{mem_stats[f'{l}_peak_mib']:.0f}" for l in labels)
            + " |"
        )
        mean_row = (
            "| Mean (MiB) | "
            + " | ".join(f"{mem_stats[f'{l}_mean_mib']:.0f}" for l in labels)
            + " |"
        )
        lines += [
            "",
            "## Memory Usage",
            "",
            f"Samples: {mem_stats['n_mem_samples']}",
            "",
            header,
            sep,
            peak_row,
            mean_row,
            "",
        ]

    if plot_paths:
        lines += ["", "## Plots", ""]
        for p in plot_paths:
            lines.append(f"![{p.stem.replace('_', ' ').title()}]({p.name})")
            lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    logger.info("markdown report → %s", out_path)


# ── HTML ──────────────────────────────────────────────────────────────────────

_CSS = """\
body {
    font-family: system-ui, -apple-system, sans-serif;
    max-width: 1400px;
    margin: 2rem auto;
    padding: 0 1.5rem;
    color: #1a1a1a;
    line-height: 1.5;
}
h1 { font-size: 1.6rem; border-bottom: 2px solid #333; padding-bottom: 0.4em; }
h2 { font-size: 1.2rem; border-bottom: 1px solid #ddd; padding-bottom: 0.2em; margin-top: 2rem; }
code { background: #f0f0f0; padding: 0.1em 0.4em; border-radius: 3px; font-size: 0.9em; }
.meta { color: #555; font-size: 0.9rem; margin-bottom: 1.5rem; }
.summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 0.75rem;
    margin: 1rem 0;
}
.metric-card {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 0.9rem 1rem;
}
.metric-card .label {
    font-size: 0.7rem;
    color: #666;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 0.3rem;
}
.metric-card .value { font-size: 1.4rem; font-weight: 600; }
table { border-collapse: collapse; width: 100%; font-size: 0.82rem; margin: 0.5rem 0; }
th { background: #2c3e50; color: #fff; padding: 7px 10px; text-align: left; font-weight: 500; }
td { padding: 5px 10px; border-bottom: 1px solid #e8e8e8; }
tr:nth-child(even) td { background: #f7f7f7; }
tr:hover td { background: #eef4ff; }
.good { background: #d4edda !important; }
.warn { background: #fff3cd !important; }
.bad  { background: #f8d7da !important; }
.plots { display: flex; flex-wrap: wrap; gap: 1.5rem; margin: 1rem 0; }
.plots figure { margin: 0; }
.plots img { max-width: 100%; border: 1px solid #ddd; border-radius: 4px; display: block; }
.plots figcaption { font-size: 0.8rem; color: #555; margin-top: 0.3rem; text-align: center; }
"""


def _td_class(col: str, val) -> str:
    if pd.isna(val) or not isinstance(val, float):
        return ""
    if "pearson" in col:
        return "good" if val > 0.99 else "warn" if val > 0.95 else "bad"
    if "relerr" in col:
        return "good" if val < 0.01 else "warn" if val < 0.05 else "bad"
    if "ts_id_match" in col:
        return "good" if val > 0.9 else "warn" if val > 0.7 else "bad"
    if "ts_link_relerr" in col:
        return "good" if val < 0.02 else "warn" if val < 0.1 else "bad"
    return ""


def save_html(
    grouped_df: pd.DataFrame,
    totals: dict,
    label_a: str,
    label_b: str,
    out_path: Path,
    plot_paths: list[Path] | None = None,
    mem_stats: dict | None = None,
) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    cols = _col_spec(label_a, label_b)

    cards = "".join(
        f'<div class="metric-card">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{fmt_fn(totals[key]) if totals.get(key) is not None else "—"}</div>'
        f"</div>"
        for key, label, fmt_fn in _totals_spec(label_a, label_b)
        if key in totals
    )

    thead = "<tr>" + "".join(f"<th>{c[1]}</th>" for c in cols) + "</tr>"
    tbody_rows = []
    for _, row in grouped_df.iterrows():
        cells = ""
        for key, _, fmt_fn in cols:
            val = row[key]
            cls = _td_class(key, val)
            cls_attr = f' class="{cls}"' if cls else ""
            if fmt_fn and pd.notna(val):
                cell = fmt_fn(val)
            elif pd.isna(val):
                cell = "—"
            else:
                cell = str(val)
            cells += f"<td{cls_attr}>{cell}</td>"
        tbody_rows.append(f"<tr>{cells}</tr>")

    plots_html = ""
    if plot_paths:
        figures = "".join(
            f'<figure><img src="{p.name}" alt="{p.stem}">'
            f"<figcaption>{p.stem.replace('_', ' ').title()}</figcaption></figure>"
            for p in plot_paths
        )
        plots_html = f'<div class="plots">{figures}</div>'

    mem_html = ""
    if mem_stats:
        mem_labels = [
            k.removesuffix("_peak_mib") for k in mem_stats if k.endswith("_peak_mib")
        ]
        mem_thead = (
            "<tr><th>Metric</th>"
            + "".join(f"<th>{l}</th>" for l in mem_labels)
            + "</tr>"
        )
        peak_cells = "".join(
            f"<td>{mem_stats[f'{l}_peak_mib']:.0f}</td>" for l in mem_labels
        )
        mean_cells = "".join(
            f"<td>{mem_stats[f'{l}_mean_mib']:.0f}</td>" for l in mem_labels
        )
        mem_html = (
            "<h2>Memory Usage</h2>"
            f"<p>Samples: {mem_stats['n_mem_samples']}</p>"
            f"<table><thead>{mem_thead}</thead><tbody>"
            f"<tr><td>Peak (MiB)</td>{peak_cells}</tr>"
            f"<tr><td>Mean (MiB)</td>{mean_cells}</tr>"
            "</tbody></table>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Comparison: {label_a} vs {label_b}</title>
<style>
{_CSS}</style>
</head>
<body>
<h1>Comparison: <code>{label_a}</code> vs <code>{label_b}</code></h1>
<p class="meta">{ts} &middot; {totals["n_comparisons"]} comparisons, {totals["n_errors"]} errors</p>
<h2>Summary</h2>
<div class="summary-grid">{cards}</div>
<h2>By root type × breakdown</h2>
<table><thead>{thead}</thead>
<tbody>{"".join(tbody_rows)}</tbody></table>
{mem_html}
<h2>Plots</h2>
{plots_html}
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    logger.info("HTML report → %s", out_path)


def open_report(html_path: Path) -> None:
    try:
        subprocess.Popen(["firefox", str(html_path)])
    except Exception:
        pass
