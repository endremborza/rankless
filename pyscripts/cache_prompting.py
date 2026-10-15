"""Warm/validate the server response cache (single box, banded)."""

import hashlib
import json
import math
import os
import re
import time
from datetime import datetime
from multiprocessing import Pool
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

from wire.rankless_server.responses import TREE_SPECS

from .fleet.config import DEFAULT_MIN_CITATIONS
from .server_ops import DEFAULT_BE_ADDR as DEFAULT_ADDR

SIDC = "semanticId"
RTC = "rt"
TIDC = "tid"
BDSC = "bds"
DMIC = "dmId"


load_dotenv(".env", override=True)

# Size-band defaults, in millions of cut_basis (citations × breakdown count):
# a `warm` run computes the trees in (min, limit], its bins each requested with
# their procs in parallel. Banded runs get these as CLI flags — from
# data/warm.toml when driven (pyscripts/fleet), by hand otherwise.
DEFAULT_BINS = [1.5 * 4, 3.5 * 4, 12 * 4]
DEFAULT_PROCS = [16, 8, 4, 1]


class BatchRequester:
    def __init__(
        self,
        min_citations=DEFAULT_MIN_CITATIONS,
        addr: str = DEFAULT_ADDR,
    ) -> None:
        self.addr = addr
        self.ext_dic = {}
        wait_for_backend(addr)
        self.specs = TREE_SPECS["specs"]
        self.n_periods = len(TREE_SPECS["yearBreaks"])
        tid_df = pd.DataFrame(
            [
                {RTC: k, TIDC: i, BDSC: len(v["breakdowns"])}
                for k, ss in self.specs.items()
                for i, v in enumerate(ss)
            ]
        )
        resdf = get_resdf(self.specs, addr, 100)
        self.urled_sample: pd.DataFrame = (
            resdf.merge(tid_df)
            .loc[lambda df: df["citations"] >= min_citations, :]
            .assign(cut_basis=lambda df: df["citations"] * df["bds"])
            .sort_values("cut_basis", ascending=False)
            .pipe(add_be_urls, addr)
        )
        self.resps = []

    def warm(self, edges: list[float], procs: list[int], sampling_kwargs={"frac": 1.0}):
        """Request the trees between consecutive `edges` (M cut_basis), each bin
        with its `procs` in parallel."""
        print("procs", procs)
        print(f"n: {round(self.urled_sample.shape[0] / 1e3, 1)}k")
        for gid, gdf in tqdm(self.iter_gdfs(edges, procs)):
            suburls = gdf.sample(**sampling_kwargs)["url"].tolist()
            self._run(suburls, gid)

    def set_ext_dic(self, d):
        self.ext_dic = d

    def get_resps_df(self):
        return pd.DataFrame(self.resps).merge(
            self.urled_sample.loc[:, [RTC, SIDC, TIDC, BDSC, "citations", "cut_basis"]]
        )

    def iter_gdfs(self, edges: list[float], procs: list[int]):
        print("running with bins ", [f"{e}M" for e in edges])
        mbins = [e * 1e6 for e in edges]
        # Bands are labelled by index, then mapped to their proc count: two
        # bands may legitimately run the same number of procs, and pd.cut
        # rejects duplicate labels.
        bands = list(range(len(mbins) - 1))
        grouped = (
            self.urled_sample.assign(
                ccut=lambda df: pd.cut(df["cut_basis"], mbins, labels=bands)
            )
            .loc[lambda df: df["ccut"].notna()]
            .groupby("ccut", observed=True)
        )
        return ((procs[band], gdf) for band, gdf in grouped)

    def _run(self, urls, nprocs):
        if nprocs == 1:
            for url in tqdm(urls):
                self.resps.append(resp_pipe(url) | self.ext_dic)
        else:
            print(f"starting {len(urls)} with {nprocs} procs at {datetime.now()}")
            s = time.time()
            pool = Pool(nprocs)
            self.resps.extend([d | self.ext_dic for d in pool.map(resp_pipe, urls)])
            pool.terminate()
            pool.join()
            print(f"done in {round((time.time() - s) / 60 / 60, 2)} hours")


