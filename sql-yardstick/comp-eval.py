import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load project .env before ccl_science_data imports its own, so OA_ROOT etc. are correct.
load_dotenv(override=True)

import numpy as np
import pandas as pd
import requests
from ccl_science_data.common import EntC, load_map
from scipy.stats import spearmanr
from tqdm import tqdm

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

SNAPSHOT_PATH = Path(__file__).parent / "eval-snapshot.json"


def flatten_child(children: dict, prefix=[]):
    out = []
    for k, v in children.items():
        if "children" in v:
            out.extend(flatten_child(v["children"], [*prefix, k]))
        out.append(
            {sk: v.get(sk) for sk in keys} | {"path": "-".join(map(str, [*prefix, k]))}
        )
    return out


def get_diff_df(flask_dic, rs_dic):
    flask_rows = flatten_child(flask_dic["children"])
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
    df["depth"] = df.index.map(lambda p: p.count("-"))
    for c in keys:
        df[f"{c}_diff"] = df[c] - df[f"flask_{c}"]
        flask_col = df[f"flask_{c}"].replace(0, float("nan"))
        df[f"{c}_relerr"] = (df[f"{c}_diff"].abs() / flask_col).fillna(0)
        df[f"{c}_relbias"] = (df[f"{c}_diff"] / flask_col).fillna(
            0
        )  # signed: RS - flask
    return df


def _fmtn(v, fmt=".3f") -> str:
    return (
        f"{v:{fmt}}"
        if v is not None and not (isinstance(v, float) and np.isnan(v))
        else "n/a"
    )


def print_result(cr: "CompResult", min_flask_link: int = 2):
    print("\n" + "-" * 49)
    tid_str = f"  tid={cr.tid}" if cr.tid is not None else ""
    print(f"payload:{tid_str}", cr.payload)
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
            med_bias = matched[f"{c}_relbias"].median()
            corr = matched[c].corr(matched[f"flask_{c}"])
            print(
                f"  {c}: median_relerr={med_relerr:.1%}  bias={med_bias:+.1%}"
                f"  max_relerr={max_relerr:.1%}  corr={corr:.3f}"
            )

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
    flask_root: tuple[int, int] | None = None  # (linkCount, sourceCount)
    rs_root: tuple[int, int] | None = None
    tid: int | None = None

    @property
    def root_match_ratio(self) -> float:
        if self.flask_root is None or self.rs_root is None:
            return 0.0
        fl, rl = self.flask_root[0], self.rs_root[0]
        return min(fl, rl) / max(fl, rl) if max(fl, rl) > 0 else 1.0


class ReproEvaluator:
    def __init__(self, upper_bound=20_000 * 4) -> None:
        self.br = BatchRequester(min_citations=1000, big_limit=upper_bound)
        self.specs, _ = get_specs_and_ys()
        self.supported = {
            EntC.AUTHORS,
            EntC.INSTITUTIONS,
            EntC.COUNTRIES,
            EntC.SOURCES,
            EntC.SUBFIELDS,
            EntC.TOPICS,
            EntC.WORKS,
        }

    def iter_comparisons(self, root_type: str, oa_ids, bd_nums: list[int] = [3, 4]):
        match_recs = []
        for oa_id in oa_ids:
            mapper_url = f"{addr}/v1/sem-id-via-oa/{root_type}/{oa_id}"
            resp = requests.get(mapper_url)
            sem_id = resp.json()[0]
            match_recs.append({SIDC: sem_id, RTC: root_type, "oa_id": oa_id})

        matched_df = pd.DataFrame(match_recs).merge(self.br.urled_sample)

        for _, rec in tqdm(
            list(matched_df.loc[lambda df: df["bds"].isin(bd_nums)].iterrows()),
            desc=root_type,
        ):
            url = rec["url"]
            oa_id = rec["oa_id"]
            tid = int(rec[TIDC])
            bds = self.specs[root_type][rec[TIDC]]["breakdowns"]
            flask_bds = [
                {"node": bd["attributeType"], "sourceSide": bd["sourceSide"]}
                for bd in bds
            ]
            bd_etypes = [b["node"] for b in flask_bds]

            if not all(et in self.supported for et in bd_etypes):
                # print(f"skipping unsupported breakdown types: {bd_etypes}")
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
                yield CompResult(payload, e, tid=tid)
                continue

            rs_resp = requests.get(url)
            rs_dic = rs_resp.json()

            rs_tree = rs_dic["tree"]
            flask_root = (flask_dic["linkCount"], flask_dic["sourceCount"])
            rs_root = (rs_tree["linkCount"], rs_tree["sourceCount"])
            flask_root_ratio = (
                f"flask_lc={flask_root[0]} rs_lc={rs_root[0]} "
                f"flask_sc={flask_root[1]} rs_sc={rs_root[1]}"
            )

            yield CompResult(
                payload,
                None,
                get_diff_df(flask_dic, rs_dic),
                flask_resp.elapsed.total_seconds(),
                rs_resp.elapsed.total_seconds(),
                flask_root_ratio,
                flask_root,
                rs_root,
                tid=tid,
            )


