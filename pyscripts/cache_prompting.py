import hashlib
import json
import re
import sys
import time
from urllib.parse import quote_plus
from datetime import datetime
from multiprocessing import Pool

import pandas as pd
import requests
from tqdm import tqdm

DEFAULT_ADDR = "http://127.0.0.1:3038"
year = 1950

SIDC = "semanticId"
RTC = "rt"
TIDC = "tid"
BDSC = "bds"


class BatchRequester:
    def __init__(
        self,
        min_citations=100_000,
        big_limit=80_000_000 * 4,
        addr: str = DEFAULT_ADDR,
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
        resdf = get_resdf(specs, addr, 100)
        self.urled_sample: pd.DataFrame = (
            resdf.merge(tid_df)
            .loc[lambda df: df["citations"] >= min_citations, :]
            .assign(cut_basis=lambda df: df["citations"] * df["bds"])
            .sort_values("cut_basis", ascending=False)
            .rename(columns={"dm_id": "index"})
            .pipe(add_be_urls, year, addr)
        )

        self.big_urls = self.urled_sample.loc[
            lambda df: df["cut_basis"] > big_limit, "url"
        ].tolist()
        self.resps = []

    def do_rest(
        self,
        bins=[0, 1_500_00 * 4, 3_500_000 * 4, 12_000_000 * 4],
        proc_counts=[16, 8, 4, 1],
        sampling_kwargs={"frac": 1.0},
    ):
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

    def iter_gdfs(self, bins: list[int], labels: list):
        return (
            self.urled_sample.assign(
                ccut=lambda df: pd.cut(
                    df["cut_basis"], [*bins, self.big_limit], labels=labels
                )
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
        except:
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
    sd = requests.get(f"{addr}/v1/specs").json()
    return sd["specs"], sd["yearBreaks"]


def validate(urls):
    list(map(resp_pipe, tqdm(urls)))


if __name__ == "__main__":
    do_big_prep = "cache_big_prep" in sys.argv
    do_big_read = "cache_big_read" in sys.argv
    do_rest = "cache_do_rest" in sys.argv

    validate_all = "cache_validate_all" in sys.argv
    validate_big = "cache_validate_bigs" in sys.argv

    runner = BatchRequester()

    if do_big_prep:
        runner.do_big_prep()

    if do_big_read:
        runner.do_big_read()

    if validate_big:
        validate(runner.big_urls)

    if do_rest:
        runner.do_rest()

    if validate_all:
        validate(runner.urled_sample["url"].tolist())
