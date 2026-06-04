"""Poster-quality vector figures from comparison-artifact CSVs.

Reads a run's ``summary.csv`` (per-query rows) and ``memory_samples.csv`` (the
memory time-series, written by ``comparison_report.save_mem_samples``) and emits
clean SVG + PDF figures for the A0 poster. Vector output keeps text editable
(SVG) and print-ready (PDF). Existing PNGs are never touched — new files use a
fixed stem with ``.svg`` / ``.pdf`` extensions.

Colours follow the poster brief: Rankless is the saturated brand cyan-blue (the
hero), the PostgreSQL + Flask baseline is a muted grey-red that recedes. Every
figure shares this mapping so colours never swap between plots.

Speed and memory each get alternate cuts of the same data (combined gap, speedup
distribution, peak bars) so the poster designer can pick the framing per panel.

Standalone:
    python -m pyscripts.poster_figures <artifacts_dir> [--out-dir DIR] \
        [--only speed,speed-combined,speedup,memory,memory-peak,accuracy]

It is also called automatically at the end of ``sql_comparison.run_comparison``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter, LogLocator

RANKLESS = "#1f8fd0"
BASELINE = "#bd7a73"
RANKLESS_LABEL = "Rankless"
BASELINE_LABEL = "PostgreSQL + Flask"
ACC_GOOD = "#3a9b58"
ACC_WARN = "#e0902f"
ACC_BAD = "#cc4b3f"

# the live-site "range" spectrum (src/routes/styles.css), legible slice for white
SPECTRUM = LinearSegmentedColormap.from_list(
    "rankless_spectrum",
    ["#0dc6f3", "#269ada", "#5842a8", "#7d0082", "#af5850", "#e1b01e", "#fadc05"],
)
# darker sub-range that stays readable on a light background (the brand --text-grad)
TEXT_GRAD = LinearSegmentedColormap.from_list(
    "rankless_textgrad", ["#269ada", "#7d0082", "#c88437"]
)

mpl.rcParams.update(
    {
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "font.family": "sans-serif",
        "font.size": 13,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#444444",
        "axes.labelcolor": "#222222",
        "text.color": "#222222",
        "xtick.color": "#444444",
        "ytick.color": "#444444",
    }
)


def _count_fmt(v: float, _pos: int) -> str:
    if v >= 1e6:
        return f"{v / 1e6:g}M"
    if v >= 1e3:
        return f"{v / 1e3:g}k"
    return f"{v:g}"


def _time_fmt(v: float, _pos: int) -> str:
    return f"{v * 1000:g} ms" if v < 1 else f"{v:g} s"


def _save(fig, out_stem: Path) -> list[Path]:
    out_stem.parent.mkdir(parents=True, exist_ok=True)
    paths = [out_stem.with_suffix(ext) for ext in (".svg", ".pdf")]
    for p in paths:
        fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    return paths


def load_summary(summary_csv: Path) -> pd.DataFrame:
    return pd.read_csv(summary_csv)


def speed_view(summary: pd.DataFrame) -> pd.DataFrame:
    df = summary[(summary["time_a"] > 0) & (summary["time_b"] > 0)].copy()
    df["depth"] = df["bd_label"].str.count(";") + 1
    return df


def _loglog_fit(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    slope, intercept = np.polyfit(np.log10(x), np.log10(y), 1)
    xs = np.array([x.min(), x.max()])
    ys = 10 ** (intercept + slope * np.log10(xs))
    return xs, ys


def _fit_line(ax, x: np.ndarray, y: np.ndarray, color: str, lw: float = 2.2) -> None:
    xs, ys = _loglog_fit(x, y)
    ax.plot(xs, ys, color=color, lw=lw, zorder=4)


def _gradient_barh(ax, y: float, width: float, height: float, cmap) -> None:
    """Fill a horizontal bar [0, width] at row y with a left→right gradient."""
    grad = np.linspace(0, 1, 256).reshape(1, -1)
    ax.imshow(
        grad,
        extent=(0, width, y - height / 2, y + height / 2),
        aspect="auto",
        cmap=cmap,
        vmin=0,
        vmax=1,
        zorder=3,
    )


def plot_speed(df: pd.DataFrame, out_stem: Path) -> list[Path]:
    series = {
        RANKLESS_LABEL: (df["time_b"], RANKLESS, "o"),
        BASELINE_LABEL: (df["time_a"], BASELINE, "s"),
    }
    depths = sorted(df["depth"].unique())
    fig, axes = plt.subplots(
        1, len(depths), figsize=(4.5 * len(depths), 5.0), sharey=True
    )
    if len(depths) == 1:
        axes = [axes]

    for ax, depth in zip(axes, depths):
        sub = df[df["depth"] == depth]
        cits = sub["citation_count"].to_numpy(dtype=float)
        for label, (times, color, marker) in series.items():
            y = times[sub.index].to_numpy(dtype=float)
            ax.scatter(
                cits,
                y,
                s=24,
                alpha=0.45,
                color=color,
                marker=marker,
                edgecolor="none",
                label=label,
                zorder=3,
            )
            _fit_line(ax, cits, y, color)

        ratio = (sub["time_a"] / sub["time_b"]).median()
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.xaxis.set_major_formatter(FuncFormatter(_count_fmt))
        ax.yaxis.set_major_formatter(FuncFormatter(_time_fmt))
        ax.yaxis.set_major_locator(LogLocator(base=10))
        ax.grid(True, which="major", color="#000000", alpha=0.07, lw=0.8)
        ax.set_axisbelow(True)
        ax.set_title(
            f"{depth} breakdown level" + ("s" if depth != 1 else ""),
            fontsize=14,
            pad=10,
        )
        ax.set_xlabel("entity size — citations  (bigger →)", fontsize=12)
        ax.annotate(
            f"median {ratio:.0f}× faster",
            xy=(0.04, 0.94),
            xycoords="axes fraction",
            ha="left",
            va="top",
            fontsize=12,
            fontweight="bold",
            color=RANKLESS,
        )

    axes[0].set_ylabel("response time  (slower ↑)", fontsize=12)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper right",
        ncol=2,
        frameon=False,
        fontsize=13,
        bbox_to_anchor=(0.99, 0.965),
    )
    fig.suptitle(
        "Response time — Rankless vs. PostgreSQL + Flask baseline",
        x=0.01,
        y=0.99,
        ha="left",
        fontsize=17,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.915,
        f"{len(df)} hierarchical citation queries · log–log axes · lower is faster",
        fontsize=12,
        color="#666666",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    return _save(fig, out_stem)


def plot_speed_combined(df: pd.DataFrame, out_stem: Path) -> list[Path]:
    """Single-panel version: every query at once, with the persistent gap shaded."""
    fig, ax = plt.subplots(figsize=(10, 6))
    cits = df["citation_count"].to_numpy(dtype=float)
    for label, times, color, marker in (
        (BASELINE_LABEL, df["time_a"], BASELINE, "s"),
        (RANKLESS_LABEL, df["time_b"], RANKLESS, "o"),
    ):
        y = times.to_numpy(dtype=float)
        ax.scatter(
            cits,
            y,
            s=26,
            alpha=0.4,
            color=color,
            marker=marker,
            edgecolor="none",
            label=label,
            zorder=3,
        )

    xs, y_rs = _loglog_fit(cits, df["time_b"].to_numpy(dtype=float))
    _, y_fl = _loglog_fit(cits, df["time_a"].to_numpy(dtype=float))
    ax.fill_between(xs, y_rs, y_fl, color=RANKLESS, alpha=0.08, zorder=1)
    ax.plot(xs, y_rs, color=RANKLESS, lw=2.6, zorder=4)
    ax.plot(xs, y_fl, color=BASELINE, lw=2.6, zorder=4)

    ratio = (df["time_a"] / df["time_b"]).median()
    mid_x = 10 ** np.mean(np.log10(xs))
    mid_y = 10 ** np.mean(
        [np.log10(np.interp(mid_x, xs, y_rs)), np.log10(np.interp(mid_x, xs, y_fl))]
    )
    ax.annotate(
        f"≈ {ratio:.0f}× faster\n(median)",
        xy=(mid_x, mid_y),
        ha="center",
        va="center",
        fontsize=14,
        fontweight="bold",
        color=RANKLESS,
        bbox=dict(
            boxstyle="round,pad=0.35", fc="white", ec=RANKLESS, lw=1.2, alpha=0.92
        ),
        zorder=6,
    )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(_count_fmt))
    ax.yaxis.set_major_formatter(FuncFormatter(_time_fmt))
    ax.yaxis.set_major_locator(LogLocator(base=10))
    ax.grid(True, which="major", color="#000000", alpha=0.07, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("entity size — citations behind the query  (bigger →)", fontsize=13)
    ax.set_ylabel("response time  (slower ↑)", fontsize=13)
    ax.legend(loc="upper left", frameon=False, fontsize=14, markerscale=1.6)
    fig.suptitle(
        "Response time — Rankless vs. PostgreSQL + Flask",
        x=0.01,
        y=0.99,
        ha="left",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.925,
        f"{len(df)} hierarchical citation queries · log–log axes · the gap holds across "
        "four orders of magnitude",
        fontsize=12.5,
        color="#666666",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    return _save(fig, out_stem)


def plot_speedup_dist(df: pd.DataFrame, out_stem: Path) -> list[Path]:
    """The 'every query was faster' story: distribution of per-query speedup."""
    ratio = (df["time_a"] / df["time_b"]).to_numpy(dtype=float)
    lr = np.log10(ratio)
    med = np.median(ratio)
    rng = np.random.default_rng(0)
    jitter = rng.uniform(-0.34, 0.34, size=lr.size)

    fig, ax = plt.subplots(figsize=(11, 4.2))
    parts = ax.violinplot(lr, positions=[0], vert=False, widths=0.9, showextrema=False)
    for body in parts["bodies"]:
        body.set_facecolor(RANKLESS)
        body.set_alpha(0.12)
    ax.scatter(
        lr, jitter, c=lr, cmap=TEXT_GRAD, s=26, alpha=0.75, edgecolor="none", zorder=3
    )

    ax.axvline(0, color=BASELINE, lw=1.6, ls="--", zorder=2)
    ax.annotate(
        "parity (1×)\n← Rankless slower: 0 queries",
        xy=(0, 0.62),
        ha="center",
        va="bottom",
        fontsize=10.5,
        color=BASELINE,
    )
    ax.axvline(np.log10(med), color=RANKLESS, lw=2.0, zorder=4)
    ax.annotate(
        f"median {med:.0f}×",
        xy=(np.log10(med), -0.62),
        ha="center",
        va="top",
        fontsize=13,
        fontweight="bold",
        color=RANKLESS,
    )

    ticks = [0, 1, 2, 3]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{10**t:g}×" for t in ticks])
    ax.set_xlim(-0.35, lr.max() + 0.2)
    ax.set_yticks([])
    ax.set_ylim(-0.9, 0.9)
    ax.spines["left"].set_visible(False)
    ax.grid(True, axis="x", color="#000000", alpha=0.07, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("per-query speedup — Rankless vs. baseline  (log scale)", fontsize=13)
    fig.suptitle(
        "Every single query ran faster",
        x=0.01,
        y=0.99,
        ha="left",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.9,
        f"{len(df)} queries · range {ratio.min():.0f}×–{ratio.max():.0f}× · "
        f"median {med:.0f}× · each dot is one query",
        fontsize=12.5,
        color="#666666",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    return _save(fig, out_stem)


def plot_memory(mem_df: pd.DataFrame, out_stem: Path) -> list[Path]:
    mins = mem_df["elapsed_s"].to_numpy() / 60.0
    series = {
        BASELINE_LABEL: (mem_df["flask_mib"].to_numpy() / 1024.0, BASELINE, 1.6),
        RANKLESS_LABEL: (mem_df["rs_mib"].to_numpy() / 1024.0, RANKLESS, 2.0),
    }
    fig, ax = plt.subplots(figsize=(12, 5))
    peaks: dict[str, float] = {}
    for z, (label, (gib, color, lw)) in enumerate(series.items()):
        ax.fill_between(mins, gib, color=color, alpha=0.12, zorder=z)
        ax.plot(mins, gib, color=color, lw=lw, label=label, zorder=z + 2)
        peaks[label] = float(gib.max())
        ax.axhline(peaks[label], color=color, ls="--", lw=0.9, alpha=0.55, zorder=1)

    x_end = mins.max()
    for label, color in ((BASELINE_LABEL, BASELINE), (RANKLESS_LABEL, RANKLESS)):
        ax.annotate(
            f"peak {peaks[label]:.1f} GiB",
            xy=(x_end, peaks[label]),
            xytext=(-4, 4),
            textcoords="offset points",
            ha="right",
            va="bottom",
            fontsize=11,
            fontweight="bold",
            color=color,
        )

    ratio = peaks[BASELINE_LABEL] / peaks[RANKLESS_LABEL]
    ax.annotate(
        f"{ratio:.1f}× lower peak",
        xy=(0.02, 0.68),
        xycoords="axes fraction",
        ha="left",
        va="center",
        fontsize=14,
        fontweight="bold",
        color=RANKLESS,
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none", alpha=0.75),
    )

    ax.set_ylim(bottom=0)
    ax.set_xlim(left=0, right=x_end)
    ax.set_xlabel("elapsed time (minutes)", fontsize=12)
    ax.set_ylabel("memory footprint (GiB)", fontsize=12)
    ax.grid(True, which="major", color="#000000", alpha=0.07, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False, fontsize=13)
    fig.suptitle(
        "Memory footprint over the full benchmark",
        x=0.01,
        y=0.99,
        ha="left",
        fontsize=17,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.915,
        "container RSS while answering every query · flatter & lower is better",
        fontsize=12,
        color="#666666",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.85))
    return _save(fig, out_stem)


def plot_memory_peak(mem_df: pd.DataFrame, out_stem: Path) -> list[Path]:
    """Big, legible-from-distance peak-vs-mean memory bars."""
    stats = {
        BASELINE_LABEL: (
            mem_df["flask_mib"].max() / 1024,
            mem_df["flask_mib"].mean() / 1024,
        ),
        RANKLESS_LABEL: (mem_df["rs_mib"].max() / 1024, mem_df["rs_mib"].mean() / 1024),
    }
    fig, ax = plt.subplots(figsize=(10, 3.6))
    rows = [BASELINE_LABEL, RANKLESS_LABEL]  # baseline on top, hero below
    for i, label in enumerate(rows):
        y = len(rows) - 1 - i
        peak, mean = stats[label]
        if label == RANKLESS_LABEL:
            _gradient_barh(ax, y, peak, 0.62, SPECTRUM)
        else:
            ax.barh(y, peak, height=0.62, color=BASELINE, zorder=3)
        ax.plot([mean, mean], [y - 0.31, y + 0.31], color="white", lw=2.0, zorder=5)
        ax.annotate(
            f"{peak:.1f} GiB",
            xy=(peak, y),
            xytext=(8, 0),
            textcoords="offset points",
            va="center",
            fontsize=15,
            fontweight="bold",
            color="#222222",
        )
        ax.annotate(
            f"mean {mean:.1f}",
            xy=(mean, y - 0.31),
            xytext=(0, -3),
            textcoords="offset points",
            ha="center",
            va="top",
            fontsize=9.5,
            color="#666666",
        )

    ratio = stats[BASELINE_LABEL][0] / stats[RANKLESS_LABEL][0]
    ax.text(
        stats[BASELINE_LABEL][0] * 0.62,
        0.5,
        f"{ratio:.1f}× smaller peak",
        ha="center",
        va="center",
        fontsize=15,
        fontweight="bold",
        color=RANKLESS,
        bbox=dict(
            boxstyle="round,pad=0.35", fc="white", ec=RANKLESS, lw=1.1, alpha=0.92
        ),
        zorder=6,
    )

    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(rows[::-1], fontsize=13)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlim(0, stats[BASELINE_LABEL][0] * 1.18)
    ax.set_xlabel("peak container memory (GiB)  — white tick = mean", fontsize=12.5)
    ax.grid(True, axis="x", color="#000000", alpha=0.07, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("left", "right", "top"):
        ax.spines[s].set_visible(False)
    fig.suptitle(
        "Peak memory footprint",
        x=0.01,
        y=1.02,
        ha="left",
        fontsize=18,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.9,
        "highest container RSS over the full benchmark · both fit on one commodity box",
        fontsize=12.5,
        color="#666666",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    return _save(fig, out_stem)


def plot_accuracy(summary: pd.DataFrame, out_stem: Path) -> list[Path]:
    by_type = (
        summary.groupby("root_type")[["relerr_lc", "relerr_sc"]]
        .mean()
        .sort_values("relerr_sc")
    )
    fig, axes = plt.subplots(
        1, 2, figsize=(12, max(4.0, len(by_type) * 0.62 + 1.4)), sharey=True
    )
    panels = [
        (axes[0], "relerr_lc", "Citation-count error"),
        (axes[1], "relerr_sc", "Source-count error"),
    ]
    for ax, col, title in panels:
        vals = by_type[col] * 100
        colors = [
            ACC_GOOD if v < 1 else ACC_WARN if v < 5 else ACC_BAD for v in vals.values
        ]
        ax.barh(by_type.index, vals, color=colors, zorder=3)
        for y, v in enumerate(vals.values):
            ax.annotate(
                f"{v:.1f}%",
                xy=(v, y),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
                fontsize=11,
                color="#444444",
            )
        ax.axvline(1, color=ACC_GOOD, ls="--", lw=0.9, alpha=0.7)
        ax.axvline(5, color=ACC_BAD, ls="--", lw=0.9, alpha=0.7)
        ax.set_xlabel("mean relative error (%)", fontsize=12)
        ax.set_title(title, fontsize=14, pad=8)
        ax.set_xlim(left=0)
        ax.grid(True, axis="x", color="#000000", alpha=0.07, lw=0.8)
        ax.set_axisbelow(True)

    fig.suptitle(
        "Structural accuracy vs. the PostgreSQL baseline",
        x=0.01,
        y=0.99,
        ha="left",
        fontsize=17,
        fontweight="bold",
    )
    fig.text(
        0.01,
        0.915,
        "mean error per entity type · lower is better · green < 1%, red ≥ 5%",
        fontsize=12,
        color="#666666",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.85))
    return _save(fig, out_stem)


def generate_from_artifacts(
    artifacts_dir: Path,
    out_dir: Path | None = None,
    only: set[str] | None = None,
) -> list[Path]:
    out_dir = out_dir or artifacts_dir
    summary = load_summary(artifacts_dir / "summary.csv")
    speed = speed_view(summary)
    wrote: list[Path] = []

    def want(name: str) -> bool:
        return not only or name in only

    if want("speed"):
        wrote += plot_speed(speed, out_dir / "timing_plot")
    if want("speed-combined"):
        wrote += plot_speed_combined(speed, out_dir / "timing_combined")
    if want("speedup"):
        wrote += plot_speedup_dist(speed, out_dir / "timing_speedup")
    if want("accuracy"):
        wrote += plot_accuracy(summary, out_dir / "accuracy_plot")
    mem_csv = artifacts_dir / "memory_samples.csv"
    if mem_csv.exists():
        mem = pd.read_csv(mem_csv)
        if want("memory"):
            wrote += plot_memory(mem, out_dir / "memory_plot")
        if want("memory-peak"):
            wrote += plot_memory_peak(mem, out_dir / "memory_peak")
    return wrote


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "artifacts_dir", type=Path, help="run dir holding summary.csv (+ memory CSV)"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="where to write figures (default: the artifacts dir)",
    )
    parser.add_argument(
        "--only",
        type=lambda s: set(s.split(",")),
        default=None,
        help="comma-separated subset of: "
        "speed,speed-combined,speedup,memory,memory-peak,accuracy",
    )
    args = parser.parse_args()
    for p in generate_from_artifacts(args.artifacts_dir, args.out_dir, args.only):
        print(f"wrote {p}")


if __name__ == "__main__":
    main()
