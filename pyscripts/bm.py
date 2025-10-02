import datetime as dt
import json
import re
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
import requests
from ccl_science_data.common import oa_root
from ccl_science_data.gen import EntC
from tqdm import tqdm

test_sites = {
    EntC.AUTHORS: ["cesar-a-hidalgo"],
    EntC.SUBFIELDS: ["information-systems"],
    EntC.COUNTRIES: ["hun"],
    EntC.SOURCES: ["american-economic-review"],
    EntC.INSTITUTIONS: ["budapesti-corvinus-egyetem"],  # "upenn"],
}

do_sites = test_sites

be_url = "http://127.0.0.1:3038/v1"
bm_root = "/tmp/dmove-bm"


def p99(s):
    return np.quantile(s, 0.99)


def dump_bms():
    recs = []
    for bm_dir in Path("/tmp/dmove-bm").iterdir():
        _log_df = pd.read_csv(bm_dir / "logs.csv.gz")
        resp_df = pd.read_csv(bm_dir / "resps.csv.gz")

        agg_dic = (
            resp_df.groupby("eid")[["size", "time"]]
            .agg(["mean", "median", p99])
            .melt(ignore_index=False)
            .reset_index()
            .assign(id=lambda df: df.iloc[:, :3].apply("_".join, axis=1))
            .set_index("id")["value"]
            .to_dict()
        )

        _bmcache_sizes = pd.DataFrame(
            re.findall(
                "(\d+).*caches/(.*)",
                subprocess.check_output(
                    ["du", "--max-depth=1", f"{bm_dir}/cache"]
                ).decode(),
            ),
            columns=["size", "rev"],
        ).assign(size=lambda df: df["size"].astype(int))

        recs.append(json.loads((bm_dir / "stats.json").read_text()) | agg_dic)
    pd.DataFrame(recs).to_csv("bm-perf.csv")


if __name__ == "__main__":
    rev = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()[:6]
    rev_dir = Path(f"{bm_root}/{rev}")
    subprocess.check_output(["rm", "-rf", rev_dir.as_posix()])
    rev_dir.mkdir(parents=True)

    subprocess.Popen(["make", "clean-cache"]).wait()
    # subprocess.Popen(["make", "restart-service"]).wait()
    subprocess.Popen(["cargo", "build", "--release"]).wait()

    try:
        requests.get(be_url + "/specs")
        raise RuntimeError("backend is running")
    except:
        pass

    p = subprocess.Popen(
        ["target/release/rankless-server", oa_root.as_posix()],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    print("waiting for setup")
    time.sleep(10)
    pbar = tqdm()
    while True:
        try:
            specs = requests.get(be_url + "/specs")
        except:
            pbar.update()
            time.sleep(3)
            assert p.poll() is None
            continue
        if specs.ok:
            break
        time.sleep(3)
    pbar.close()

    proc = psutil.Process(p.pid)
    mem_info = proc.memory_info()
    rec = {"rss": mem_info.rss, "vms": mem_info.vms}
    resp_recs = []
    rcounts = {k: len(v) for k, v in specs.json()["specs"].items()}
    totals = {k: c * len(do_sites.get(k, [])) for k, c in rcounts.items()}

    for rt, counts in rcounts.items():
        pbar = tqdm(desc=rt, total=totals[rt])
        for sem_id in do_sites.get(rt, []):
            for tid in range(counts):
                resp = requests.get(f"{be_url}/trees/{rt}/{sem_id}?tid={tid}")
                assert resp.ok, f"{be_url}/trees/{rt}/{sem_id}?tid={tid}"
                resp_recs.append(
                    {
                        "time": resp.elapsed.total_seconds(),
                        "size": len(resp.content),
                        "sid": sem_id,
                        "tid": tid,
                        "eid": rt,
                    }
                )
                pbar.update()
        pbar.close()
    p.kill()
    out, err = p.communicate()
    setup = re.compile(r"set-up in (\d+)s").findall(out.decode())[0]
    speed_recs = re.compile(r"([a-z]+)\((\d+)\:(\d+)/.*\)\: (.*) in (\d+)").findall(
        out.decode()
    )
    pd.DataFrame(speed_recs, columns=["et", "eid", "tid", "proc", "dur"]).to_csv(
        f"{rev_dir}/logs.csv.gz", index=False
    )
    pd.DataFrame(resp_recs).to_csv(f"{rev_dir}/resps.csv.gz", index=False)
    (rev_dir / "stats.json").write_text(
        json.dumps(rec | {"recorded": dt.datetime.now().isoformat(), "setup": setup})
    )
    subprocess.check_output(["mv", (oa_root / "cache").as_posix(), rev_dir.as_posix()])
    dump_bms()
