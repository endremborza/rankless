import os
from dataclasses import dataclass

import pandas as pd
import requests
from ccl_science_data.common import EntC, load_map
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
keys = ["linkCount", "sourceCount"]


def get_diff_df(flask_dic, rs_dic, bd_etypes, oa_id_map):

    return (
        pd.DataFrame(flatten_child(flask_dic, etypes=bd_etypes, oa_id_map=oa_id_map))
        .set_index("path")
        .rename(columns=lambda s: f"flask_{s}")
        .merge(
            pd.DataFrame(flatten_child(rs_dic["tree"]["children"])),
            left_index=True,
            right_on="path",
            how="outer",
        )
        .fillna(0)
        .pipe(
            lambda df: df.assign(
                **{f"{c}_diff": df[c] - df[f"flask_{c}"] for c in keys}
            )
        )
        .set_index("path")
    )


def cc_to_id(s: str):
    if s is None or s == "None":
        return 0
    return sum([ord(c) * 0x100**i for i, c in enumerate(s)])


def flatten_child(children: dict, prefix=[], etypes=None, oa_id_map=None):
    out = []
    next_etypes = None
    et_dic = None
    if etypes is not None:
        next_etypes = etypes[1:]
        et_dic = oa_id_map[etypes[0]]
    for k, v in children.items():
        if et_dic is not None:
            if etypes[0] == EntC.COUNTRIES:
                kint = cc_to_id(k)
            else:
                kint = int(k)
            try:
                k = et_dic[kint]
            except KeyError:
                print(k, etypes)
        if "children" in v.keys():
            out.extend(
                flatten_child(
                    v["children"], [*prefix, k], next_etypes, oa_id_map=oa_id_map
                )
            )
        out.append(
            {sk: v.get(sk) for sk in keys} | {"path": "-".join(map(str, [*prefix, k]))}
        )
    return out


@dataclass
class CompResult:
    payload: dict
    error: Exception | None
    diff_df: pd.DataFrame | None = None
    flask_time: float | None = None
    rs_time: float | None = None


class ReproEvaluator:
    def __init__(self) -> None:
        self.oa_id_map = {
            k: load_map(k)
            for k in [
                EntC.INSTITUTIONS,
                EntC.COUNTRIES,
                EntC.AUTHORS,
                EntC.SOURCES,
                EntC.SUBFIELDS,
            ]
        }

        self.br = BatchRequester(min_citations=1000)
        self.specs, _ = get_specs_and_ys()

    def iter_comparisons(self, root_type: str, oa_ids):
        match_recs = []
        for oa_id in oa_ids:
            mapper_url = f"{addr}/v1/sem-id-via-oa/{root_type}/{oa_id}"
            resp = requests.get(mapper_url)
            sem_id = resp.json()[0]
            match_recs.append({SIDC: sem_id, RTC: root_type, "oa_id": oa_id})

        matched_df = pd.DataFrame(match_recs).merge(self.br.urled_sample)

        for _, rec in matched_df.loc[lambda df: df["bds"] == 3].iterrows():

            url = rec["url"]
            oa_id = rec["oa_id"]
            bds = self.specs[root_type][rec[TIDC]]["breakdowns"]
            flask_bds = [
                {"node": bd["attributeType"], "sourceSide": bd["sourceSide"]}
                for bd in bds
            ]
            bd_etypes = [b["node"] for b in flask_bds]

            payload = {
                "root_type": root_type,
                "root_id": oa_id,
                "breakdowns": flask_bds,
            }

            try:
                flask_resp = requests.post(flask_url, json=payload)
                flask_dic = flask_resp.json()
            except Exception as e:
                yield CompResult(payload, e)
                continue

            rs_resp = requests.get(url)
            rs_dic = rs_resp.json()

            yield CompResult(
                payload,
                None,
                get_diff_df(flask_dic, rs_dic, bd_etypes, self.oa_id_map),
                flask_resp.elapsed.total_seconds(),
                rs_resp.elapsed.total_seconds(),
            )


inst_oa_ids = [
    78577930,
]

comper = ReproEvaluator()

comp_results = list(comper.iter_comparisons(EntC.INSTITUTIONS, inst_oa_ids))

# %%
for cr in comp_results:
    print("\n" * 2 + "-" * 49)
    print("evaluation for payload", cr.payload)
    if cr.error is None:
        print("success:")
        print("nodes compared:")
        print(cr.diff_df.head())
        print("diffs:")
        print(cr.diff_df.describe())
    else:
        print("error:")
        print(cr.error)
