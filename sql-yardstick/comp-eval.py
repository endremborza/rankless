import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load project .env before ccl_science_data imports its own, so OA_ROOT etc. are correct.
load_dotenv(override=True)

import pandas as pd
import requests
from ccl_science_data.common import EntC, load_map

from pyscripts.cache_prompting import (
    RTC,
    SIDC,
    TIDC,
    BatchRequester,
    addr,
    get_specs_and_ys,
)

con = os.environ["PG_CONSTR"]

flask_url = "http://localhost:5000/impact-tree"
keys = ["linkCount", "sourceCount"]


def get_diff_df(flask_dic, rs_dic, bd_etypes, oa_id_map):
    flask_rows = flatten_child(
        flask_dic["children"], etypes=bd_etypes, oa_id_map=oa_id_map
    )
    rs_rows = flatten_child(rs_dic["tree"]["children"])

    flask_df = (
        pd.DataFrame(flask_rows)
        .set_index("path")
        .rename(columns=lambda s: f"flask_{s}")
    )
    rs_df = (
        pd.DataFrame(rs_rows).set_index("path")
        if rs_rows
        else pd.DataFrame(columns=["path", *keys]).set_index("path")
    )

    df = flask_df.merge(rs_df, left_index=True, right_index=True, how="outer").fillna(0)
    for c in keys:
        df[f"{c}_diff"] = df[c] - df[f"flask_{c}"]
        flask_col = df[f"flask_{c}"].replace(0, float("nan"))
        df[f"{c}_relerr"] = (df[f"{c}_diff"].abs() / flask_col).fillna(0)
    return df


def cc_to_id(s: str):
    if s is None or s == "None":
        return 0
    return sum([ord(c) * 0x100**i for i, c in enumerate(s)])


def flatten_child(children: dict, prefix=[], etypes=None, oa_id_map=None):
    out = []
    next_etypes = None
    et_dic = None
    if etypes is not None and oa_id_map is not None and etypes[0] in oa_id_map:
        next_etypes = etypes[1:]
        et_dic = oa_id_map[etypes[0]]
    elif etypes is not None:
        next_etypes = etypes[1:]
    for k, v in children.items():
        display_k = k
        if et_dic is not None:
            if etypes[0] == EntC.COUNTRIES:
                kint = cc_to_id(k)
            else:
                kint = int(k)
            try:
                display_k = et_dic[kint]
            except KeyError:
                pass  # keep raw key if unmapped
        if "children" in v:
            out.extend(
                flatten_child(
                    v["children"],
                    [*prefix, display_k],
                    next_etypes,
                    oa_id_map=oa_id_map,
                )
            )
        out.append(
            {sk: v.get(sk) for sk in keys}
            | {"path": "-".join(map(str, [*prefix, display_k]))}
        )
    return out


def print_result(cr: "CompResult", min_flask_link: int = 2):
    print("\n" + "-" * 49)
    print("payload:", cr.payload)
    if cr.error is not None:
        print("ERROR:", cr.error)
        return

    df = cr.diff_df
    n_flask_only = (df["linkCount"] == 0).sum()
    n_rs_only = (df["flask_linkCount"] == 0).sum()
    matched = df.loc[(df["linkCount"] > 0) & (df["flask_linkCount"] > 0)]
    n_both = len(matched)

    print(f"flask {cr.flask_time:.2f}s  rs {cr.rs_time:.2f}s")
    if cr.root_summary:
        print(f"root: {cr.root_summary}")
    print(f"nodes: {n_both} matched  {n_flask_only} flask-only  {n_rs_only} rs-only")

    if n_both > 0:
        for c in keys:
            med_relerr = matched[f"{c}_relerr"].median()
            max_relerr = matched[f"{c}_relerr"].max()
            # Pearson correlation on matched nodes
            corr = matched[c].corr(matched[f"flask_{c}"])
            print(
                f"  {c}: median_relerr={med_relerr:.1%}  max_relerr={max_relerr:.1%}  corr={corr:.3f}"
            )

        # Worst nodes with enough flask data to be meaningful
        sig = matched.loc[matched["flask_linkCount"] >= min_flask_link]
        if len(sig) > 0:
            worst = sig.nlargest(5, "linkCount_relerr")[
                [
                    "flask_linkCount",
                    "linkCount",
                    "linkCount_diff",
                    "linkCount_relerr",
                    "flask_sourceCount",
                    "sourceCount",
                    "sourceCount_relerr",
                ]
            ]
            print(f"worst 5 (flask_linkCount>={min_flask_link}) by linkCount_relerr:")
            print(worst.to_string())


@dataclass
class CompResult:
    payload: dict
    error: Exception | None
    diff_df: pd.DataFrame | None = None
    flask_time: float | None = None
    rs_time: float | None = None
    root_summary: str | None = None


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
                EntC.TOPICS,
            ]
        }

        self.br = BatchRequester(min_citations=1000)
        self.specs, _ = get_specs_and_ys()

    def iter_comparisons(self, root_type: str, oa_ids, max_bds: int = 3):
        match_recs = []
        for oa_id in oa_ids:
            mapper_url = f"{addr}/v1/sem-id-via-oa/{root_type}/{oa_id}"
            resp = requests.get(mapper_url)
            sem_id = resp.json()[0]
            match_recs.append({SIDC: sem_id, RTC: root_type, "oa_id": oa_id})

        matched_df = pd.DataFrame(match_recs).merge(self.br.urled_sample)

        for _, rec in matched_df.loc[lambda df: df["bds"] == max_bds].iterrows():

            url = rec["url"]
            oa_id = rec["oa_id"]
            bds = self.specs[root_type][rec[TIDC]]["breakdowns"]
            flask_bds = [
                {"node": bd["attributeType"], "sourceSide": bd["sourceSide"]}
                for bd in bds
            ]
            bd_etypes = [b["node"] for b in flask_bds]

            # skip breakdown types not yet supported by flask server
            supported = {
                "authors",
                "institutions",
                "countries",
                "sources",
                "subfields",
                "topics",
                "works",
            }
            if not all(et in supported for et in bd_etypes):
                print(f"skipping unsupported breakdown types: {bd_etypes}")
                continue

            payload = {
                "root_type": root_type,
                "root_id": oa_id,
                "breakdowns": flask_bds,
            }

            try:
                flask_resp = requests.post(flask_url, json=payload)
                flask_resp.raise_for_status()
                flask_dic = flask_resp.json()
            except Exception as e:
                yield CompResult(payload, e)
                continue

            rs_resp = requests.get(url)
            rs_dic = rs_resp.json()

            rs_tree = rs_dic["tree"]
            flask_root_ratio = (
                f"flask_lc={flask_dic['linkCount']} rs_lc={rs_tree['linkCount']} "
                f"flask_sc={flask_dic['sourceCount']} rs_sc={rs_tree['sourceCount']}"
            )

            yield CompResult(
                payload,
                None,
                get_diff_df(flask_dic, rs_dic, bd_etypes, self.oa_id_map),
                flask_resp.elapsed.total_seconds(),
                rs_resp.elapsed.total_seconds(),
                flask_root_ratio,
            )


inst_oa_ids = [
    78577930,
]

if __name__ == "__main__":
    comper = ReproEvaluator()

    comp_results = list(comper.iter_comparisons(EntC.INSTITUTIONS, inst_oa_ids))
    for cr in comp_results:
        print_result(cr)
