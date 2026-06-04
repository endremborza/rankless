import base64
import io
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from ccl_science_data.common import load_map
from ccl_science_data.gen import EntC, Steps
from ccl_science_data.gen_reader_ext import GenReaderExt

START_YEAR = 1950
CITATION_THRESHOLD = 500

BG = "#0f1117"
PANEL = "#1a1d27"
BLUE = "#3b82f6"
TEXT = "#e5e7eb"
MUTED = "#9ca3af"
BORDER = "#374151"


def df_from_varr(sizes, targets):
    return pd.DataFrame(
        {"idx": np.repeat(np.arange(sizes.shape[0]), sizes), "val": targets}
    ).astype(int)


def gini(x: np.ndarray) -> float:
    x = np.sort(x.astype(float))
    n = len(x)
    if n == 0 or x.sum() == 0:
        return 0.0
    idx = np.arange(1, n + 1)
    return float((2 * (idx * x).sum() / (n * x.sum())) - (n + 1) / n)


def build_figure(year_counts, sf_raw, author_hits, citations, hit_rate) -> str:
    """Render the five-panel figure and return a base64-encoded PNG."""
    fig = plt.figure(figsize=(22, 9), facecolor=BG)
    gs = gridspec.GridSpec(
        2,
        4,
        figure=fig,
        left=0.05,
        right=0.98,
        top=0.88,
        bottom=0.10,
        wspace=0.32,
        hspace=0.35,
    )

    axes = [fig.add_subplot(gs[0, i]) for i in range(4)]
    ax_hist = fig.add_subplot(gs[1, :])
    all_axes = axes + [ax_hist]

    for ax in all_axes:
        ax.set_facecolor(PANEL)
        for spine in ax.spines.values():
            spine.set_edgecolor(BORDER)
        ax.tick_params(colors=MUTED, labelsize=7)
        ax.xaxis.label.set_color(MUTED)
        ax.yaxis.label.set_color(MUTED)

    ax_t, ax_s, ax_l, ax_r = axes
    year_min, year_max = int(year_counts.index.min()), int(year_counts.index.max())

    ax_t.bar(year_counts.index, year_counts.values, color=BLUE, width=0.8)
    ax_t.set_title("Papers by Year", color=TEXT, fontsize=9, pad=6)
    ax_t.set_xlabel("Year")
    ax_t.set_ylabel("Hit papers")
    ax_t.set_xlim(year_min - 1, year_max + 1)

    top_n = 18
    top_sf = sf_raw.head(top_n)
    labels = [n[:34] + "…" if len(n) > 34 else n for n in top_sf.index[::-1]]
    ax_s.barh(range(top_n), top_sf.values[::-1], color=BLUE, height=0.7)
    ax_s.set_yticks(range(top_n))
    ax_s.set_yticklabels(labels, fontsize=5.5)
    ax_s.set_title("Top Subfields", color=TEXT, fontsize=9, pad=6)
    ax_s.set_xlabel("Hit papers")

    for vals, label, color in [
        (np.sort(author_hits.values), "Authors", BLUE),
        (np.sort(sf_raw.values), "Subfields", "#f59e0b"),
        (np.sort(year_counts.values), "Years", "#8b5cf6"),
    ]:
        cumshare = np.cumsum(vals) / vals.sum()
        ax_l.plot(
            np.linspace(0, 1, len(cumshare)),
            cumshare,
            label=f"{label} (G={gini(vals):.2f})",
            color=color,
            linewidth=1.4,
        )
    ax_l.plot([0, 1], [0, 1], color=BORDER, linewidth=0.8, linestyle="--")
    ax_l.set_title("Lorenz Curves", color=TEXT, fontsize=9, pad=6)
    ax_l.set_xlabel("Cumulative share of entities")
    ax_l.set_ylabel("Cumulative share of hit papers")
    ax_l.legend(fontsize=7, framealpha=0, labelcolor=TEXT, loc="upper left")

    ax_r.plot(
        hit_rate.index,
        hit_rate.values * 100,
        color=BLUE,
        linewidth=1.5,
        marker="o",
        markersize=3,
    )
    ax_r.set_title("Hit Rate by Year", color=TEXT, fontsize=9, pad=6)
    ax_r.set_xlabel("Year")
    ax_r.set_ylabel("Hit papers (%)")
    ax_r.set_xlim(year_min - 1, year_max + 1)

    # Histogram of citation counts (log10 scale)
    ax_hist.hist(
        np.log10(citations + 1), bins=50, color=BLUE, edgecolor=BORDER, linewidth=0.5
    )
    ax_hist.set_title(
        "Citation Count Distribution (log₁₀)", color=TEXT, fontsize=9, pad=6
    )
    ax_hist.set_xlabel("log₁₀(citing citations + 1)")
    ax_hist.set_ylabel("Hit papers")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, facecolor=BG)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def build_html(img_b64: str, stat_items: list[tuple[str, str]]) -> str:
    stat_html = "".join(
        f'<div style="background:#1a1d27;border:1px solid #374151;border-radius:8px;'
        f'padding:12px 20px;text-align:center;min-width:130px">'
        f'<div style="color:#9ca3af;font-size:11px;margin-bottom:4px">{label}</div>'
        f'<div style="color:#e5e7eb;font-size:20px;font-weight:700">{value}</div>'
        f"</div>"
        for label, value in stat_items
    )
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hit Paper Distribution</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f1117; color: #e5e7eb; font-family: system-ui, sans-serif;
         display: flex; flex-direction: column; align-items: center;
         padding: 24px 16px; gap: 18px; min-height: 100vh; }}
  h1 {{ font-size: 18px; font-weight: 600; color: #f9fafb; }}
  .ts {{ font-size: 12px; color: #6b7280; margin-top: 2px; }}
  .stats {{ display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }}
  img {{ max-width: 100%; border-radius: 8px; border: 1px solid #374151; }}
</style>
</head>
<body>
  <div style="text-align:center">
    <h1>Hit Paper Distribution</h1>
    <div class="ts">{ts}</div>
  </div>
  <div class="stats">{stat_html}</div>
  <img src="data:image/png;base64,{img_b64}" alt="Hit paper charts">
</body>
</html>
"""


if __name__ == "__main__":
    gr = GenReaderExt()
    sf_names = list(gr.get_names(EntC.SUBFIELDS))

    hpm = load_map("hit-papers", Steps.DERIVE_LINKS3)
    wyears = pd.Series(gr.load_arr_work_years()).astype(int) + START_YEAR
    all_citations = pd.Series(gr.load_arr_work_citing_counts())
    hit_df = (
        pd.Series(hpm)
        .rename("hit_id")
        .to_frame()
        .assign(
            year=wyears,
            citations=all_citations,
        )
    )

    def filter_wdf(df):
        return df["idx"].isin(hit_df.index)

    work_subfields = df_from_varr(
        gr.load_varr_work_subfields_sizes(),
        gr.load_varr_work_subfields_targets(),
    ).loc[filter_wdf]

    work_authors = df_from_varr(
        gr.load_varr_work_filtered_authors_sizes(),
        gr.load_varr_work_filtered_authors_targets(),
    ).loc[filter_wdf]

    year_counts = hit_df["year"].value_counts().sort_index()
    all_wid_year_counts = wyears.value_counts().sort_index()
    hit_rate = year_counts / all_wid_year_counts

    # Citation threshold analysis
    hit_papers_above_threshold = (hit_df["citations"] >= CITATION_THRESHOLD).sum()
    all_papers_above_threshold = (all_citations >= CITATION_THRESHOLD).sum()

    hit_rate_above = (
        hit_papers_above_threshold / len(hit_df) * 100 if len(hit_df) > 0 else 0
    )
    all_rate_above = (
        all_papers_above_threshold / len(all_citations) * 100
        if len(all_citations) > 0
        else 0
    )

    sf_raw = work_subfields.groupby("val")["idx"].nunique().sort_values(ascending=False)
    sf_raw.index = [
        sf_names[i] if i < len(sf_names) else f"sf_{i}" for i in sf_raw.index
    ]

    author_hits = work_authors.groupby("val")["idx"].nunique()

    stat_items = [
        ("Hit Papers", f"{len(hit_df):,}"),
        ("Unique Authors", f"{work_authors['val'].nunique():,}"),
        ("Year Range", f"{int(hit_df['year'].min())}–{int(hit_df['year'].max())}"),
        ("Gini (Authors)", f"{gini(author_hits.values):.3f}"),
        ("Gini (Subfields)", f"{gini(sf_raw.values):.3f}"),
        ("Gini (Years)", f"{gini(year_counts.values):.3f}"),
        (
            f"Hit Papers >{CITATION_THRESHOLD} cites",
            f"{hit_papers_above_threshold:,} ({hit_rate_above:.1f}%)",
        ),
        (
            f"All Papers >{CITATION_THRESHOLD} cites",
            f"{all_papers_above_threshold:,} ({all_rate_above:.1f}%)",
        ),
    ]

    img_b64 = build_figure(
        year_counts, sf_raw, author_hits, hit_df["citations"].values, hit_rate
    )
    html = build_html(img_b64, stat_items)

    out_path = "docs/hit-paper-dist.html"
    with open(out_path, "w") as f:
        f.write(html)
    print(f"Exported → {out_path}")