def _compute_group_stats(valid: list[CompResult]) -> dict:
    all_dfs = pd.concat([cr.diff_df for cr in valid])
    matched = all_dfs.loc[(all_dfs["linkCount"] > 0) & (all_dfs["flask_linkCount"] > 0)]
    n_total = len(all_dfs)
    n_matched = len(matched)
    n_flask_only = int((all_dfs["linkCount"] == 0).sum())
    n_rs_only = int((all_dfs["flask_linkCount"] == 0).sum())

    stats: dict = {
        "n_comparisons": len(valid),
        "n_total": n_total,
        "n_matched": n_matched,
        "n_flask_only": n_flask_only,
        "n_rs_only": n_rs_only,
        "node_match_rate": n_matched / n_total if n_total > 0 else 0.0,
        "tids": [cr.tid for cr in valid if cr.tid is not None],
        "metrics": {},
    }

    if n_matched > 0:
        per_comp_corrs: dict[str, list] = {c: [] for c in keys}
        per_comp_spearman: dict[str, list] = {c: [] for c in keys}
        for cr in valid:
            df = cr.diff_df
            m = df.loc[(df["linkCount"] > 0) & (df["flask_linkCount"] > 0)]
            if len(m) >= 3:
                for c in keys:
                    r = m[c].corr(m[f"flask_{c}"])
                    if pd.notna(r):
                        per_comp_corrs[c].append(float(r))
                    sr, _ = spearmanr(m[c], m[f"flask_{c}"])
                    if not np.isnan(sr):
                        per_comp_spearman[c].append(float(sr))

        for c in keys:
            pool_r = matched[c].corr(matched[f"flask_{c}"])
            pool_rho, _ = spearmanr(matched[c], matched[f"flask_{c}"])
            mean_r = (
                float(pd.Series(per_comp_corrs[c]).mean())
                if per_comp_corrs[c]
                else None
            )
            mean_rho = (
                float(pd.Series(per_comp_spearman[c]).mean())
                if per_comp_spearman[c]
                else None
            )

            depth_stats: dict = {}
            for d in sorted(matched["depth"].unique()):
                dm = matched.loc[matched["depth"] == d]
                if len(dm) < 2:
                    continue
                dr = dm[c].corr(dm[f"flask_{c}"])
                depth_stats[int(d)] = {
                    "n": int(len(dm)),
                    "med_err": float(dm[f"{c}_relerr"].median()),
                    "med_bias": float(dm[f"{c}_relbias"].median()),
                    "pool_pearson": float(dr) if pd.notna(dr) else None,
                }

            stats["metrics"][c] = {
                "med_err": float(matched[f"{c}_relerr"].median()),
                "mean_err": float(matched[f"{c}_relerr"].mean()),
                "p90": float(matched[f"{c}_relerr"].quantile(0.9)),
                "med_bias": float(matched[f"{c}_relbias"].median()),
                "pool_pearson": float(pool_r) if pd.notna(pool_r) else None,
                "mean_pearson": mean_r,
                "pool_spearman": float(pool_rho) if not np.isnan(pool_rho) else None,
                "mean_spearman": mean_rho,
                "by_depth": depth_stats,
            }

    root_lc_errs, root_sc_errs = [], []
    for cr in valid:
        if cr.flask_root and cr.rs_root:
            fl, rl = cr.flask_root[0], cr.rs_root[0]
            fs, rs_ = cr.flask_root[1], cr.rs_root[1]
            if fl > 0:
                root_lc_errs.append(abs(rl - fl) / fl)
            if fs > 0:
                root_sc_errs.append(abs(rs_ - fs) / fs)
    if root_lc_errs:
        stats["root_err"] = {
            "lc_median": float(pd.Series(root_lc_errs).median()),
            "lc_mean": float(pd.Series(root_lc_errs).mean()),
            "sc_median": float(pd.Series(root_sc_errs).median()),
            "sc_mean": float(pd.Series(root_sc_errs).mean()),
        }

    return stats


