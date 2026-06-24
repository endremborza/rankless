"""Bake the homepage feature-showcase snapshot.

Runs the same way as `make lib_data_generation` (`uv run -m pyscripts.homepage_showcase`)
and writes `src/lib/assets/data/homepage-showcase.json`. The home page imports that file
directly, so the showcase needs no backend call on load.

Data is pulled from the running backend (the source of truth for peers / co-authors /
works), not recomputed here. Fails loudly if the backend is unreachable.
"""

import json
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

BASE = "http://127.0.0.1:3038/v1"
OUT = Path("src/lib/assets/data/homepage-showcase.json")

# Tried in order; first one that resolves becomes the featured scholar. Falls back to the
# top-ranked author if none resolve, so the script never depends on a single id surviving
# a data refresh.
PREFERRED = ["richard-h-thaler"]

COAUTHOR_N = 6
SUBFIELD_N = 6


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
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
    hero = peers["hero"]
    pairs = sorted(
        (
            {"name": sf["name"], "cites": c}
            for sf, c in zip(peers["topSubfields"], hero["subfieldCitations"])
        ),
        key=lambda p: -p["cites"],
    )
    # EraRec ends at the current calendar year (== backend FINAL_YEAR / frontend LATEST_YEAR);
    # year_from anchors the (trailing-zero-trimmed) series so the chart can label real years.
    yearly = hero["yearlyCites"]
    year_from = date.today().year - (len(yearly) - 1)
    while len(yearly) > 1 and yearly[-1] == 0:
        yearly = yearly[:-1]
    return {
        "subfields": pairs[:SUBFIELD_N],
        "yearFrom": year_from,
        "yearly": yearly,
    }


def resolvable_authors(paper: dict, authors_map: dict, disc: dict) -> int:
    n = 0
    for s in paper["authorships"]:
        a = s["author"]
        if a[0] == "F" and a[1:] in authors_map:
            n += 1
        elif disc.get(a) and disc[a] != "Unknown":
            n += 1
    return n


def extract_paper(resp: dict, exclude_name: str) -> tuple | None:
    """Best (score, payload) from one author's works, or None.

    Ranks by: well-formed biblio, then a real indexed journal (non-empty source semantic id,
    which excludes preprint repos), then the fraction of authors that resolve to real names
    (a clean byline reads better than one peppered with "et al."), then citations. Papers that
    name the featured scholar are skipped so their name never surfaces in the citation preview.
    """
    atts = resp["entityAtts"]
    disc = resp["discAuthorNames"]
    authors_map = atts.get("authors", {})
    sources = atts.get("sources", {})

    def resolved_names(p: dict) -> set[str]:
        return {
            authors_map[s["author"][1:]]["name"]
            for s in p["authorships"]
            if s["author"][0] == "F" and s["author"][1:] in authors_map
        }

    def score(p: dict) -> tuple:
        b = p.get("biblio") or {}
        src = sources.get(str(p["source"]), {})
        n_res = resolvable_authors(p, authors_map, disc)
        return (
            bool(p.get("doi") and b.get("volume") and b.get("first_page")),
            bool(src.get("semantic_id")),
            n_res / max(1, len(p["authorships"])),
            p["citations"],
        )

    candidates = [
        p
        for p in resp["papers"]
        if resolvable_authors(p, authors_map, disc)
        and exclude_name not in resolved_names(p)
    ]
    if not candidates:
        return None
    paper = max(candidates, key=score)

    # Bake only the entity atts this one paper references.
    needed_authors = {
        s["author"][1:]
        for s in paper["authorships"]
        if s["author"][0] == "F" and s["author"][1:] in authors_map
    }
    needed_disc = {
        s["author"]: disc[s["author"]]
        for s in paper["authorships"]
        if s["author"] in disc
    }
    payload = {
        "paper": paper,
        "entityAtts": {
            "sources": {k: v for k, v in sources.items() if k == str(paper["source"])},
            "authors": {k: authors_map[k] for k in needed_authors},
        },
        "discAuthorNames": needed_disc,
    }
    return score(paper), payload


def build_sample_paper(candidate_sids: list[str], exclude_name: str) -> dict | None:
    """Pick the cleanest demo paper across the candidate scholars. The featured scholar is
    excluded so the citation/BibTeX preview reads as a generic feature demo, not their profile.
    """
    best = None
    for sid in candidate_sids:
        got = extract_paper(get(f"/works/authors/{sid}/0?n=80")["resp"], exclude_name)
        if got and (best is None or got[0] > best[0]):
            best = got
    return best[1] if best else None


def main():
    sids = author_sids()
    sid = pick_scholar(sids)
    view = get(f"/views/authors/{sid}")
    peers = get(f"/peers/authors/{sid}")
    others = [s for s in sids if s != sid]
    snapshot = {
        "scholar": {
            "name": view["name"],
            "semanticId": sid,
            "papers": view["papers"],
            "citations": view["citations"],
        },
        "coauthors": build_coauthors(view),
        "peers": build_peers(peers),
        "samplePaper": build_sample_paper(
            others or [sid], view["name"] if others else ""
        ),
    }
    OUT.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    print(f"wrote {OUT} (featured: {view['name']})")


if __name__ == "__main__":
    main()
