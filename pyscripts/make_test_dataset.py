import gzip
import json
import os
from pathlib import Path

import pandas as pd
from ccl_science_data.common import DN, PUBY, snap_dir
from ccl_science_data.gen import EntC
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

test_root = Path(os.environ["OA_TEST_ROOT"])

inst_names = [
    "Massachusetts Institute of Technology",
    "Corvinus University of Budapest",
    "Utrecht University",
    "Zhejiang University",
    "Toulouse School of Economics",
    "Northeastern University",
    "University of Cambridge",
    "University of Chile",
    "Hungarian Academy of Sciences",
    "Bocconi University",
    "Stanford University",
    "California Institute of Technology",
    "Howard Hughes Medical Institute",
]


def entity_files(e: str, src_dir: Path) -> list[Path]:
    rdir = src_dir / "data" / "jsonl" / e
    return [f for subd in rdir.iterdir() if subd.is_dir() for f in subd.iterdir()]


def get_inst_ids(inst_names):
    insts = []
    for jsf in tqdm(entity_files(EntC.INSTITUTIONS, snap_dir), EntC.INSTITUTIONS):
        with gzip.open(jsf) as gzp:
            insts.extend(
                json.loads(gl)
                for gl in gzp
                if any(n.encode() in gl for n in inst_names)
            )
    return (
        pd.DataFrame([{k: i[k] for k in ["id", DN]} for i in insts])
        .drop_duplicates(subset=DN)
        .set_index(DN)
        .loc[inst_names, "id"]
        .tolist()
    )


mini_snap = test_root / "mini-snapshot"
micro_snap = test_root / "micro-snapshot"
nano_snap = test_root / "nano-snapshot"

rest_ents = [
    EntC.DOMAINS,
    EntC.FIELDS,
    EntC.SUBFIELDS,
    EntC.PUBLISHERS,
    EntC.TOPICS,
]


def entity_filter(e: str, src_dir, target_dir, filter_fun=lambda x: True):
    for jsf in tqdm(entity_files(e, src_dir), e):
        olines = []
        with gzip.open(jsf) as gzp:
            for gl in gzp:
                jso = json.loads(gl)
                # return jso
                if filter_fun(jso):
                    # return jso
                    olines.append(gl)
        if len(olines) > 0:
            out_p = target_dir / jsf.relative_to(src_dir)
            out_p.parent.mkdir(exist_ok=True, parents=True)
            out_p.write_bytes(gzip.compress(b"".join(olines)))


class WFler:
    def __init__(self, oa_ids, minc=0, miny=0):
        self.oa_ids = oa_ids
        self.minc = minc
        self.miny = miny
        self.insts = []
        self.authors = []
        self.sources = []

    def __call__(self, jso):
        if jso.get("cited_by_count", 0) < self.minc:
            return False
        try:
            if jso[PUBY] < self.miny:
                return False
        except KeyError:
            return False

        ships = jso.get("authorships", [])
        if not any(
            i.get("id") in self.oa_ids for a in ships for i in a["institutions"]
        ):
            return False

        # Keep every entity this work references, not just the matching author, so no
        # co-author/institution/source renders as (unknown) in the generated dataset.
        for a in ships:
            self.insts.extend(i.get("id") for i in a["institutions"])
            aid = (a.get("author") or {}).get("id")
            if aid:
                self.authors.append(aid)
        self.sources.extend(
            (loc.get("source") or {}).get("id") for loc in jso["locations"]
        )
        return True

    def snowball(self, src_snap, target_snap):
        _sets = list(map(set, [self.authors, self.insts, self.sources]))
        for vset, e in zip(_sets, [EntC.AUTHORS, EntC.INSTITUTIONS, EntC.SOURCES]):
            print(e, len(vset) / 1e6)
            entity_filter(e, src_snap, target_snap, lambda e: e["id"] in vset)

        for e in rest_ents:
            entity_filter(e, src_snap, target_snap)


if __name__ == "__main__":
    intro_oa_ids = get_inst_ids(inst_names)
    micro_oa_ids = intro_oa_ids[:8]
    nano_oa_ids = intro_oa_ids[:3]
    test_root.mkdir(exist_ok=True)

    wfler = WFler(intro_oa_ids)
    entity_filter(EntC.WORKS, snap_dir, mini_snap, wfler)

    wfler.snowball(snap_dir, mini_snap)

    micro_wfler = WFler(micro_oa_ids, 10, 2010)
    entity_filter(EntC.WORKS, mini_snap, micro_snap, micro_wfler)
    micro_wfler.snowball(mini_snap, micro_snap)

    nano_wfler = WFler(nano_oa_ids, 15, 2016)
    entity_filter(EntC.WORKS, micro_snap, nano_snap, nano_wfler)
    nano_wfler.snowball(micro_snap, nano_snap)
