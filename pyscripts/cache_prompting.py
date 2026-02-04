import sys
import time
from datetime import datetime
from multiprocessing import Pool

import pandas as pd
import requests
from tqdm import tqdm

addr = "http://127.0.0.1:3038"
limit = 100_000
year = 1950


big_limit = 120_000_000
# 120G
# big_limit = 200_000_000

bins = [0, 1_500_000, 3_500_000, 12_000_000, big_limit]
proc_counts = [16, 8, 4, 1]
# 120G
# bins = [0, 5_000_000, 10_000_000, 30_000_000, big_limit]
# proc_counts = [20, 10, 5, 1]


def parse_resp(resp):
    return (resp.status_code, resp.elapsed.total_seconds(), len(resp.content), resp.url)


def resp_pipe(url):
    for _ in range(15):
        try:
            resp = requests.get(url)
            return parse_resp(resp)
        except:
            print(f"failed {url}")
            time.sleep(600)


def para_extend(urls, nprocs, extendable):
    if nprocs == 1:
        for url in tqdm(urls):
            extendable.append(resp_pipe(url))
    else:
        print(f"starting {len(urls)} with {nprocs} procs at {datetime.now()}")
        s = time.time()
        pool = Pool(nprocs)
        extendable.extend(pool.map(resp_pipe, urls))
        pool.terminate()
        pool.join()
        print(f"done in {round((time.time() - s) / 60 / 60, 2)} hours")


def urlify(s):
    return f"{addr}/v1/trees/{s['rt']}/{s['semanticId']}?tid={s['tid']}&year={year}"


def add_be_urls(df, year=1950):
    return df.assign(url=df.apply(urlify, axis=1))


def get_resdf(specs, step_size=100, max_n=25_000):
    resdfs = []
    for r in specs.keys():
        for ss in tqdm(range(0, max_n, step_size), r):
            rjs = requests.get(f"{addr}/v1/slice/{r}/{ss}/{ss+step_size}").json()
            if len(rjs) == 0:
                break
            resdfs.append(
                pd.DataFrame(rjs).assign(rt=r).drop("meta", axis=1, errors="ignore")
            )

    return pd.concat(resdfs).drop_duplicates()


def get_specs_and_ys():
    for _ in tqdm(range(100)):
        try:
            sd = requests.get(f"{addr}/v1/specs").json()
            return sd["specs"], sd["yearBreaks"]
        except:
            time.sleep(15)
    raise RuntimeError("no server")


def validate(urls):
    list(map(resp_pipe, tqdm(urls)))


if __name__ == "__main__":

    do_big_prep = "cache_big_prep" in sys.argv
    do_big_read = "cache_big_read" in sys.argv
    do_rest = "cache_do_rest" in sys.argv
    validate_all = "cache_validate_all" in sys.argv

    specs, ys = get_specs_and_ys()
    tid_df = pd.DataFrame(
        [
            {"rt": k, "tid": i, "bds": len(v["breakdowns"])}
            for k, ss in specs.items()
            for i, v in enumerate(ss)
        ]
    )
    rcounts = {r: len(v) for r, v in specs.items()}
    resdf = get_resdf(specs, 100)
    sample = (
        resdf.merge(tid_df)
        .sort_values(["citations", "bds"], ascending=False)
        .loc[lambda df: df["citations"] >= limit, :]
        .rename(columns={"dm_id": "index"})
    )

    urled_sample = sample.pipe(add_be_urls, year)
    big_urls = urled_sample.loc[lambda df: df["citations"] > big_limit, "url"].tolist()

    pexres = []
    if do_big_prep:
        para_extend([url + "&big_prep=true" for url in big_urls], 12, pexres)

    resps = []
    if do_big_read:
        para_extend([url + "&big_read=true" for url in big_urls], 1, resps)
        validate(big_urls)

    if do_rest:
        for gid, gdf in tqdm(
            urled_sample.assign(
                ccut=lambda df: pd.cut(df["citations"], bins, labels=proc_counts)
            )
            .loc[lambda df: df["ccut"].notna()]
            .groupby("ccut", observed=True)
        ):
            suburls = gdf.sample(frac=1.0)["url"].tolist()
            para_extend(suburls, gid, resps)
        validate(urled_sample["url"])

    if validate_all:
        all_urls = big_urls + urled_sample["url"].tolist()
        validate(all_urls)
