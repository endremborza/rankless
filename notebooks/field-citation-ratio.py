"""
Field Citation Ratio analysis.

Fits a per-subfield power-law citation model:
    citations ≈ alpha[subfield] * age^beta[subfield]

Default: export citation timeline HTML to docs/field-citations.html.
Pass --fit to train the model instead.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from ccl_science_data.common import EntC
from ccl_science_data.gen_reader_ext import GenReaderExt
from tqdm import tqdm

MIN_GROUP_SIZE = 20
TOP_PERCENTILE = 0.10


@dataclass
class FitConfig:
    discard_global_top: float = 0.005
    discard_sf_top: float = 0.005
    min_papers: int = 30
    min_cites: int = 120
    batch_size: int = 200_000
    max_age: float = 20.0
    lr: float = 0.001
    n_steps: int = 50


@dataclass
class FlatData:
    """Per-(work, subfield) arrays ready for model fitting."""

    flat_sfs: np.ndarray
    flat_cites: np.ndarray
    flat_ages: np.ndarray
    n_subfields: int
    valid_inds: np.ndarray
    dropped_subfields: frozenset


class FieldCitationModel:
    """Per-subfield power-law citation model: cites ≈ alpha * age^beta."""

    def __init__(
        self, alpha: np.ndarray, beta: np.ndarray, dropped_subfields: frozenset
    ) -> None:
        self.alpha = alpha
        self.beta = beta
        self.dropped_subfields = dropped_subfields

    @classmethod
    def fit(
        cls,
        data: FlatData,
        config: FitConfig = FitConfig(),
        device=None,
        seed: int | None = None,
    ) -> "FieldCitationModel":
        import torch
        import torch.nn.functional as F

        if device is None:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        nsfs = data.n_subfields
        bs = config.batch_size

        a = torch.randn(nsfs, requires_grad=True, device=device, dtype=torch.float32)
        b = torch.randn(nsfs, requires_grad=True, device=device, dtype=torch.float32)
        optimizer = torch.optim.Adam([a, b], lr=config.lr)

        t_wsufs = torch.empty((bs, nsfs), dtype=torch.float32, device=device)
        t_ages = torch.empty((bs, 1), dtype=torch.float32, device=device)
        t_wcites = torch.empty((bs,), dtype=torch.bfloat16, device=device)

        rng = np.random.RandomState(seed)
        valid_inds = data.valid_inds.copy()
        batch_starts = list(range(0, valid_inds.shape[0], bs))[:-1]

        for step in range(config.n_steps):
            rng.shuffle(valid_inds)
            sumloss = 0.0
            for i in batch_starts:
                stinds = valid_inds[i : i + bs]
                subset_long = torch.from_numpy(data.flat_sfs[stinds]).to(device).long()
                t_wsufs.zero_().scatter_(1, subset_long.unsqueeze(1), 1.0)
                t_ages.copy_(
                    torch.from_numpy(
                        data.flat_ages[stinds]
                        .astype(np.float32)
                        .clip(1, config.max_age)
                    ).view(-1, 1)
                )
                t_wcites.copy_(
                    torch.from_numpy(data.flat_cites[stinds].astype(np.float32)).to(
                        torch.bfloat16
                    )
                )

                optimizer.zero_grad()
                alpha = F.softplus(a)
                beta = torch.sigmoid(b)
                pred = (
                    torch.matmul(t_wsufs, alpha.view(-1, 1)) * t_ages
                ) ** torch.matmul(t_wsufs, beta.view(-1, 1))
                loss = torch.mean((pred - t_wcites.view(-1, 1)) ** 2)
                loss.backward()
                optimizer.step()
                sumloss += loss.item()

            print(f"step {step:3d}  loss={sumloss / len(batch_starts):.4f}")

        with torch.no_grad():
            alpha_np = F.softplus(a).cpu().numpy()
            beta_np = torch.sigmoid(b).cpu().numpy()

        alpha_np[list(data.dropped_subfields)] = np.nan
        beta_np[list(data.dropped_subfields)] = np.nan

        return cls(alpha_np, beta_np, data.dropped_subfields)

    def predict(self, subfield_ids: np.ndarray, ages: np.ndarray) -> np.ndarray:
        return self.alpha[subfield_ids] * ages ** self.beta[subfield_ids]

    def to_frame(self, subfield_names: list[str]) -> pd.DataFrame:
        return pd.DataFrame(
            {"alpha": self.alpha, "beta": self.beta}, index=subfield_names
        )


def compute_top_pct_stats(
    gr: GenReaderExt, min_papers: int = MIN_GROUP_SIZE
) -> pd.DataFrame:
    """
    For each (subfield, year) pair with >= min_papers works, compute mean and
    median citations over the top 10% of papers (by citation count).

    Uses the subfield→works reverse index to avoid expanding the full flat table.
    """
    wyears = gr.load_arr_work_years()
    wcits = gr.load_arr_work_citing_counts()
    sf_targets = gr.load_varr_subfield_works_targets()
    sf_sizes = gr.load_varr_subfield_works_sizes()
    sf_ancestors = gr.load_arr_subfield_ancestors()

    rows = []
    offset = 0
    for sf_id, sf_size in tqdm(list(enumerate(sf_sizes))):
        sz = int(sf_size)
        if sz == 0:
            continue

        wids = sf_targets[offset : offset + sz]
        years = wyears[wids]
        cites = wcits[wids]
        offset += sz

        field_id = int(sf_ancestors[sf_id])

        for yr in np.unique(years):
            yr_cites = cites[years == yr]
            if len(yr_cites) < min_papers:
                continue
            threshold = np.quantile(yr_cites, 1 - TOP_PERCENTILE)
            top = yr_cites[yr_cites >= threshold]
            rows.append(
                {
                    "subfield": sf_id,
                    "year": int(yr),
                    "field": field_id,
                    "mean_cites": float(top.mean()),
                    "median_cites": float(np.median(top)),
                    "n_papers": int(len(yr_cites)),
                }
            )
    return pd.DataFrame(rows)


def export_html(
    stats: pd.DataFrame,
    sf_names: list[str],
    field_names: list[str],
    output_path: str,
) -> None:
    """Export per-subfield citation timeline charts in a flexbox grid."""
    import base64
    import io

    import matplotlib.pyplot as plt

    subfields = sorted(stats["subfield"].unique())
    figs_html = []

    for sf in subfields:
        sf_data = stats[stats["subfield"] == sf].sort_values("year")
        field_id = int(sf_data["field"].iloc[0])

        fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
        ax.plot(sf_data["year"], sf_data["mean_cites"], color="steelblue", label="Mean", marker="o", markersize=4)
        ax.plot(sf_data["year"], sf_data["median_cites"], color="tomato", label="Median", marker="s", markersize=4)
        ax.set_xlabel("Year")
        ax.set_ylabel("Citations (top 10%)")
        ax.set_title(f"{sf_names[sf]}\n({field_names[field_id]})", fontsize=11)
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Encode as base64 data URL
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=100)
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode()
        plt.close(fig)

        figs_html.append(f'<img src="data:image/png;base64,{img_b64}" alt="fig-{sf}">')

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: sans-serif; margin: 20px; }}
        .container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(550px, 1fr)); gap: 20px; }}
        .figure {{ display: flex; justify-content: center; }}
        .figure img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <h1>Field Citation Ratios</h1>
    <div class="container">
        {"".join(f'<div class="figure">{fig_html}</div>' for fig_html in figs_html)}
    </div>
</body>
</html>
"""
    with open(output_path, "w") as f:
        f.write(html)
    print(f"Exported {len(subfields)} subfields → {output_path}")