def _print_group_stats(label: str, stats: dict) -> None:
    n_comp = stats["n_comparisons"]
    n_total = stats["n_total"]
    n_matched = stats["n_matched"]
    n_flask_only = stats["n_flask_only"]
    n_rs_only = stats["n_rs_only"]
    match_rate = stats["node_match_rate"]

    print(f"\n  [{label}] {n_comp} comparisons")
    print(
        f"  nodes: {n_total} total  {n_matched} matched  {n_flask_only} flask-only  {n_rs_only} rs-only"
    )
    if n_total > 0:
        print(f"  node match rate: {match_rate:.1%}")

    for c in keys:
        m = stats["metrics"].get(c)
        if not m:
            continue
        print(
            f"  {c}: med_err={m['med_err']:.1%}  bias={m['med_bias']:+.1%}"
            f"  mean_err={m['mean_err']:.1%}  p90={m['p90']:.1%}"
        )
        print(
            f"    pearson: pool={_fmtn(m.get('pool_pearson'))}  mean={_fmtn(m.get('mean_pearson'))}"
            f"  spearman: pool={_fmtn(m.get('pool_spearman'))}  mean={_fmtn(m.get('mean_spearman'))}"
        )
        bd = m.get("by_depth")
        if bd:
            parts = [
                f"d{d}(n={ds['n']}, err={ds['med_err']:.0%}, bias={ds['med_bias']:+.0%})"
                for d, ds in bd.items()
            ]
            print("    by_depth: " + "  ".join(parts))

    re = stats.get("root_err")
    if re:
        print(
            f"  root_lc_err: med={re['lc_median']:.1%}  mean={re['lc_mean']:.1%}"
            f"  root_sc_err: med={re['sc_median']:.1%}  mean={re['sc_mean']:.1%}"
        )


def _aggregate_group(label: str, results: list[CompResult]) -> dict | None:
    valid = [cr for cr in results if cr.error is None and cr.diff_df is not None]
    if not valid:
        return None
    stats = _compute_group_stats(valid)
    _print_group_stats(label, stats)
    return stats


def print_aggregate(results: list[CompResult]) -> dict:
    valid = [cr for cr in results if cr.error is None and cr.diff_df is not None]
    groups: dict = {}
    if not valid:
        print("\nno valid results to aggregate")
        return groups

    print("\n" + "=" * 49)
    print("AGGREGATE RESULTS")
    print(f"comparisons: {len(valid)} successful / {len(results)} total")

    root_matched = [cr for cr in valid if cr.root_match_ratio > 0.9]
    root_mismatched = [cr for cr in valid if cr.root_match_ratio <= 0.9]

    if root_matched:
        g = _aggregate_group(f"root-matched (n={len(root_matched)})", root_matched)
        if g:
            groups["root_matched"] = g
    if root_mismatched:
        g = _aggregate_group(
            f"root-mismatched (n={len(root_mismatched)}, different dataset)",
            root_mismatched,
        )
        if g:
            groups["root_mismatched"] = g
    g = _aggregate_group("all", valid)
    if g:
        groups["all"] = g

    return groups


def _cr_summary(cr: CompResult) -> dict:
    base: dict = {
        "tid": cr.tid,
        "payload": cr.payload,
        "flask_root": list(cr.flask_root) if cr.flask_root else None,
        "rs_root": list(cr.rs_root) if cr.rs_root else None,
        "root_match_ratio": float(cr.root_match_ratio),
    }
    if cr.error is not None:
        base["error"] = str(cr.error)
        return base
    df = cr.diff_df
    matched = df.loc[(df["linkCount"] > 0) & (df["flask_linkCount"] > 0)]
    base["nodes"] = {
        "total": len(df),
        "matched": len(matched),
        "flask_only": int((df["linkCount"] == 0).sum()),
        "rs_only": int((df["flask_linkCount"] == 0).sum()),
    }
    for c in keys:
        if len(matched) > 0:
            r = matched[c].corr(matched[f"flask_{c}"])
            base[c] = {
                "med_err": float(matched[f"{c}_relerr"].median()),
                "med_bias": float(matched[f"{c}_relbias"].median()),
                "pool_pearson": float(r) if pd.notna(r) else None,
            }
    return base


