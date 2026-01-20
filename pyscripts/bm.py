import datetime as dt
import hashlib
import json
import re
import subprocess
import time
from io import BufferedWriter
from itertools import product
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import psutil
import requests
from ccl_science_data.common import oa_root, snap_dir
from ccl_science_data.gen import EntC
from tqdm import tqdm

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

be_url = "http://127.0.0.1:3038/v1"
bm_root = "/tmp/dmove-bm"


class Benchmarker:
    def __init__(self) -> None:
        rev = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()[:8]
        now = dt.datetime.now().strftime("%Y-%m-%d-%H-%M")
        self.dump_root = Path(bm_root) / rev / now
        self.dump_root.mkdir(parents=True)
        self.popen: Optional[subprocess.Popen] = None
        self.log_p = self.dump_root / "bm.log"
        self.log_h: Optional[BufferedWriter] = None
        self.memory_recs = []
        self.resp_recs = []

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
        pbar = tqdm()
        while True:
            try:
                specs = requests.get(be_url + "/specs")
                assert specs.ok
            except:
                pbar.update()
                time.sleep(3)
                assert self.p.poll() is None
                continue
            if specs.ok:
                break
            time.sleep(3)
        pbar.close()
        self.add_memory_rec("started")

    def run_requests(self, sem_id_dic):
        specs = requests.get(be_url + "/specs")
        rcounts = {k: len(v) for k, v in specs.json()["specs"].items()}
        for run_id in range(1, 3):
            for rt, counts in rcounts.items():
                sem_ids = sem_id_dic.get(rt, [])
                for sem_id, tid in tqdm(
                    list(product(sem_ids, list(range(counts)))), desc=rt
                ):
                    for tid in range(counts):
                        url = f"{be_url}/trees/{rt}/{sem_id}?tid={tid}"
                        resp = requests.get(url)
                        assert resp.ok, url
                        jsb = json.dumps(resp.json(), sort_keys=True).encode()
                        self.resp_recs.append(
                            {
                                "time": resp.elapsed.total_seconds(),
                                "size": len(resp.content),
                                "md5": hashlib.md5(jsb).hexdigest(),
                                "sid": sem_id,
                                "tid": tid,
                                "eid": rt,
                                "run": run_id,
                            }
                        )
        self.add_memory_rec("post-requests")

    def close(self):
        self.p.kill()
        self.log_h.close()
        logs = self.log_p.read_text()
        setup = re.compile(r"set-up in (\d+)s").findall(logs)[0]
        speed_recs = re.compile(r"([a-z]+)\((\d+)\:(\d+)/.*\)\: (.*) in (\d+)").findall(
            logs
        )
        log_df = pd.DataFrame(
            speed_recs, columns=["et", "eid", "tid", "proc", "dur"]
        ).assign(dur=lambda df: df["dur"].astype(int))
        log_df.to_csv(self.dump_root / "logs.csv.gz", index=False)
        resp_df = pd.DataFrame(self.resp_recs)
        resp_df.to_csv(self.dump_root / "resps.csv.gz", index=False)
        mem_df = pd.DataFrame(self.memory_recs)
        mem_df.to_csv(self.dump_root / "mem.csv.gz", index=False)
        stats = {
            "recorded": dt.datetime.now().isoformat(),
            "setup_secs": setup,
            "oa_root": oa_root.as_posix(),
        }
        (self.dump_root / "stats.json").write_text(json.dumps(stats))
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
        time_aggers = ["mean", "median", p99, "max"]
        subprocess.check_output(
            ["mv", (oa_root / "cache").as_posix(), self.dump_root.as_posix()]
        )
        agg_df = (
            resp_df.groupby(["eid", "run"])
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
                        log_df.groupby(["et", "proc"])["dur"]
                        .agg(["mean", "median", "max", p99])
                        .reset_index()
                        .rename(columns={"et": "eid", "proc": "run"}),
                    ]
                )
            )
        )
        sizes_df = pd.DataFrame(
            re.findall(rf"(\d+).*{oa_root}/(.*)", sizes.decode())
            + re.findall(r"(\d+).*(cache/.*)", cache_sizes.decode())
            + [[snap_size, "snapshot"]],
            columns=["size", "directory"],
        ).assign(size=lambda df: df["size"].astype(int))
        agg_df.to_csv(self.dump_root / "agg.csv.gz", index=False)
        sizes_df.to_csv(self.dump_root / "size.csv.gz", index=False)

    def add_memory_rec(self, stage):
        proc = psutil.Process(self.p.pid)
        mem_info = proc.memory_info()
        rec = {"rss": mem_info.rss, "vms": mem_info.vms, "stage": stage}
        self.memory_recs.append(rec)


def p99(s):
    return np.quantile(s, 0.99)


def _assert_no_running_be():
    try:
        requests.get(be_url + "/specs").json()
        raise RuntimeError("backend is running")
    except:
        pass


if __name__ == "__main__":
    test_set = json.loads(Path("extern/test-semids.json").read_text())
    bmer = Benchmarker()
    bmer.setup()
    bmer.run_requests(test_sites)
    bmer.close()
