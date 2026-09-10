"""Author records that are a country, not a person (`uv run -m pyscripts country-authors <step>`).

OpenAlex credits countries — and the UN — with their own constitutions, legal codes,
development plans and UN documents, so records named `Hungary` or `Russian Federation`
sit in author search next to real researchers. They get no profile: their ids live in
`rankless_server/author_blacklist.txt` beside the people who asked for theirs to go, and
the server blanks the semantic id of everything listed there.

Which record is a country is a judgement, so both verdicts are data, in that file below
the marker line: `<oa_id> <name>` is a country record, `# cleared <oa_id> <name> — why`
is a person who happens to carry the name (three authors are named Hong Kong, one Monaco).
The name alone decides nothing.

    scan    match every author display name against the country names and report what the
            file leaves undecided; exits 1 when a record needs a verdict
    review  print an undecided record's papers, ask, and write the verdict back

The data-root readers are imported where they are used, so the file and its verdicts load
without `OA_ROOT`. Both steps read it though, so they run where a recalc runs; `review`
also needs a backend serving that same data root, for the papers it shows.
"""

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import partial
from multiprocessing import Pool
from pathlib import Path

from protocli import Dispatcher

from mcp_server import resolve_backend

BLACKLIST = "rankless_server/author_blacklist.txt"
MARKER = "# `uv run -m pyscripts country-authors` owns every line below."
CLEARED = "# cleared "
SCAN_WORKERS = 12
EVIDENCE_PAPERS = 6
# The entity list names each country once; OpenAlex also credits these variants. The UN
# is here for the same reason a country is — it authors its own documents. Sister bodies
# (WHO, the World Bank, the EC) are out of scope.
EXTRA_NAMES = (
    "Burma",
    "Cape Verde",
    "Cote d'Ivoire",
    "Côte d'Ivoire",
    "Czech Republic",
    "Great Britain",
    "Islamic Republic of Iran",
    "Korea",
    "Lao PDR",
    "Macedonia",
    "Republic of Korea",
    "Russian Federation",
    "Swaziland",
    "Syrian Arab Republic",
    "Turkey",
    "United Nations",
    "United States of America",
    "Viet Nam",
)


@dataclass(frozen=True)
class Record:
    name: str
    orcid: str
    works: int
    cites: int


def scan(*, blacklist: str = BLACKLIST) -> None:
    """Report what the blacklist does not decide about this snapshot's country-named records."""
    listed, cleared, _ = _parse(Path(blacklist))
    names = _country_names()
    rows = _match(names, set(listed))
    matched = {i: r for i, r in rows.items() if r.name.strip().lower() in names}
    in_app = _in_app(matched)

    undecided = {
        i: r for i, r in in_app.items() if i not in listed and i not in cleared
    }
    absent = sorted(set(listed) - set(rows))
    # rows carries the listed ids whatever they are named now; the ones the match set
    # dropped were renamed out of the country list.
    renamed = {i: (listed[i], rows[i].name) for i in rows.keys() - matched.keys()}

    print(f"country names: {len(names)} ({len(EXTRA_NAMES)} of them aliases)")
    print(
        f"records carrying one: {len(matched)} in the snapshot, {len(in_app)} in the app"
    )
    print(f"decided: {len(listed)} country, {len(cleared)} cleared")
    for oa_id in absent:
        print(f"  listed, absent from this snapshot: {oa_id} {listed[oa_id]}")
    for oa_id, (was, now) in renamed.items():
        print(f"  listed, no longer a country name: {oa_id} {was!r} -> {now!r}")
    if not undecided:
        print("undecided: none")
        return
    print(f"undecided: {len(undecided)}")
    for oa_id, rec in _by_size(undecided):
        print(f"  {_summary(oa_id, rec)}")
    raise SystemExit(
        f"\n{len(undecided)} record(s) need a verdict: "
        "uv run -m pyscripts country-authors review"
    )


def review(*, backend: str = "live", blacklist: str = BLACKLIST) -> None:
    """Show each undecided record's papers and ask; each answer is written back at once."""
    be_url, label = resolve_backend(backend)
    path = Path(blacklist)
    listed, cleared, _ = _parse(path)
    rows = _in_app(_match(_country_names(), set()))
    undecided = {i: r for i, r in rows.items() if i not in listed and i not in cleared}
    if not undecided:
        print("nothing to review")
        return

    print(f"{len(undecided)} to review, papers from {label} ({be_url})\n")
    for oa_id, rec in _by_size(undecided):
        print(f"\n{_summary(oa_id, rec)}")
        sem_id, papers = _evidence(be_url, oa_id)
        if sem_id is None:
            print("  not on this backend — point --backend at the data root's own")
            continue
        print(f"  /authors/{sem_id}")
        for year, cites, title in papers:
            print(f"    {year} c={cites} {title}")
        if input("  the country itself? [y/N] ").strip().lower() == "y":
            listed[oa_id] = rec.name
        else:
            cleared[oa_id] = f"{rec.name} — {input('  then what is it? ').strip()}"
        _write(path, listed, cleared)
    print(f"\n{len(listed)} country, {len(cleared)} cleared -> {path}")


