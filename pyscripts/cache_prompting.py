import hashlib
import json
import os
import re
import time
from datetime import datetime
from multiprocessing import Pool
from urllib.parse import quote_plus

import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

from .server_ops import DEFAULT_BE_ADDR as DEFAULT_ADDR

year = 1950

SIDC = "semanticId"
RTC = "rt"
TIDC = "tid"
BDSC = "bds"


def parse_env_list(k, default):
    s = os.environ.get(k)
    if s is None:
        return default
    return list(map(int, s.split(",")))


load_dotenv(".env", override=True)

default_bins = [1.5 * 4, 3.5 * 4, 12 * 4]

BIG_LIMIT = float(os.environ.get("BIG_LIMIT", 80 * 4))
BINS = parse_env_list("RL_BINS", default_bins)
PROC_COUNTS = parse_env_list("RL_PROCS", [16, 8, 4, 1])

assert len(BINS) == (len(PROC_COUNTS) - 1)


class BatchRequester:
    def __init__(
        self, min_citations=100_000, big_limit=BIG_LIMIT, addr: str = DEFAULT_ADDR
    ) -> None:
        self.addr = addr
        self.big_limit = big_limit
        self.ext_dic = {}
        self.specs, _ = get_specs_and_ys(addr)
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
            .rename(columns={"dm_id": "index"})
            .pipe(add_be_urls, year, addr)
        )
        self.big_urls = self.urled_sample.loc[
            lambda df: df["cut_basis"] > self.big_limit * 1e6, "url"
        ].tolist()
        print("BIGS:", len(self.big_urls))
        self.resps = []

    def do_rest(
        self, bins=[0, *BINS], proc_counts=PROC_COUNTS, sampling_kwargs={"frac": 1.0}
    ):
        print("procs", proc_counts)
        print(f"n: {round(self.urled_sample.shape[0] / 1e3, 1)}k")
        for gid, gdf in tqdm(self.iter_gdfs(bins, proc_counts)):
            suburls = gdf.sample(**sampling_kwargs)["url"].tolist()
            self._run(suburls, gid)

    def do_big_prep(self):
        self._run([url + "&big_prep=true" for url in self.big_urls], 12)

    def do_big_read(self):
        self._run([url + "&big_read=true" for url in self.big_urls], 1)

    def set_ext_dic(self, d):
        self.ext_dic = d

    def get_resps_df(self):
        return pd.DataFrame(self.resps).merge(
            self.urled_sample.loc[:, [RTC, SIDC, TIDC, BDSC, "citations", "cut_basis"]]
        )

    def iter_gdfs(self, bins: list[float], labels: list):
        full_bins = [*bins, self.big_limit]
        print("running with bins ", [f"{e}M" for e in full_bins])
        mbins = [e * 1e6 for e in full_bins]
        return (
            self.urled_sample.assign(
                ccut=lambda df: pd.cut(df["cut_basis"], mbins, labels=labels)
            )
            .loc[lambda df: df["ccut"].notna()]
            .groupby("ccut", observed=True)
        )

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


CACHE_ACTIONS = ("prep", "read", "rest", "validate-all", "validate-bigs")


def add_arguments(parser) -> None:
    parser.add_argument("action", choices=CACHE_ACTIONS)


def run(args) -> None:
    """Warm or validate the server response cache. See `uv run -m pyscripts cache -h`."""
    runner = BatchRequester()
    dispatch = {
        "prep": runner.do_big_prep,
        "read": runner.do_big_read,
        "rest": runner.do_rest,
        "validate-all": lambda: validate(runner.urled_sample["url"].tolist()),
        "validate-bigs": lambda: validate(runner.big_urls),
    }
    assert set(dispatch) == set(CACHE_ACTIONS)  # choices and dispatch stay in lockstep
    dispatch[args.action]()
