import numpy as np
import pandas as pd
import requests
from ccl_science_data.common import EntC, oa_root, StowC, np_dtype
from tqdm import tqdm

pref = "https://openalex.org/works/W"
oa_id = 5102416863

api_url = f"https://api.openalex.org/works?filter=author.id:A{oa_id}"

results = []
for page in tqdm(range(1, 10), desc="get works"):
    obj = requests.get(api_url + f"&page={page}").json()
    if not obj.get("results"):
        break
    results += obj["results"]

wids = set([np.uint64(int(r["id"][len(pref) :])) for r in results])
kind = EntC.WORKS
N = 1_000_000

filtered_works = []

for filp in sorted((oa_root / StowC.filter_steps).iterdir()):
    efil = filp / kind
    if efil.exists():
        with efil.open("rb") as fp:
            misses = wids.copy()
            for _ in tqdm(range(100_000), desc=f"reading {efil}"):
                arr = np.frombuffer(fp.read(8 * N), dtype=np_dtype(64))
                if len(arr) == 0:
                    break
                misses.difference_update(arr)
            for wid in misses:
                filtered_works.append([filp.name, wid])

print("total works in api: ", len(wids))


print(
    pd.DataFrame(filtered_works, columns=["fid", "wid"])["fid"]
    .value_counts()
    .sort_index()
)
