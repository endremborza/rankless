"""Reporting for the perf comparison (compare-branch).

Pairs two refs' per-query ``tlog`` phase timings, computes per-phase speedups
(A = candidate, B = baseline; speedup = t_B / t_A, >1 means A is faster), checks
that the two produce structurally identical trees (a perf change must not alter
output), and emits a console + markdown + HTML report plus a timing plot.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from pyscripts.comparison_report import _CSS, logger
from pyscripts.tree_diff import METRICS, make_diff_df, metric_stats

# tlog phase key -> display label. "compute" is the derived sum of the three.
PHASES = {
    "heaps": "got heaps",
    "roots": "fold (roots)",
    "serialize": "serialize",
}
PHASE_KEYS = [*PHASES, "compute"]


@dataclass
class QueryPerf:
    rt: str
    sem: str
    tid: int
    bd_label: str
    citations: int
    http_s: float
    phases_ms: dict[str, float]  # median ms per phase key (heaps/roots/serialize)
    phases_min_ms: dict[str, float]
    mem_delta_mib: float
    children: dict = field(default_factory=dict)  # one response, for the diff

    @property
    def compute_ms(self) -> float:
        return sum(self.phases_ms.get(k, 0.0) for k in PHASES)


@dataclass
class RefPerf:
    label: str
    sha: str
    baseline_mib: float
    peak_mib: float
    queries: list[QueryPerf]

    @property
    def mem_delta_mib(self) -> float:
        return self.peak_mib - self.baseline_mib


def _key(q: QueryPerf) -> tuple[str, str, int]:
    return (q.rt, q.sem, q.tid)


def _relerr(a: QueryPerf, b: QueryPerf) -> float:
    if not a.children or not b.children:
        return 0.0
    df = make_diff_df(a.children, "a", b.children, "b")
    stats = metric_stats(df, METRICS[0], "a", "b")
    if not stats or stats["relerr"] is None:
        return 0.0
    return float(stats["relerr"])


def build_pairs(run_a: RefPerf, run_b: RefPerf) -> pd.DataFrame:
    """One row per (rt, sem, tid) present in both refs, with a_/b_ phase columns."""
    b_by_key = {_key(q): q for q in run_b.queries}
    rows = []
    for qa in run_a.queries:
        qb = b_by_key.get(_key(qa))
        if qb is None:
            continue
        row = {
            "rt": qa.rt,
            "bd_label": qa.bd_label,
            "sem": qa.sem,
            "tid": qa.tid,
            "citations": qa.citations,
            "http_a": qa.http_s,
            "http_b": qb.http_s,
            "mem_a": qa.mem_delta_mib,
            "mem_b": qb.mem_delta_mib,
            "relerr": _relerr(qa, qb),
        }
        for k in PHASE_KEYS:
            av = qa.compute_ms if k == "compute" else qa.phases_ms.get(k, 0.0)
            bv = qb.compute_ms if k == "compute" else qb.phases_ms.get(k, 0.0)
            row[f"{k}_a"] = av
            row[f"{k}_b"] = bv
        rows.append(row)
    return pd.DataFrame(rows)


def _speedup(df: pd.DataFrame, key: str) -> float:
    a, b = df[f"{key}_a"].sum(), df[f"{key}_b"].sum()
    return b / a if a else float("nan")


def build_totals(df: pd.DataFrame, run_a: RefPerf, run_b: RefPerf) -> dict:
    return {
        "n": len(df),
        "max_relerr": float(df["relerr"].max()) if len(df) else 0.0,
        "peak_a": run_a.peak_mib,
        "peak_b": run_b.peak_mib,
        "mem_delta_a": run_a.mem_delta_mib,
        "mem_delta_b": run_b.mem_delta_mib,
        **{f"speedup_{k}": _speedup(df, k) for k in PHASE_KEYS},
    }


def build_grouped(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    g = df.groupby(["rt", "bd_label"], observed=True)
    out = g.agg(n=("citations", "count"), max_cites=("citations", "max")).reset_index()
    for k in PHASE_KEYS:
        sums = g[[f"{k}_a", f"{k}_b"]].sum()
        out[f"sp_{k}"] = (sums[f"{k}_b"] / sums[f"{k}_a"]).values
    out["relerr"] = g["relerr"].max().values
    return out.sort_values("max_cites", ascending=False)


# ── console ───────────────────────────────────────────────────────────────────


def print_report(
    df: pd.DataFrame, totals: dict, label_a: str, label_b: str, top_k: int = 8
) -> None:
    print(f"\n{'=' * 78}")
    print(f"PERF  A={label_a} (candidate)  vs  B={label_b} (baseline)")
    print(f"speedup = t_B / t_A  (>1 ⇒ A faster).  N={totals['n']}")
    print("=" * 78)
    for k in PHASE_KEYS:
        print(
            f"  {PHASES.get(k, 'compute total'):<16} speedup: {totals[f'speedup_{k}']:.2f}×"
        )
    print(
        f"  peak mem: A {totals['peak_a']:.0f} MiB / B {totals['peak_b']:.0f} MiB"
        f"  (rise A {totals['mem_delta_a']:.0f} / B {totals['mem_delta_b']:.0f} MiB)"
    )
    flag = "  ⚠ DIVERGENT OUTPUT" if totals["max_relerr"] > 0.001 else "  ✓ identical"
    print(f"  max rel-error (link count): {totals['max_relerr']:.2%}{flag}")

    if df.empty:
        return
    print(
        f"\n{'-' * 78}\nbiggest {top_k} queries (heaps / roots / compute ms, A→B, ×)\n{'-' * 78}"
    )
    big = df.sort_values("citations", ascending=False).head(top_k)
    for _, r in big.iterrows():
        seg = "  ".join(
            f"{k}:{r[f'{k}_a']:.0f}→{r[f'{k}_b']:.0f}({(r[f'{k}_b'] / r[f'{k}_a']) if r[f'{k}_a'] else float('nan'):.2f}×)"
            for k in ("heaps", "roots", "compute")
        )
        print(
            f"  {r['rt'][:12]:<12} {r['sem'][:22]:<22} c={int(r['citations']):>10}  {seg}"
        )


# ── markdown + html ─────────────────────────────────────────────────────────


def _totals_lines(totals: dict, label_a: str, label_b: str) -> list[tuple[str, str]]:
    rows = [
        ("Comparisons", str(totals["n"])),
        ("Peak mem A / B (MiB)", f"{totals['peak_a']:.0f} / {totals['peak_b']:.0f}"),
        (
            "Mem rise A / B (MiB)",
            f"{totals['mem_delta_a']:.0f} / {totals['mem_delta_b']:.0f}",
        ),
        (
            "Max rel-error (link count)",
            f"{totals['max_relerr']:.2%}"
            + ("  ⚠ divergent" if totals["max_relerr"] > 0.001 else "  ✓"),
        ),
    ]
    for k in PHASE_KEYS:
        rows.append(
            (
                f"Speedup — {PHASES.get(k, 'compute total')}",
                f"{totals[f'speedup_{k}']:.2f}×",
            )
        )
    return rows


def save_markdown(
    df: pd.DataFrame,
    grouped: pd.DataFrame,
    totals: dict,
    label_a: str,
    label_b: str,
    out_path: Path,
    plot_paths: list[Path] | None = None,
) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# Perf Comparison",
        "",
        f"**{ts}** | A=`{label_a}` (candidate) vs B=`{label_b}` (baseline)",
        "",
        "> speedup = t_B / t_A — values >1 mean A is faster.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
    ]
    lines += [f"| {k} | {v} |" for k, v in _totals_lines(totals, label_a, label_b)]

    if not grouped.empty:
        cols = [
            "rt",
            "bd_label",
            "n",
            "max_cites",
            "sp_heaps",
            "sp_roots",
            "sp_compute",
            "relerr",
        ]
        head = [
            "Root",
            "Breakdown",
            "N",
            "Max cites",
            "heaps×",
            "roots×",
            "compute×",
            "relerr",
        ]
        lines += ["", "## By root × breakdown", "", "| " + " | ".join(head) + " |"]
        lines.append("|" + "|".join("---" for _ in head) + "|")
        for _, r in grouped[cols].iterrows():
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(r["rt"]),
                        str(r["bd_label"]),
                        str(int(r["n"])),
                        f"{int(r['max_cites']):,}",
                        f"{r['sp_heaps']:.2f}×",
                        f"{r['sp_roots']:.2f}×",
                        f"{r['sp_compute']:.2f}×",
                        f"{r['relerr']:.2%}",
                    ]
                )
                + " |"
            )

    if plot_paths:
        lines += ["", "## Plots", ""]
        lines += [f"![{p.stem}]({p.name})\n" for p in plot_paths]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    logger.info("perf markdown → %s", out_path)


def save_html(
    grouped: pd.DataFrame,
    totals: dict,
    label_a: str,
    label_b: str,
    out_path: Path,
    plot_paths: list[Path] | None = None,
) -> None:
    cards = "".join(
        f'<div class="metric-card"><div class="label">{k}</div>'
        f'<div class="value">{v}</div></div>'
        for k, v in _totals_lines(totals, label_a, label_b)
    )
    table = ""
    if not grouped.empty:
        head = [
            "Root",
            "Breakdown",
            "N",
            "Max cites",
            "heaps×",
            "roots×",
            "compute×",
            "relerr",
        ]
        thead = "<tr>" + "".join(f"<th>{h}</th>" for h in head) + "</tr>"
        body = ""
        for _, r in grouped.iterrows():
            cells = [
                r["rt"],
                r["bd_label"],
                int(r["n"]),
                f"{int(r['max_cites']):,}",
                f"{r['sp_heaps']:.2f}×",
                f"{r['sp_roots']:.2f}×",
                f"{r['sp_compute']:.2f}×",
                f"{r['relerr']:.2%}",
            ]
            body += "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"
        table = f"<h2>By root × breakdown</h2><table><thead>{thead}</thead><tbody>{body}</tbody></table>"

    plots = ""
    if plot_paths:
        figs = "".join(
            f'<figure><img src="{p.name}" alt="{p.stem}">'
            f"<figcaption>{p.stem.replace('_', ' ').title()}</figcaption></figure>"
            for p in plot_paths
        )
        plots = f'<h2>Plots</h2><div class="plots">{figs}</div>'

    html = (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>Perf: {label_a} vs {label_b}</title><style>{_CSS}</style></head><body>"
        f"<h1>Perf: <code>{label_a}</code> (candidate) vs <code>{label_b}</code> (baseline)</h1>"
        f'<p class="meta">speedup = t_B / t_A — &gt;1 means A is faster.</p>'
        f'<h2>Summary</h2><div class="summary-grid">{cards}</div>{table}{plots}</body></html>'
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)
    logger.info("perf HTML → %s", out_path)


def plot_timing(df: pd.DataFrame, label_a: str, label_b: str, out_path: Path) -> None:
    if df.empty:
        return
    rows = []
    for _, r in df.iterrows():
        if r["citations"] <= 0:
            continue
        for phase in ("heaps", "roots", "compute"):
            for label, col in [(label_a, f"{phase}_a"), (label_b, f"{phase}_b")]:
                if r[col] > 0:
                    rows.append(
                        {
                            "ref": label,
                            "phase": phase,
                            "log_cites": np.log2(r["citations"]),
                            "log_ms": np.log2(r[col]),
                        }
                    )
    if not rows:
        return
    pdf = pd.DataFrame(rows)
    g = sns.lmplot(
        data=pdf,
        x="log_cites",
        y="log_ms",
        hue="ref",
        hue_order=[label_a, label_b],
        col="phase",
        col_order=["heaps", "roots", "compute"],
        palette=["#e45756", "#4c78a8"],
        markers=["o", "s"],
        scatter_kws={"alpha": 0.55, "s": 28},
        height=4,
        aspect=0.85,
        facet_kws={"sharey": False},
    )
    g.set_axis_labels("Citations (log₂)", "Phase time, ms (log₂)")
    g.set_titles("{col_name}")
    g.figure.suptitle(f"{label_a} vs {label_b}: cold tree-build phase time", y=1.03)
    g.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    g.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info("perf timing plot → %s", out_path)


def write_report(
    run_a: RefPerf,
    run_b: RefPerf,
    artifacts_dir: Path,
) -> None:
    df = build_pairs(run_a, run_b)
    grouped = build_grouped(df)
    totals = build_totals(df, run_a, run_b)
    df.to_csv(artifacts_dir / "per_query.csv", index=False)
    plot = artifacts_dir / "timing_plot.png"
    plot_timing(df, run_a.label, run_b.label, plot)
    plots = [plot] if plot.exists() else []
    print_report(df, totals, run_a.label, run_b.label)
    save_markdown(
        df,
        grouped,
        totals,
        run_a.label,
        run_b.label,
        artifacts_dir / "report.md",
        plots,
    )
    save_html(
        grouped, totals, run_a.label, run_b.label, artifacts_dir / "report.html", plots
    )
