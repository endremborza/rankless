import os

import pandas as pd
import requests
from dotenv import load_dotenv

from pyscripts.cache_prompting import (
    RTC,
    SIDC,
    TIDC,
    BatchRequester,
    addr,
    get_specs_and_ys,
)

load_dotenv()

con = os.environ["PG_CONSTR"]

flask_url = "http://localhost:5000/impact-tree"


# %%

br = BatchRequester(min_citations=1000)

# %%

specs, _ = get_specs_and_ys()

# %%

root_type = "institutions"

oa_ids = [
    78577930,
]

match_recs = []
for oa_id in oa_ids:
    mapper_url = f"{addr}/v1/sem-id-via-oa/{root_type}/{oa_id}"
    resp = requests.get(mapper_url)
    sem_id = resp.json()[0]
    match_recs.append({SIDC: sem_id, RTC: root_type, "oa_id": oa_id})

matched_df = pd.DataFrame(match_recs).merge(br.urled_sample)

# %%


for i, rec in matched_df.loc[lambda df: df["bds"] == 3].iterrows():
    pass

url = rec["url"]
oa_id = rec["oa_id"]
bds = specs[root_type][rec[TIDC]]["breakdowns"]
flask_bds = [
    {"node": bd["attributeType"], "sourceSide": bd["sourceSide"]} for bd in bds
]

payload = {
    "root_type": root_type,
    "root_id": oa_id,
    "breakdowns": flask_bds,
}

flask_resp = requests.post(flask_url, json=payload)
flask_dic = flask_resp.json()

rs_resp = requests.get(url)
rs_dic = rs_resp.json()

# %%

keys = ["linkCount", "sourceCount"]


def flatten_child(children: dict, prefix=[]):
    out = []
    for k, v in children.items():
        if "children" in v.keys():
            out.extend(flatten_child(v["children"], [k]))
        out.append(
            {sk: v.get(sk) for sk in keys} | {"path": "-".join(map(str, [*prefix, k]))}
        )
    return out


rs_dic.keys()
flask_dic.keys()
pd.DataFrame(flatten_child(flask_dic)).sort_values(keys[0], ascending=False)

# %%

pd.DataFrame(flatten_child(rs_dic["tree"]["children"])).sort_values(
    keys[0], ascending=False
)


# %%

flask_resp.elapsed.total_seconds(), rs_resp.elapsed.total_seconds()

# %%

bds

# %%

payload = {
    "root_type": "institutions",
    "root_id": 78577930,
    "breakdowns": [
        {"node": "subfields", "sourceSide": True},
        {"node": "countries", "sourceSide": False},
    ],
}

resp = requests.post(flask_url, json=payload)
resp.json()

# %%
