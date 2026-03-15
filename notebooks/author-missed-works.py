import numpy as np
import pandas as pd
import requests
from ccl_science_data.common import EntC, StowC, iter_dfs, np_dtype, oa_root, parse_id
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

res_df = (
    pd.DataFrame(results).assign(wid=lambda df: parse_id(df["id"])).set_index("wid")
)

wids = set(res_df.index)
kind = EntC.WORKS
N = 1_000_000

filtered_works = []

in_dfs = []

for wdf in tqdm(iter_dfs(kind, cols=["id"])):
    in_dfs.append(wdf["id"].pipe(parse_id).loc[lambda s: s.isin(wids)])

in_df = pd.concat(in_dfs)
print(in_df.values, in_df.shape)

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
