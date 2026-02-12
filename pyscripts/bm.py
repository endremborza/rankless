import datetime as dt
import json
import re
import subprocess
import time
from io import BufferedWriter
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import psutil
import requests
from ccl_science_data.common import oa_root, snap_dir
from ccl_science_data.gen import EntC
from tqdm import tqdm

from pyscripts.cache_prompting import BatchRequester

test_sites = {
    EntC.AUTHORS: ["cesar-a-hidalgo", "balazs-lengyel"],
    EntC.SUBFIELDS: [
        "information-systems",
        "general-economics-econometrics-and-finance",
    ],
    EntC.COUNTRIES: ["hun", "swe", "chi"],
    EntC.SOURCES: [
        "american-economic-review",
        "ann-neurol",
        "papeis-avulsos-de-zoologia",
    ],
    EntC.INSTITUTIONS: ["budapesti-corvinus-egyetem", "mta-ok", "udec"],  # "upenn"],
}

MAIN_BRANCH = "rankless-main"

spec_url = "http://127.0.0.1:3038/v1/specs"
bm_root = "/tmp/dmove-bm"


class Benchmarker:
    def __init__(self) -> None:
        now = dt.datetime.now().strftime("%Y-%m-%d-%H-%M")
        self.dump_root = Path(bm_root) / now
        self.dump_root.mkdir(parents=True)
        self.popen: Optional[subprocess.Popen] = None
        self.log_p = self.dump_root / "bm.log"
        self.log_h: Optional[BufferedWriter] = None
        self.memory_recs = []
        self.resp_recs = []

        self.log_dfs = []
        self.resp_dfs = []
        self.mem_dfs = []
        self.stats = []
        self.size_dfs = []

    def setup(self):
        subprocess.Popen(["make", "clean-cache"]).wait()
        subprocess.Popen(["cargo", "build", "--release"]).wait()
        _assert_no_running_be()

        self.log_h = self.log_p.open("wb")
        self.p = subprocess.Popen(
            ["target/release/rankless-server", oa_root.as_posix()],
            stdout=self.log_h,
            stderr=subprocess.DEVNULL,
        )
        print("waiting for setup")
        time.sleep(2)
        for _ in tqdm(range(500)):
            try:
                specs = requests.get(spec_url)
                assert specs.ok
            except:
                time.sleep(3)
                assert self.p.poll() is None
                continue
            if specs.ok:
                break
            time.sleep(3)
        self.add_memory_rec("started")

    def run_requests(self):
        requester = BatchRequester()
        qs = [0.6, 0.75, 0.9]
        bins = [0, *[requester.urled_sample["cut_basis"].quantile(q) for q in qs]]
        proc_counts = [8, 4, 2, 1]
        for run_id in range(1, 3):
            requester.set_ext_dic({"run": run_id})
            requester.do_rest(bins, proc_counts, {"random_state": 742, "n": 5})
        self.resp_recs = requester.resps
        self.add_memory_rec("post-requests")

    def close(self):
        branch = (
            subprocess.check_output(["git", "branch", "--show-current"])
            .decode()
            .strip()
        )
        self.p.kill()
        self.log_h.close()
        logs = self.log_p.read_text()
        setup = re.compile(r"set-up in (\d+)s").findall(logs)[0]
        speed_recs = re.compile(r"([a-z]+)\((\d+)\:(\d+)/.*\)\: (.*) in (\d+)").findall(
            logs
        )
        sizes = subprocess.check_output(["du", "--max-depth=1", oa_root.as_posix()])
        cache_sizes = subprocess.check_output(
            ["du", "--max-depth=1", f"{oa_root}/cache"]
        )
        snap_size = (
            subprocess.check_output(["du", "--max-depth=0", snap_dir])
            .decode()
            .strip()
            .split()[0]
        )
        for _df, l in [
            (
                pd.DataFrame(
                    speed_recs, columns=["et", "eid", "tid", "proc", "dur"]
                ).assign(dur=lambda df: df["dur"].astype(int)),
                self.log_dfs,
            ),
            (pd.DataFrame(self.resp_recs), self.resp_dfs),
            (pd.DataFrame(self.memory_recs), self.mem_dfs),
            (
                pd.DataFrame(
                    re.findall(rf"(\d+).*{oa_root}/(.*)", sizes.decode())
                    + re.findall(r"(\d+).*(cache/.*)", cache_sizes.decode())
                    + [[snap_size, "snapshot"]],
                    columns=["size", "directory"],
                ).assign(size=lambda df: df["size"].astype(int)),
                self.size_dfs,
            ),
        ]:
            l.append(_df.assign(branch=branch))

        self.stats.append(
            {
                "recorded": dt.datetime.now().isoformat(),
                "setup_secs": setup,
                "oa_root": oa_root.as_posix(),
                "branch": branch,
            }
        )

        cache_root = oa_root / "cache"
        troot = self.dump_root / branch
        troot.parent.mkdir(exist_ok=True)
        subprocess.check_output(["mv", cache_root.as_posix(), troot.as_posix()])
        if branch != MAIN_BRANCH:
            subprocess.check_output(["git", "checkout", MAIN_BRANCH])
            self.setup()
            self.run_requests()
            self.close()
        else:
            self.write_all()

    def write_all(self):
        resp_df = pd.concat(self.resp_dfs)
        log_df = pd.concat(self.log_dfs)
        time_aggers = ["mean", "median", p99, "max"]
        agg_df = (
            resp_df.groupby(["branch", "eid", "run"])
            .agg({"time": time_aggers, "size": time_aggers})
            .pipe(
                lambda df: pd.concat(
                    [
                        df.loc[:, "time"]
                        .astype(float)
                        .pipe(lambda df: df * 1000)
                        .reset_index()
                        .assign(
                            run=lambda _df: _df["run"].apply(
                                lambda e: f"resp_time_run{e}"
                            )
                        ),
                        df.loc[:, "size"]
                        .astype(float)
                        .pipe(lambda df: df / 1000)
                        .reset_index()
                        .assign(
                            run=lambda _df: _df["run"].apply(
                                lambda e: f"resp_size_run{e}"
                            )
                        ),
                        log_df.groupby(["branch", "et", "proc"])["dur"]
                        .agg(["mean", "median", "max", p99])
                        .reset_index()
                        .rename(columns={"et": "eid", "proc": "run"}),
                    ]
                )
            )
        )
        for df, fname in [
            (pd.DataFrame(self.stats), "stats"),
            (log_df, "logs"),
            (resp_df, "resps"),
            (pd.concat(self.mem_dfs), "mem"),
            (pd.concat(self.size_dfs), "size"),
            (agg_df, "agg"),
        ]:
            df.to_csv(self.dump_root / f"{fname}.csv.gz", index=False)

    def add_memory_rec(self, stage):
        proc = psutil.Process(self.p.pid)
        mem_info = proc.memory_info()
        rec = {"rss": mem_info.rss, "vms": mem_info.vms, "stage": stage}
        self.memory_recs.append(rec)


def p99(s):
    return np.quantile(s, 0.99)


def _assert_no_running_be():
    try:
        requests.get(spec_url).json()
        raise RuntimeError("backend is running")
    except:
        pass


if __name__ == "__main__":
    bmer = Benchmarker()
    bmer.setup()
    bmer.run_requests()
    bmer.close()