def build_flat_data(
    wyears: np.ndarray,
    wcits: np.ndarray,
    flat_sfs: np.ndarray,
    wsf_sizes: np.ndarray,
    n_subfields: int,
    config: FitConfig = FitConfig(),
) -> FlatData:
    """Build per-(work, subfield) flat arrays and apply outlier filters."""
    act_year = wyears.max()
    work_ids = np.repeat(np.arange(len(wyears)), wsf_sizes)
    flat_cites = wcits[work_ids]
    flat_ages = (act_year - wyears[work_ids]).astype(np.float16)

    filt = (flat_cites > 0) & (
        flat_cites < np.quantile(wcits, 1 - config.discard_global_top)
    )

    # Sort by subfield for O(n log n) grouping instead of O(n * n_sfs)
    sort_idx = np.argsort(flat_sfs, kind="stable")
    sorted_sfs = flat_sfs[sort_idx]
    sorted_cites = flat_cites[sort_idx]
    boundaries = np.searchsorted(sorted_sfs, np.arange(n_subfields + 1))

    dropped = []
    sf_filt = np.ones(len(flat_sfs), dtype=bool)

    for sfid in range(n_subfields):
        lo, hi = int(boundaries[sfid]), int(boundaries[sfid + 1])
        sf_cites = sorted_cites[lo:hi]
        if len(sf_cites) < config.min_papers or sf_cites.sum() < config.min_cites:
            dropped.append(sfid)
            sf_filt[sort_idx[lo:hi]] = False
            continue
        q = np.quantile(sf_cites, 1 - config.discard_sf_top)
        outlier_orig_idx = sort_idx[lo:hi][sf_cites >= q]
        sf_filt[outlier_orig_idx] = False

    filt &= sf_filt
    return FlatData(
        flat_sfs=flat_sfs,
        flat_cites=flat_cites,
        flat_ages=flat_ages,
        n_subfields=n_subfields,
        valid_inds=np.where(filt)[0],
        dropped_subfields=frozenset(dropped),
    )


