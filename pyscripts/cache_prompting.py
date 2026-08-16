"""Warm/validate the server response cache (single box, banded)."""

import hashlib
import json
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

from .fleet.config import DEFAULT_BIG_CHUNK, DEFAULT_MIN_CITATIONS
from .server_ops import DEFAULT_BE_ADDR as DEFAULT_ADDR

year = 1950

SIDC = "semanticId"
RTC = "rt"
TIDC = "tid"
BDSC = "bds"
DMIC = "dmId"


load_dotenv(".env", override=True)

# Size-band defaults, in millions of cut_basis (citations × breakdown count).
# min..big_limit is a box's `rest` share, above big_limit is the `bigs` set
# (prep/read via /tmp/dmove-parts). Banded runs get these as CLI flags — from
# data/warm.toml when driven (pyscripts/fleet), by hand otherwise.
DEFAULT_BINS = [1.5 * 4, 3.5 * 4, 12 * 4]
DEFAULT_PROCS = [16, 8, 4, 1]
DEFAULT_BIG_LIMIT = 80.0 * 4


class BatchRequester:
    def __init__(
        self,
        min_citations=DEFAULT_MIN_CITATIONS,
        big_limit=DEFAULT_BIG_LIMIT,
        addr: str = DEFAULT_ADDR,
    ) -> None:
        self.addr = addr
        self.big_limit = big_limit
        self.ext_dic = {}
        self.specs, self.year_breaks = get_specs_and_ys(addr)
        self.n_periods = len(self.year_breaks)
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
            .pipe(add_be_urls, year, addr)
        )
        self.bigs = self.urled_sample.loc[
            lambda df: df["cut_basis"] > self.big_limit * 1e6
        ]
        self.big_urls = self.bigs["url"].tolist()
        print("BIGS:", len(self.big_urls))
        self.resps = []

    def do_rest(self, bins=None, proc_counts=None, sampling_kwargs={"frac": 1.0}):
        if bins is None:
            bins = [0, *DEFAULT_BINS]
        if proc_counts is None:
            proc_counts = DEFAULT_PROCS
        print("procs", proc_counts)
        print(f"n: {round(self.urled_sample.shape[0] / 1e3, 1)}k")
        for gid, gdf in tqdm(self.iter_gdfs(bins, proc_counts)):
            suburls = gdf.sample(**sampling_kwargs)["url"].tolist()
            self._run(suburls, gid)

    def do_bigs(self, chunk_size=DEFAULT_BIG_CHUNK):
        # Chunked prep→read: the server deletes each tree's /tmp/dmove-parts
        # after its read, so parts disk peaks at one chunk instead of every big
        # at once. Already-cached trees are skipped (prep/read bypass the cache,
        # so a plain rerun would recompute them) — rerunning resumes.
        rows = [s for _, s in self.bigs.iterrows()]
        todo = [s for s in rows if not tree_cached(s, self.n_periods)]
        print(f"bigs: {len(rows) - len(todo)} cached, {len(todo)} to compute")
        for i in range(0, len(todo), chunk_size):
            chunk = [s["url"] for s in todo[i : i + chunk_size]]
            self._run([url + "&big_prep=true" for url in chunk], len(chunk))
            self._run([url + "&big_read=true" for url in chunk], 1)

    def set_ext_dic(self, d):
        self.ext_dic = d

    def get_resps_df(self):
        return pd.DataFrame(self.resps).merge(
            self.urled_sample.loc[:, [RTC, SIDC, TIDC, BDSC, "citations", "cut_basis"]]
        )

    def iter_gdfs(self, bins: list[float], proc_counts: list):
        full_bins = [*bins, self.big_limit]
        print("running with bins ", [f"{e}M" for e in full_bins])
        mbins = [e * 1e6 for e in full_bins]
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
        return ((proc_counts[band], gdf) for band, gdf in grouped)

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


def _urlify(s, year: int, addr: str) -> str:
    qsid = quote_plus(s[SIDC])
    return f"{addr}/v1/trees/{s[RTC]}/{qsid}?tid={s[TIDC]}&year={year}"


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


def add_be_urls(df, year=1950, addr: str = DEFAULT_ADDR):
    return df.assign(url=df.apply(lambda s: _urlify(s, year, addr), axis=1))


def cache_dir_of(data_root: str, rt: str, eid: int, tid: int) -> Path:
    # Mirrors TreeBasisState::cache_dir: $OA_ROOT/cache/<root type>/<eid>/<tid>/
    return Path(data_root) / "cache" / rt / str(eid) / str(tid)


def tree_cached(s, n_periods: int, data_root: str | None = None) -> bool:
    # The server writes one bare {pid}.zst per period as it walks the years
    # (wide-/shallow- variants alongside), so a kill mid-read leaves a dir with
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
            rjs = requests.get(f"{addr}/v1/slice/{r}/{ss}/{ss + step_size}").json()
            if len(rjs) == 0:
                break
            resdfs.append(
                pd.DataFrame(rjs).assign(rt=r).drop("meta", axis=1, errors="ignore")
            )

    return pd.concat(resdfs).drop_duplicates()


def get_specs_and_ys(addr: str = DEFAULT_ADDR):
    for _ in range(20):
        try:
            sd = requests.get(f"{addr}/v1/specs").json()
            break
        except Exception as _:
            time.sleep(120)
    else:
        raise RuntimeError("no running backend")
    return sd["specs"], sd["yearBreaks"]


def validate(urls):
    list(map(resp_pipe, tqdm(urls)))


CACHE_ACTIONS = ("bigs", "rest", "validate-all", "validate-bigs")


def main(
    action: Literal["bigs", "rest", "validate-all", "validate-bigs"],
    *,
    min: float = 0.0,
    limit: float = DEFAULT_BIG_LIMIT,
    bins: list[float] = DEFAULT_BINS,
    procs: list[int] = DEFAULT_PROCS,
    chunk: int = DEFAULT_BIG_CHUNK,
    min_citations: int = DEFAULT_MIN_CITATIONS,
) -> None:
    """Warm or validate the server response cache: --min/--limit band the run
    in M cut_basis, --bins/--procs set per-size-bin client parallelism."""
    if len(procs) != len(bins) + 1:
        raise SystemExit("--procs needs exactly one more entry than --bins")
    runner = BatchRequester(min_citations=min_citations, big_limit=limit)
    dispatch = {
        "bigs": lambda: runner.do_bigs(chunk),
        "rest": lambda: runner.do_rest([min, *bins], procs),
        "validate-all": lambda: validate(runner.urled_sample["url"].tolist()),
        "validate-bigs": lambda: validate(runner.big_urls),
    }
    assert set(dispatch) == set(CACHE_ACTIONS)  # choices and dispatch stay in lockstep
    dispatch[action]()
