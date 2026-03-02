"""
Field Citation Ratio model.

Fits a per-subfield power-law citation model:
    citations ≈ alpha[subfield] * age^beta[subfield]

alpha (softplus-constrained): citation volume/rate for the subfield
beta  (sigmoid-constrained, ∈ (0,1)): citation growth exponent over time
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from tqdm import tqdm


from ccl_science_data.common import EntC
from ccl_science_data.gen_reader_ext import GenReaderExt


@dataclass
class FitConfig:
    discard_global_top: float = 0.01
    discard_sf_top: float = 0.01
    min_papers: int = 30
    min_cites: int = 120
    batch_size: int = 200_000
    max_age: float = 20.0
    lr: float = 0.001
    n_steps: int = 50


@dataclass
class FlatData:
    """Per-(work, subfield) arrays ready for model fitting."""

    flat_sfs: np.ndarray  # subfield ID per row
    flat_cites: np.ndarray  # citation count per row
    flat_ages: np.ndarray  # paper age in years per row
    n_subfields: int
    valid_inds: np.ndarray  # row indices passing all filters
    dropped_subfields: frozenset


class FieldCitationModel:
    """
    Per-subfield power-law citation model fit via SGD (MSE loss).

    Parameters alpha and beta are indexed by subfield ID, with NaN for
    subfields that were dropped during data preparation.
    """

    def __init__(
        self,
        alpha: np.ndarray,
        beta: np.ndarray,
        dropped_subfields: frozenset,
    ) -> None:
        self.alpha = alpha
        self.beta = beta
        self.dropped_subfields = dropped_subfields

    @classmethod
    def fit(
        cls,
        data: FlatData,
        config: FitConfig = FitConfig(),
        device: torch.device | None = None,
        seed: int | None = None,
    ) -> "FieldCitationModel":
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
            for i in tqdm(batch_starts, desc=f"step {step}"):
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
        """Expected citation count for given subfield IDs and paper ages."""
        return self.alpha[subfield_ids] * ages ** self.beta[subfield_ids]

    def to_frame(self, subfield_names: list[str]) -> pd.DataFrame:
        """DataFrame of per-subfield alpha/beta, indexed by name."""
        return pd.DataFrame(
            {"alpha": self.alpha, "beta": self.beta},
            index=subfield_names,
        )


def build_flat_data(
    wyears: np.ndarray,
    wcits: np.ndarray,
    flat_sfs: np.ndarray,
    wsf_sis: np.ndarray,
    n_subfields: int,
    config: FitConfig = FitConfig(),
) -> FlatData:
    """
    Build per-(work, subfield) flat arrays and apply outlier filters.

    Each work appears once per subfield it is assigned to. Subfields with
    too few papers or citations are dropped entirely from training.
    """
    act_year = wyears.max()
    n = flat_sfs.shape[0]
    print(n)
    flat_cites = np.zeros(n, dtype=wcits.dtype)
    flat_ages = np.zeros(n, dtype=np.float16)

    i = 0
    for wi, wsf_size in enumerate(tqdm(wsf_sis, desc="flattening")):
        age = act_year - wyears[wi]
        for _ in range(wsf_size):
            flat_cites[i] = wcits[wi]
            flat_ages[i] = age
            i += 1

    filt = (flat_cites > 0) & (
        flat_cites < np.quantile(wcits, 1 - config.discard_global_top)
    )

    dropped = []
    for sfid in tqdm(range(n_subfields), desc="filtering subfields"):
        sf_mask = flat_sfs == sfid
        if (
            sf_mask.sum() < config.min_papers
            or flat_cites[sf_mask].sum() < config.min_cites
        ):
            dropped.append(sfid)
            filt &= ~sf_mask
            continue
        filt &= ~(
            sf_mask
            & (
                flat_cites
                >= np.quantile(flat_cites[sf_mask], 1 - config.discard_sf_top)
            )
        )

    print(f"training rows: {filt.sum() / 1e6:.2f}M  dropped subfields: {len(dropped)}")
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


if __name__ == "__main__":
    gr = GenReaderExt(".")
    wyears = gr.load_arr_work_years()
    wcits = gr.load_arr_work_citing_counts()
    flat_sfs = gr.load_varr_work_subfields_targets()
    wsfs_sizes = gr.load_varr_work_subfields_sizes()
    tsufs = gr.load_arr_topic_subfields()

    config = FitConfig()
    data = build_flat_data(wyears, wcits, flat_sfs, wsfs_sizes, tsufs.max() + 1, config)
    model = FieldCitationModel.fit(data, config)

    names = list(gr.get_names(EntC.SUBFIELDS))
    pdf = model.to_frame(names).sort_values("alpha", ascending=False)
    print(pdf.head(20))
    print(pdf.tail(30))
    print(pdf.corr())

    diag = residuals_by_age(model, data, config)
    print(diag)