_dispatcher = Dispatcher(
    "pyscripts country-authors",
    {"scan": scan, "review": review},
)


def _country_names() -> set[str]:
    """Every name the app knows a country by, lowercased."""
    from ccl_science_data.common import A2_GEN, get_str_arr

    names = set(get_str_arr(f"{A2_GEN}/countries-names", 8)) | set(EXTRA_NAMES)
    return {n.strip().lower() for n in names if n.strip()}


def _match(names: set[str], watch: set[int]) -> dict[int, Record]:
    """Author records whose display name is a country, plus every watched id, name aside."""
    from ccl_science_data.common import get_csv_parts

    parts = get_csv_parts("authors", "main")
    with Pool(SCAN_WORKERS) as pool:
        found = pool.imap_unordered(
            partial(_match_part, names=names, watch=watch), parts
        )
        return {oa_id: rec for part in found for oa_id, rec in part}


def _match_part(
    part: Path, names: set[str], watch: set[int]
) -> list[tuple[int, Record]]:
    import pandas as pd
    from ccl_science_data.common import DN, IDC, PREFIX_LEN, parse_id

    out = []
    for chunk in pd.read_csv(
        part,
        usecols=[IDC, "orcid", DN, "works_count", "cited_by_count"],
        dtype={"orcid": "string"},
        compression="zstd",
        chunksize=1_000_000,
    ):
        hit = chunk[DN].str.strip().str.lower().isin(names)
        if watch:
            hit |= parse_id(chunk[IDC]).isin(watch)
        for row in chunk[hit].itertuples(index=False):
            orcid = row.orcid
            out.append(
                (
                    int(getattr(row, IDC)[PREFIX_LEN:]),
                    Record(
                        name=getattr(row, DN),
                        orcid=orcid if isinstance(orcid, str) else "",
                        works=int(row.works_count),
                        cites=int(row.cited_by_count),
                    ),
                )
            )
    return out


def _in_app(rows: dict[int, Record]) -> dict[int, Record]:
    """The subset the pipeline's last filter kept — the only ids the server can serve."""
    import numpy as np
    from ccl_science_data.common import get_last_filter

    ids = np.fromiter(rows, dtype=np.uint64, count=len(rows))
    kept = ids[np.isin(ids, get_last_filter("authors"))]
    return {int(i): rows[int(i)] for i in kept}


def _by_size(rows: dict[int, Record]) -> list[tuple[int, Record]]:
    return sorted(rows.items(), key=lambda kv: -kv[1].works)


def _summary(oa_id: int, rec: Record) -> str:
    orcid = f" {rec.orcid}" if rec.orcid else ""
    return f"{oa_id} {rec.name} (works {rec.works}, cites {rec.cites}){orcid}"


def _evidence(be_url: str, oa_id: int) -> tuple[str | None, list[tuple]]:
    sem_ids = _get(f"{be_url}/sem-id-via-oa/authors/{oa_id}")
    sem_id = sem_ids[0] if sem_ids else None
    if not sem_id:
        return None, []
    papers = _get(f"{be_url}/works/authors/{sem_id}/0")["resp"]["papers"]
    return sem_id, [
        (p["year"], p["citations"], p["name"][:90]) for p in papers[:EVIDENCE_PAPERS]
    ]


def _get(url: str, tries: int = 5):
    """The public backend rate-limits; back off rather than skipping a record."""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f"{url}: rate-limited out")


def _parse(path: Path) -> tuple[dict[int, str], dict[int, str], list[str]]:
    """The tool-owned tail as (country, cleared) verdicts, plus the head kept verbatim."""
    lines = path.read_text().splitlines()
    if MARKER not in lines:
        raise SystemExit(f"{path}: no marker line -- expected {MARKER!r}")
    head = lines[: lines.index(MARKER) + 1]
    listed: dict[int, str] = {}
    cleared: dict[int, str] = {}
    for line in lines[len(head) :]:
        if line.startswith(CLEARED):
            oa_id, _, note = line[len(CLEARED) :].partition(" ")
            cleared[int(oa_id)] = note
        elif line.strip():
            oa_id, _, name = line.partition(" ")
            listed[int(oa_id)] = name
    return listed, cleared, head


def _write(path: Path, listed: dict[int, str], cleared: dict[int, str]) -> None:
    _, _, head = _parse(path)
    body = [f"{i} {n}" for n, i in sorted((n, i) for i, n in listed.items())]
    notes = [f"{CLEARED}{i} {n}" for n, i in sorted((n, i) for i, n in cleared.items())]
    path.write_text("\n".join(head + body + notes) + "\n")