def save_snapshot(results: list[CompResult], groups: dict) -> None:
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "comparisons": [_cr_summary(cr) for cr in results],
        "groups": groups,
    }
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2))
    print(f"\nsnapshot saved → {SNAPSHOT_PATH}")


def load_snapshot() -> dict | None:
    if SNAPSHOT_PATH.exists():
        return json.loads(SNAPSHOT_PATH.read_text())
    return None


def _fmt_delta(cur: float | None, prev: float | None, pct: bool = True) -> str:
    if cur is None or prev is None:
        return "n/a"
    fmt = ".1%" if pct else ".3f"
    delta = cur - prev
    sign = "+" if delta >= 0 else ""
    return f"{cur:{fmt}} ({sign}{delta:{fmt}})"


def print_comparison(current_groups: dict, prev_snapshot: dict) -> None:
    prev_groups = prev_snapshot.get("groups", {})
    prev_ts = prev_snapshot.get("timestamp", "unknown")
    print("\n" + "=" * 49)
    print(f"COMPARISON TO PREVIOUS RUN ({prev_ts[:19]})")

    for gk in ["root_matched", "root_mismatched", "all"]:
        cur = current_groups.get(gk)
        prev = prev_groups.get(gk)
        if not cur or not prev:
            continue
        print(f"\n  [{gk}]")
        print(
            f"  node_match_rate: {_fmt_delta(cur['node_match_rate'], prev['node_match_rate'])}"
        )
        print(
            f"  matched: {cur['n_matched']} (prev {prev['n_matched']})"
            f"  flask-only: {cur['n_flask_only']} (prev {prev['n_flask_only']})"
            f"  rs-only: {cur['n_rs_only']} (prev {prev['n_rs_only']})"
        )
        for c in keys:
            cm = cur.get("metrics", {}).get(c, {})
            pm = prev.get("metrics", {}).get(c, {})
            if not cm or not pm:
                continue
            print(
                f"  {c}: med_err={_fmt_delta(cm.get('med_err'), pm.get('med_err'))}"
                f"  bias={_fmt_delta(cm.get('med_bias'), pm.get('med_bias'))}"
                f"  pearson={_fmt_delta(cm.get('pool_pearson'), pm.get('pool_pearson'), pct=False)}"
            )
        cur_re = cur.get("root_err", {})
        prev_re = prev.get("root_err", {})
        if cur_re and prev_re:
            print(
                f"  root_lc_err: {_fmt_delta(cur_re.get('lc_median'), prev_re.get('lc_median'))}"
                f"  root_sc_err: {_fmt_delta(cur_re.get('sc_median'), prev_re.get('sc_median'))}"
            )


if __name__ == "__main__":

    inst_oa_ids = [78577930]
    comper = ReproEvaluator()
    oa_maps = {
        k: {v: k2 for k2, v in load_map(k).items()}
        for k in comper.br.urled_sample[RTC].unique()
    }
    bins = [0, 10_000 * 4]
    labels = [1, 2]

    eid_map = {EntC.INSTITUTIONS: set(inst_oa_ids)}
    for gid, gdf in comper.br.iter_gdfs(bins, labels):
        for _, row in gdf.sample(20, random_state=742).iterrows():
            etype = row[RTC]
            if etype not in eid_map.keys():
                eid_map[etype] = set()
            dm_id = row["dmId"]
            oa_id = oa_maps[etype][dm_id]
            eid_map[etype].add(oa_id)

    comp_results = []
    for etype, ids in eid_map.items():
        comp_results.extend(comper.iter_comparisons(etype, ids))
    for cr in comp_results:
        print_result(cr)

    groups = print_aggregate(comp_results)

    prev_snapshot = load_snapshot()
    save_snapshot(comp_results, groups)

    if prev_snapshot:
        print_comparison(groups, prev_snapshot)
