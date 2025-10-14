import json
from pathlib import Path

import pandas as pd
from ccl_science_data.common import EntC, GenReader, get_arr

asset_dir = Path("src/lib/assets/data")

scales = [130, 100]


def scaleri(s, i):
    return lambda x: round((x - s["min"]) / (s["max"] - s["min"]) * scales[i], 1)


def get_loc_inds(gr: GenReader):
    f_names = gr.get_names(EntC.FIELDS)
    our_full_names = [
        f"{sfn} - {f_names[fi]}"
        for sfn, fi in zip(
            gr.get_names(EntC.SUBFIELDS), get_arr(f"a2_init_atts/subfield-ancestors", 8)
        )
    ]
    return {v: i for i, v in enumerate(our_full_names)}


def get_maps(els, gr):
    idmap = {}
    locmap = {}
    our_inds = get_loc_inds(gr)
    for n in els["nodes"]:
        nd = n["data"]
        our_ind = our_inds[nd["full_name"]]
        idmap[nd["id"]] = our_ind
        locmap[our_ind] = [int(n["position"][k]) for k in ["x", "y"]]
    return idmap, locmap


def get_edges(els, idmap):
    es = []
    for e in els["edges"]:
        ed = e["data"]
        es.append(
            [idmap[ed[k]] for k in ["source", "target"]]
            + [round(ed["pspace_proximity"] * 100, 2)]
        )
    return es


if __name__ == "__main__":
    gr = GenReader()
    d = json.loads(Path("extern/Net02prox.cyjs").read_text())
    els = d["elements"]
    idmap, locmap = get_maps(els, gr)
    edges = get_edges(els, idmap)
    scis = (
        pd.DataFrame(locmap)
        .T.agg(["min", "max"])
        .pipe(lambda df: [df.loc[:, i].pipe(scaleri, i=i) for i in range(2)])
    )

    scaled_locs = {k: [scis[i](e) for i, e in enumerate(v)] for k, v in locmap.items()}

    hier_desc = {
        k: [
            [name, anc]
            for name, anc in zip(
                gr.get_names(k),
                map(int, get_arr(f"a2_init_atts/{k[:-1]}-ancestors", 8)),
            )
        ]
        for k in [EntC.SUBFIELDS, EntC.FIELDS]
    } | {EntC.DOMAINS: gr.get_names(EntC.DOMAINS)}

    nw_n2 = (
        pd.DataFrame(edges)
        .drop(2, axis=1)
        .pipe(
            lambda df: pd.concat(
                [
                    df.assign(v=10),
                    df.merge(
                        pd.DataFrame(edges)
                        .drop(2, axis=1)
                        .rename(columns=lambda e: e + 1)
                    )
                    .assign(v=1)
                    .drop(1, axis=1)
                    .rename(columns={2: 1}),
                ]
            )
        )
        .pipe(lambda df: pd.concat([df, df.rename(columns={0: 1, 1: 0})]))
        .drop_duplicates()
    )

    adj_m = (
        nw_n2.pipe(
            lambda df: df.assign(
                **{
                    f"e-{k}": pd.DataFrame(hier_desc[EntC.SUBFIELDS])
                    .loc[:, 1]
                    .reindex(df.loc[:, k])
                    .values
                    for k in range(2)
                }
            )
        )
        .loc[lambda df: df["e-0"] != df["e-1"]]
        .pivot_table(index="e-0", columns="e-1", values="v", aggfunc="sum")
        .fillna(0)
    )

    ordered_fs = [adj_m.sum().idxmin()]
    ordered_fs = [adj_m.sum().idxmax()]
    der = 1.1
    ordered_fs = [adj_m.sum().sort_values().pipe(lambda s: s.index[int(len(s) / der)])]
    while len(ordered_fs) < len(adj_m.columns):
        ordered_fs.append(
            adj_m.apply(lambda s: s / s.sum())
            .loc[ordered_fs, :]
            .drop(ordered_fs, axis=1)
            .sum()
            .idxmax()
        )

    Path(asset_dir, "concept-map.json").write_text(
        json.dumps({"nodes": scaled_locs, "edges": edges})
    )
    Path(asset_dir, "field-hierarchy.json").write_text(json.dumps(hier_desc))
    Path(asset_dir, "fields-ordered.json").write_text(
        json.dumps({int(v): i for i, v in enumerate(ordered_fs)})
    )
