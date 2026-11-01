"""Served author names a curator should look at (`uv run -m pyscripts author-names`).

OpenAlex keeps some display names the way a byline printed them: in capitals, or behind a
title. Which of them is wrong is a judgement ("MR Grever" is initials, by the derived
ledger's capital-block rule), so this only lists them, in `releases/<run_id>.names.tsv`:
owners first, since they see their own name, then by citations. A fix is a curated
`name_author` line in the kept ledger. `refresh-data` runs it last.
"""

import csv
import os
import re
from collections import Counter
from pathlib import Path

import numpy as np
from ccl_science_data.gen import Steps
from dotenv import load_dotenv

from pyscripts import paths
from pyscripts.fleet import manifest
from wire.rankless_rs.derived_ledger import CAPITAL_BLOCK_MAX, TITLES
from wire.rankless_rs.user_ledger import OWNER_PINS

load_dotenv()
COLUMNS = ("flag", "oa_id", "name", "orcid", "cites", "owner")
_WORDS = re.compile(r"[\s.,]+")
_TITLES = frozenset(TITLES)


def main(*, root: str | None = None) -> Path:
    """List the served author names written in capitals or carrying a title."""
    data = Path(root or os.environ["OA_ROOT"])
    owners = set((data / paths.USER_LEDGER_DIR / OWNER_PINS).read_text().split())
    rows = sorted(
        (
            (flag, f"A{oa}", name, orcid, cites, orcid in owners)
            for oa, name, orcid, cites in _authors(data)
            for flag in flags(name)
        ),
        key=lambda r: (not r[5], -r[4]),
    )
    out = data / "releases" / f"{manifest.run_id(str(data))}.names.tsv"
    out.parent.mkdir(exist_ok=True)
    with out.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(COLUMNS)
        writer.writerows((*r[:5], "owner" if r[5] else "") for r in rows)
    counts = Counter(r[0] for r in rows)
    print(f"author names flagged: {dict(counts)} -> {out}")
    for flag, oa, name, orcid, _, owner in rows:
        if owner:
            print(f"  owner {flag} {oa} {name} {orcid}")
    return out


def flags(name: str) -> list[str]:
    """`caps` for a name in capitals with a word longer than an initial, `title` for one
    with a title among its words."""
    words = [w for w in _WORDS.split(name) if w]
    found = []
    if name.isupper() and any(sum(c.isalpha() for c in w) > 1 for w in words):
        found.append("caps")
    if any(_is_title(w) for w in words):
        found.append("title")
    return found


def _is_title(word: str) -> bool:
    capital_block = len(word) <= CAPITAL_BLOCK_MAX and word.isascii() and word.isupper()
    return not capital_block and "".join(filter(str.isalnum, word)).lower() in _TITLES


def _authors(data: Path):
    """(oa id, name, ORCID, citations) of every served author, from the built attributes."""
    mapping = np.frombuffer(
        (data / Steps.ENTITY_MAPPING / "authors").read_bytes(), dtype=">u8"
    ).reshape(-1, 2)
    # dm ids run 1..N; an attribute file holds N + 2 slots
    slots = len(mapping) + 2
    atts = data / Steps.INIT_ATTS
    sizes = _column(atts / "authors-names" / "sizes", slots)
    ends = np.cumsum(sizes, dtype=np.uint64)
    starts = ends - sizes
    text = (atts / "authors-names" / "targets").read_bytes()
    orcids = (atts / "author-orcids").read_bytes()
    width = _width(len(orcids), slots, atts / "author-orcids")
    cites = _column(atts / "author-raw-cites", slots)
    for oa, dm in mapping.tolist():
        orcid = orcids[dm * width : (dm + 1) * width].rstrip(b"\0").decode()
        name = text[int(starts[dm]) : int(ends[dm])].decode()
        yield oa, name, orcid, int(cites[dm])


def _column(path: Path, slots: int) -> np.ndarray:
    raw = path.read_bytes()
    return np.frombuffer(raw, dtype=f">u{_width(len(raw), slots, path)}")


def _width(size: int, slots: int, path: Path) -> int:
    width, rest = divmod(size, slots)
    if rest:
        raise SystemExit(f"{path}: {size} bytes are not {slots} slots")
    return width