def residuals_by_age(
    model: FieldCitationModel,
    data: FlatData,
    config: FitConfig = FitConfig(),
    n_samples: int = 200_000,
    seed: int = 0,
) -> pd.DataFrame:
    """Mean and std of prediction error grouped by paper age."""
    rng = np.random.RandomState(seed)
    inds = rng.choice(
        data.valid_inds, size=min(n_samples, len(data.valid_inds)), replace=False
    )
    ages = data.flat_ages[inds].astype(float).clip(1, config.max_age)
    cites = data.flat_cites[inds].astype(float)
    pred = model.predict(data.flat_sfs[inds], ages)
    return (
        pd.DataFrame({"age": ages, "pred": pred, "cites": cites, "miss": pred - cites})
        .groupby("age")
        .agg(["mean", "std", "count"])
    )


def run_fit(gr: GenReaderExt) -> None:
    """Train the model and print diagnostics."""
    wyears = gr.load_arr_work_years()
    wcits = gr.load_arr_work_citing_counts()
    flat_sfs = gr.load_varr_work_subfields_targets()
    wsf_sizes = gr.load_varr_work_subfields_sizes()
    tsufs = gr.load_arr_topic_subfields()

    config = FitConfig()
    data = build_flat_data(
        wyears, wcits, flat_sfs, wsf_sizes, int(tsufs.max()) + 1, config
    )
    model = FieldCitationModel.fit(data, config)

    names = list(gr.get_names(EntC.SUBFIELDS))
    pdf = model.to_frame(names).sort_values("alpha", ascending=False)
    print(pdf.dropna().head(20))
    print(residuals_by_age(model, data, config))


if __name__ == "__main__":
    import sys

    gr = GenReaderExt(".")
    if "--fit" in sys.argv:
        run_fit(gr)
    else:
        sf_names = list(gr.get_names(EntC.SUBFIELDS))
        field_names = list(gr.get_names(EntC.FIELDS))
        stats = compute_top_pct_stats(gr)
        export_html(stats, sf_names, field_names, "docs/field-citations.html")
