"""Bake the homepage feature-showcase snapshot.

Runs the same way as `make lib_data_generation` (`uv run -m pyscripts.homepage_showcase`)
and writes `src/lib/assets/data/homepage-showcase.json`. The home page imports that file
directly, so the showcase needs no backend call on load.

Data is pulled from the running backend (the source of truth for peers / co-authors /
works), not recomputed here. Fails loudly if the backend is unreachable. Point it at a
remote backend with `SHOWCASE_BE=https://host/v1 uv run -m pyscripts.homepage_showcase`
when the local instance holds a reduced test dataset.
"""

import json
import os
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

BASE = os.environ.get("SHOWCASE_BE", "http://127.0.0.1:3038/v1").rstrip("/")
OUT = Path("src/lib/assets/data/homepage-showcase.json")

# Tried in order; first one that resolves becomes the featured scholar. Falls back to the
# top-ranked author if none resolve, so the script never depends on a single id surviving
# a data refresh.
PREFERRED = ["richard-h-thaler"]

COAUTHOR_N = 6  # nodes in the network preview
SUBFIELD_N = 6  # fields in the comparative peers preview
HIT_N = 9  # arcs in the hit-paper rainbow
TIMELINE_N = 6  # rows in the co-author timeline
TIMELINE_MIN = 2  # a co-author needs this many shared papers to earn a row


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.load(r)


def tri_index(i: int, j: int, n: int) -> int:
    """Upper-triangular index, mirroring network-util.ts getIndex."""
    if i > j:
        i, j = j, i
    return (n * i - i - (i * (i - 1)) // 2) + j - i - 1


def author_sids() -> list[str]:
    authors = next(b for b in get("/tops") if b["name"] == "authors")
    return [e["semanticId"] for e in authors["entities"]]


def pick_scholar(sids: list[str]) -> str:
    for sid in PREFERRED:
        try:
            if get(f"/views/authors/{sid}").get("name"):
                return sid
        except urllib.error.HTTPError:
            continue
    return sids[0]


def build_coauthors(view: dict) -> dict:
    pa = view["relations"].get("paper-authors", [])
    full_n = len(pa)
    net = view["authorNetwork"]
    top = pa[:COAUTHOR_N]
    nodes = [
        {"name": a["name"], "semanticId": a["semanticId"], "score": a["score"]}
        for a in top
    ]
    edges = []
    for i in range(len(top)):
        for j in range(i + 1, len(top)):
            w = net[tri_index(i, j, full_n)]
            if w > 0:
                edges.append([i, j, w])
    return {"rootName": view["name"], "nodes": nodes, "edges": edges}


def build_peers(peers: dict) -> dict:
    """Hero vs its single most comparable peer — the comparison is the whole point of the
    feature, so the preview bakes both sides for the top fields and the citation timeline."""
    hero = peers["hero"]
    peer = peers["peers"][0]
    cols = sorted(
        (
            {"name": sf["name"], "hero": h, "peer": p}
            for sf, h, p in zip(
                peers["topSubfields"],
                hero["subfieldCitations"],
                peer["subfieldCitations"],
            )
        ),
        key=lambda c: -c["hero"],
    )
    hero_y = list(hero["yearlyCites"])
    peer_y = list(peer["yearlyCites"])
    # EraRec ends at the current calendar year (== backend FINAL_YEAR / frontend LATEST_YEAR);
    # year_from anchors the series so the chart can label real years.
    year_from = date.today().year - (len(hero_y) - 1)
    while len(hero_y) > 1 and hero_y[-1] == 0 and peer_y[-1] == 0:
        hero_y.pop()
        peer_y.pop()
    return {
        "heroName": hero["name"],
        "peerName": peer["name"],
        "peerCountry": peer.get("country"),
        "subfields": cols[:SUBFIELD_N],
        "yearFrom": year_from,
        "heroYearly": hero_y,
        "peerYearly": peer_y,
    }


def build_hit_papers(papers: list[dict]) -> list[dict]:
    """The scholar's hit papers as the rainbow draws them: each an arc from its publication
    year to now, height by citations. Only year/citations/title are needed for that."""
    hits = sorted(
        (p for p in papers if p.get("isHit") and (p.get("year") or 0) > 0),
        key=lambda p: -p["citations"],
    )
    return [
        {"year": p["year"], "citations": p["citations"], "name": p["name"]}
        for p in hits[:HIT_N]
    ]


def build_coauthor_timeline(
    papers: list[dict], atts: dict, disc: dict, hero_sid: str
) -> dict:
    """Per-co-author collaboration spans + per-year shared-paper marks, mirroring
    utils/author-timeline.ts buildCoauthors (hero dropped, hit papers flagged)."""
    authors_map = atts.get("authors", {})

    def resolve(ship: dict) -> tuple[str, None] | None:
        a = ship["author"]
        if a[0] == "F" and a[1:] in authors_map:
            att = authors_map[a[1:]]
            if att.get("semantic_id") == hero_sid:
                return None  # the hero links everyone — leave out
            return att["name"], None
        if disc.get(a) and disc[a] != "Unknown":
            return disc[a], None
        return None

    by_author: dict[str, dict] = defaultdict(
        lambda: {"name": "", "by_year": defaultdict(lambda: {"n": 0, "hit": False})}
    )
    for p in papers:
        y = p.get("year") or 0
        if y <= 0:
            continue
        for ship in p["authorships"]:
            r = resolve(ship)
            if r is None:
                continue
            e = by_author[ship["author"]]
            e["name"] = r[0]
            bucket = e["by_year"][y]
            bucket["n"] += 1
            if p.get("isHit"):
                bucket["hit"] = True

    rows = []
    for e in by_author.values():
        years = sorted(e["by_year"])
        count = sum(e["by_year"][y]["n"] for y in years)
        if count < TIMELINE_MIN:
            continue
        rows.append(
            {
                "name": e["name"],
                "count": count,
                "firstYear": years[0],
                "lastYear": years[-1],
                "marks": [
                    {
                        "year": y,
                        "n": e["by_year"][y]["n"],
                        "hit": e["by_year"][y]["hit"],
                    }
                    for y in years
                ],
            }
        )
    rows.sort(key=lambda r: (-r["count"], r["firstYear"]))
    rows = rows[:TIMELINE_N]
    for r in rows:
        del r["count"]
    # Anchor the axis to the shown rows (not the whole career) so the preview fills its width.
    lo = min((r["firstYear"] for r in rows), default=0)
    hi = max((r["lastYear"] for r in rows), default=0)
    return {"yearLo": lo, "yearHi": hi, "rows": rows}


def main():
    sids = author_sids()
    sid = pick_scholar(sids)
    view = get(f"/views/authors/{sid}")
    peers = get(f"/peers/authors/{sid}")
    works = get(f"/works/authors/{sid}/0?n=200")["resp"]
    snapshot = {
        "scholar": {
            "name": view["name"],
            "semanticId": sid,
            "papers": view["papers"],
            "citations": view["citations"],
        },
        "hitPapers": build_hit_papers(works["papers"]),
        "coauthorTimeline": build_coauthor_timeline(
            works["papers"], works["entityAtts"], works["discAuthorNames"], sid
        ),
        "coauthors": build_coauthors(view),
        "peers": build_peers(peers),
    }
    OUT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print(f"wrote {OUT} (featured: {view['name']})")


if __name__ == "__main__":
    main()