def _urlify(s, addr: str) -> str:
    qsid = quote_plus(s[SIDC])
    return f"{addr}/v1/trees/{s[RTC]}/{qsid}?tid={s[TIDC]}"


def parse_url(url):
    resp = requests.get(url)
    jsb = json.dumps(resp.json(), sort_keys=True).encode()
    rt, sid, tid = re.findall(r"trees/(.*)/(.*)\?tid=(\d+)", url)[0]
    return {
        "time": resp.elapsed.total_seconds(),
        "size": len(resp.content),
        "md5": hashlib.md5(jsb).hexdigest(),
        SIDC: sid,
        TIDC: int(tid),
        RTC: rt,
    }


def resp_pipe(url):
    for _ in range(15):
        try:
            return parse_url(url)
        except Exception:
            print(f"failed {url}")
            time.sleep(600)
    return {"fail": url}


def add_be_urls(df, addr: str = DEFAULT_ADDR):
    return df.assign(url=df.apply(lambda s: _urlify(s, addr), axis=1))


def cache_dir_of(data_root: str, rt: str, eid: int, tid: int) -> Path:
    # Mirrors TreeBasisState::cache_dir: $OA_ROOT/cache/<root type>/<eid>/<tid>/
    return Path(data_root) / "cache" / rt / str(eid) / str(tid)


def tree_cached(s, n_periods: int, data_root: str | None = None) -> bool:
    # The server writes one bare {pid}.zst per period as it walks the years
    # (wide-/shallow- variants alongside), so a kill mid-walk leaves a dir with
    # only the newest periods — done means all n_periods bare files are there.
    root = data_root or os.environ["OA_ROOT"]
    d = cache_dir_of(root, s[RTC], s[DMIC], s[TIDC])
    if not d.is_dir():
        return False
    return sum(1 for f in d.iterdir() if re.fullmatch(r"\d+\.zst", f.name)) >= n_periods


def get_resdf(specs, addr: str = DEFAULT_ADDR, step_size=100, max_n=25_000):
    resdfs = []
    for r in specs.keys():
        for ss in range(0, max_n, step_size):
            rjs = requests.get(
                f"{addr}/v1/slice/{r}/{ss}/{ss + step_size}",
                params={"sort": "citations"},
            ).json()["rows"]
            if len(rjs) == 0:
                break
            resdfs.append(pd.DataFrame(rjs).assign(rt=r))

    return pd.concat(resdfs).drop_duplicates([RTC, DMIC])


def wait_for_backend(addr: str = DEFAULT_ADDR) -> None:
    for _ in range(20):
        try:
            requests.get(f"{addr}/v1/specs").raise_for_status()
            return
        except Exception as _:
            time.sleep(120)
    raise RuntimeError("no running backend")


def validate(urls):
    list(map(resp_pipe, tqdm(urls)))


CACHE_ACTIONS = ("warm", "validate-all")


def main(
    action: Literal["warm", "validate-all"],
    *,
    min: float = 0.0,
    limit: float = math.inf,
    bins: list[float] = DEFAULT_BINS,
    procs: list[int] = DEFAULT_PROCS,
    min_citations: int = DEFAULT_MIN_CITATIONS,
) -> None:
    """Warm or validate the server response cache: --min/--limit band the run
    in M cut_basis, --bins/--procs set per-size-bin client parallelism."""
    if len(procs) != len(bins) + 1:
        raise SystemExit("--procs needs exactly one more entry than --bins")
    runner = BatchRequester(min_citations=min_citations)
    dispatch = {
        "warm": lambda: runner.warm([min, *bins, limit], procs),
        "validate-all": lambda: validate(runner.urled_sample["url"].tolist()),
    }
    assert set(dispatch) == set(CACHE_ACTIONS)  # choices and dispatch stay in lockstep
    dispatch[action]()
