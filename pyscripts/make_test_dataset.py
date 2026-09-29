import gzip
import io
import json
import os
from collections import defaultdict
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from ccl_science_data.common import PUBY, snap_dir
from ccl_science_data.gen import EntC
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

test_root = Path(os.environ["OA_TEST_ROOT"])

# The full snapshot sits on one spinning disk: more readers only add seeks.
READERS = 16

OA = "https://openalex.org/"
INSTITUTIONS = {
    "Massachusetts Institute of Technology": "I63966007",
    "Corvinus University of Budapest": "I163245316",
    "Utrecht University": "I193662353",
    "Zhejiang University": "I76130692",
    "Toulouse School of Economics": "I4210092408",
    "Northeastern University": "I12912129",
    "University of Cambridge": "I241749",
    "University of Chile": "I69737025",
    "Hungarian Academy of Sciences": "I7597260",
    "Bocconi University": "I71209653",
    "Stanford University": "I97018004",
    "California Institute of Technology": "I122411786",
    "Howard Hughes Medical Institute": "I1344073410",
}

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

Refs = dict[str, set[str]]
Keep = Callable[[dict], bool]

_entity: str
_keep: Keep


@dataclass(frozen=True)
class WorkFilter:
    inst_ids: frozenset[str]
    minc: int = 0
    miny: int = 0

    def __call__(self, jso: dict) -> bool:
        return (
            (jso.get("cited_by_count") or 0) >= self.minc
            and (year := jso.get(PUBY)) is not None
            and year >= self.miny
            and any(
                i.get("id") in self.inst_ids
                for a in jso.get("authorships") or []
                for i in a.get("institutions") or []
            )
        )


@dataclass(frozen=True)
class IdFilter:
    ids: frozenset[str]

    def __call__(self, jso: dict) -> bool:
        return jso["id"] in self.ids


def keep_all(jso: dict) -> bool:
    return True


def entity_files(e: str, src_dir: Path) -> list[Path]:
    rdir = src_dir / "data" / "jsonl" / e
    return [f for subd in rdir.iterdir() if subd.is_dir() for f in subd.iterdir()]


def work_refs(jso: dict) -> Iterator[tuple[str, str | None]]:
    # Every entity a kept work references is kept, not just the matching author, so no
    # co-author/institution/source renders as (unknown) in the generated dataset.
    for a in jso.get("authorships") or []:
        yield EntC.AUTHORS, (a.get("author") or {}).get("id")
        for i in a.get("institutions") or []:
            yield EntC.INSTITUTIONS, i.get("id")
    for loc in jso.get("locations") or []:
        yield EntC.SOURCES, (loc.get("source") or {}).get("id")


def _init_reader(e: str, keep: Keep) -> None:
    global _entity, _keep
    _entity, _keep = e, keep


def _filter_part(jsf: Path, src_dir: Path, target_dir: Path) -> Refs:
    out_p = target_dir / jsf.relative_to(src_dir)
    refs: Refs = defaultdict(set)
    with ExitStack() as stack:
        # A whole-file read keeps concurrent readers sequential on a spinning disk.
        gzp = stack.enter_context(gzip.open(io.BytesIO(jsf.read_bytes())))
        out: gzip.GzipFile | None = None
        for gl in gzp:
            jso = json.loads(gl)
            if not _keep(jso):
                continue
            if out is None:
                out_p.parent.mkdir(exist_ok=True, parents=True)
                out = stack.enter_context(gzip.open(out_p, "wb"))
            out.write(gl)
            if _entity == EntC.WORKS:
                for ref_e, rid in work_refs(jso):
                    if rid:
                        refs[ref_e].add(rid)
    return refs


def entity_filter(
    e: str, src_dir: Path, target_dir: Path, keep: Keep = keep_all
) -> Refs:
    files = sorted(
        entity_files(e, src_dir), key=lambda f: f.stat().st_size, reverse=True
    )
    refs: Refs = defaultdict(set)
    with ProcessPoolExecutor(
        READERS, initializer=_init_reader, initargs=(e, keep)
    ) as ex:
        parts = [ex.submit(_filter_part, f, src_dir, target_dir) for f in files]
        for part in tqdm(as_completed(parts), e, total=len(files)):
            for ref_e, ids in part.result().items():
                refs[ref_e] |= ids
    return refs


def snowball(src_snap: Path, target_snap: Path, refs: Refs) -> None:
    for e in [EntC.AUTHORS, EntC.INSTITUTIONS, EntC.SOURCES]:
        print(e, len(refs[e]) / 1e6)
        entity_filter(e, src_snap, target_snap, IdFilter(frozenset(refs[e])))
    for e in rest_ents:
        entity_filter(e, src_snap, target_snap)


def make_subset(src_snap: Path, target_snap: Path, works: WorkFilter) -> None:
    refs = entity_filter(EntC.WORKS, src_snap, target_snap, works)
    snowball(src_snap, target_snap, refs)


if __name__ == "__main__":
    inst_ids = [OA + i for i in INSTITUTIONS.values()]
    make_subset(snap_dir, mini_snap, WorkFilter(frozenset(inst_ids)))
    make_subset(mini_snap, micro_snap, WorkFilter(frozenset(inst_ids[:8]), 10, 2010))
    make_subset(micro_snap, nano_snap, WorkFilter(frozenset(inst_ids[:3]), 15, 2016))
