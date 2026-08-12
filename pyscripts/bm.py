"""Local throughput + memory benchmark; auto-compares against rankless-main."""

import datetime as dt
import re
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import psutil
from ccl_science_data.common import oa_root, snap_dir
from ccl_science_data.gen import EntC

from pyscripts.cache_prompting import BatchRequester
from pyscripts.server_ops import (
    ServerConfig,
    ServerProcess,
    build_server,
    checkout,
    current_branch,
)

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
bm_root = "/tmp/dmove-bm"


class Benchmarker:
    def __init__(self) -> None:
        now = dt.datetime.now().strftime("%Y-%m-%d-%H-%M")
        self.dump_root = Path(bm_root) / now
        self.dump_root.mkdir(parents=True)
        self.log_p = self.dump_root / "bm.log"
        self.server: Optional[ServerProcess] = None
        self.resps_act_df: Optional[pd.DataFrame] = None
        self.memory_recs: list[dict] = []

        self.log_dfs: list[pd.DataFrame] = []
        self.resp_dfs: list[pd.DataFrame] = []
        self.mem_dfs: list[pd.DataFrame] = []
        self.stats: list[dict] = []
        self.size_dfs: list[pd.DataFrame] = []

    def setup(self):
        subprocess.run(["make", "clean-cache"], check=True)
        build_server()
        self.server = ServerProcess(ServerConfig(data_root=oa_root))
        self.server.assert_port_free()
        self.server.start(self.log_p)
        self.server.wait_ready()
        self.add_memory_rec("started")

    def run_requests(self):
        requester = BatchRequester(min_citations=1000, big_limit=40 * 4)
        qs = [0.5, 0.70, 0.85, 0.95]
        bins = [0, *[requester.urled_sample["cut_basis"].quantile(q) / 1e6 for q in qs]]
        proc_counts = [12, 8, 4, 2, 1]
        n = 250
        for run_id in range(1, 3):
            requester.set_ext_dic({"run": run_id})
            requester.do_rest(bins, proc_counts, {"random_state": 742, "n": n})
        self.resps_act_df = requester.get_resps_df()
        self.add_memory_rec("post-requests")

    def close(self):
        branch = current_branch()
        logs = self.server.stop()
        setup = re.compile(r"set-up in (\d+)s").findall(logs)[0]
        # authors(48941:1/Some(1950)): got roots in 0ms
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
        for _df, lst in [
            (
                pd.DataFrame(
                    speed_recs, columns=["rt", "dmid", "tid", "proc", "dur"]
                ).assign(dur=lambda df: df["dur"].astype(int)),
                self.log_dfs,
            ),
            (pd.DataFrame(self.resps_act_df), self.resp_dfs),
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
            lst.append(_df.assign(branch=branch))

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
            checkout(MAIN_BRANCH)
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
            resp_df.groupby(["branch", "run", "rt"])
            .agg({"time": time_aggers, "size": time_aggers})
            .pipe(
                lambda df: pd.concat(
                    [
                        df.loc[:, "time"].pipe(_sub_agger, 1000),
                        df.loc[:, "size"].pipe(_sub_agger, 0.0001),
                        log_df.groupby(["branch", "rt", "proc"])["dur"]
                        .agg(time_aggers)
                        .reset_index()
                        .rename(columns={"proc": "run"}),
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

    def add_memory_rec(self, stage: str) -> None:
        proc = psutil.Process(self.server.pid)
        mem_info = proc.memory_info()
        self.memory_recs.append(
            {"rss": mem_info.rss, "vms": mem_info.vms, "stage": stage}
        )


def _sub_agger(df: pd.DataFrame, mul):
    return (
        df.astype(float)
        .pipe(lambda df: df * mul)
        .reset_index()
        .assign(run=lambda _df: _df["run"].apply(lambda e: f"resp_time_run{e}"))
    )


def p99(s):
    return np.quantile(s, 0.99)


def main() -> None:
    bmer = Benchmarker()
    bmer.setup()
    bmer.run_requests()
    bmer.close()


if __name__ == "__main__":
    main()
