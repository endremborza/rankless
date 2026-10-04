"""The MCP tool implementations: plain async functions over the backend.

Kept independent of the MCP server object so they can be called directly:
`mcp_server.verify` re-issues them deterministically for the `verify_claims`
tool and the offline miners, and `server.py` registers them wrapped in the
receipt envelope (`mcp_server.receipts`).
"""

from mcp_server import (
    NOBEL_CATEGORIES,
    ROOT_TYPES,
    SEARCH_TYPES,
    VIEW_TYPES,
    card_url,
    encode_semantic_id,
    entity_url,
    table_url,
)
from mcp_server.cards import KINDS, profile_cards
from mcp_server.client import get_json
from mcp_server.response_shaping import (
    add_url,
    coauthor_edges,
    flatten_tree,
    truncate_lists,
)

_specs_cache: dict | None = None
# Each root type's default ordering, from the registry `describe()` reads; the backend
# applies it to a sortless `/slice`, so this only names it.
_default_sorts: dict[str, str] = {}
# Each root type's metrics whose values are numbers, from the same registry.
_numeric: dict[str, set[str]] = {}

MAX_RANK_LIMIT = 100
MAX_ANNOTATE_IDS = 24
ROW_INTERNALS = ("oaId", "dmId", "values")
PAPER_FIELDS = ("name", "year", "citations", "score", "isHit", "doi")

# The two table tools' descriptions are built from the backend's metric registry (`/v1/columns`)
# by `describe()` before the server registers them, so the metric ids, meanings, value types,
# parameters and kinds exist in one place. The templates hold only what the registry does not:
# the tool's purpose and the expression language.
EXPRESSIONS = """\
A metric is written as a call: `papers`, `field_score(oncology)`, `window_papers(2020, 2024)`,
`cited_from(usa)`; the argument is a semantic_id (or a quoted name) of the parameter's entity
type, or two years. A `where` expression combines clauses `metric op value` with `and`, `or`,
`not` and parentheses (precedence: parentheses, not, and, or). Numbers take `= != < <= > >=`
and `in (1, 2)`; entity-valued metrics (country, city) take `= != in not in` with a
semantic_id or a quoted name, e.g. `country = hun and city != budapest and (papers >= 500 or
weighted_paper_score >= 20)`. On a set-valued metric (an author's countries) `=` means any equals and
`!=` none does."""

RANK_DOC = """\
Rank the entities of one type by a metric call, narrowed by a `where` expression; the way to
answer "which {{entity_type}} are strongest / biggest in ...". Without `sort` a type is ranked by
its default ({defaults}). `total` is the size of the
narrowed cohort; `screened` is set when a per-entity metric ranks (or narrows) only the cohort's
top 1000 by citations, and then `rank` is within those 1000, not within `total`. Rows carry every metric column the ranking
makes available (`columns` lists them) and `rankless_url` opens the same table on the site.

{expressions}

Metrics (global = ranks and narrows the whole cohort; per-entity = the top 1000 by citations;
a walk = a page column for annotate_entities only, never a ranking or a clause):
{metrics}
"""

ANNOTATE_DOC = """\
Metric values for up to {max_ids} named entities of one type in one call: every metric call
answered per entity, keyed by the call. Never call it once per entity. `image_url` is the table
card with the entities pinned and the metrics as columns, present when one card holds them: at
most {card_pins} entities and {card_cols} metrics, all numbers.

{expressions}

Metrics and their parameters:
{metrics}
"""


def _check_etype(entity_type: str, allowed: tuple[str, ...] = ROOT_TYPES) -> None:
    if entity_type not in allowed:
        raise ValueError(f"entity_type must be one of {allowed}, got {entity_type!r}")


async def _specs() -> dict:
    global _specs_cache
    if _specs_cache is None:
        _specs_cache = await get_json("/specs")
    return _specs_cache


async def search_entities(query: str, entity_type: str = "all") -> list[dict]:
    """Search entities by name; the ONLY legitimate way to turn a name into ids.

    Always resolve names through this (or lookup_orcid) before using a
    semantic_id — never guess ids. entity_type: one of authors, institutions,
    sources, countries, subfields, or "all". Returns matches with semanticId,
    papers, citations and a rankless_url backlink.
    """
    _check_etype(entity_type, SEARCH_TYPES)
    res = await get_json(f"/names/{entity_type}", {"q": query})
    return [add_url(r, entity_type if entity_type != "all" else "authors") for r in res]


async def get_top_entities() -> list[dict]:
    """Top entities per type (institutions, authors, sources, countries, subfields).

    Good starting seeds when exploring without a specific target.
    """
    res = await get_json("/tops")
    return [
        {**grp, "entities": [add_url(e, grp["name"]) for e in grp["entities"]]}
        for grp in res
    ]


async def get_methodology() -> dict:
    """The definitions every number is built on, as the data was built with them.

    `workScreen` decides which papers are in the data at all, and so what an
    indexed paper and an indexed citation are: work kinds, year window, citation
    floor, author cap, and the per-entity minimums. `paperScore` holds what a
    paper's score measures it against (the bar's top share and blend weights) and
    the multiple that makes it a hit paper; `topN` and `hSince` parametrize the
    Top-N means and the recent h-indices; `yearlyCounts` is the first and last
    year with yearly counts, the bounds of a year window. `texts` states the
    paper score and the hit paper in words, filled from those values. Explain
    what a number counts from this, never from memory; its values verify like any
    other data.
    """
    return await get_json("/methodology")


async def get_entity_profile(entity_type: str, semantic_id: str) -> dict:
    """Full profile of one entity: totals, yearly series, top relations, similars.

    entity_type is a root type or hit-papers (a hit paper's semantic_id comes
    from get_papers or get_impact_dag). `yearlyPapers`/`yearlyCites` cover the
    recent era (2016..now), and `startYear` is the first year of that era with a
    paper, not a career start (a hit paper's is its publication year).
    `relations` holds ranked related entities per relation type (paper-fields,
    citing-fields, paper-journals, paper-authors, ...). `coauthorEdges` lists
    the strongest ties among the entity's top authors (an author's co-authors):
    the papers each pair wrote together anywhere, not only within this entity
    (counts cap at 255). `image_url` is the share card of the entity's default
    breakdown and `cards` the default card of every other kind this profile
    shows the entity has (yearly citations, map, fields, and for an author with
    co-authors their network and timeline); get_peers, get_papers and
    get_impact_dag link the peers, hit-paper and impact cards, and make_card
    renders a variant.
    """
    _check_etype(entity_type, VIEW_TYPES)
    res = await get_json(f"/views/{entity_type}/{encode_semantic_id(semantic_id)}")
    shaped = {k: v for k, v in res.items() if k != "authorNetwork"}
    if "authorNetwork" in res:
        shaped["coauthorEdges"] = coauthor_edges(res)
    shaped["rankless_url"] = entity_url(entity_type, semantic_id)
    shaped["image_url"] = card_url("tree", entity_type, semantic_id)
    shaped["cards"] = profile_cards(entity_type, semantic_id, res)
    return truncate_lists(shaped)


async def get_entity_stats(
    entity_type: str,
    semantic_id: str,
    year_from: int | None = None,
    year_to: int | None = None,
    subfield: str | None = None,
) -> dict:
    """Lifetime + year-windowed paper/citation counts, top citing subfields.

    The per-year window only covers the recent era (2016..now); `windowFrom`/
    `windowTo` in the response show the clamped range actually used. Pass
    `subfield` (a subfields semantic_id) for that subfield's citation slice.
    """
    _check_etype(entity_type)
    res = await get_json(
        f"/stats/{entity_type}/{encode_semantic_id(semantic_id)}",
        {"year_from": year_from, "year_to": year_to, "subfield": subfield},
    )
    res["rankless_url"] = entity_url(entity_type, semantic_id)
    return truncate_lists(res)


async def get_citation_tree(
    entity_type: str,
    semantic_id: str,
    tree_index: int = 0,
    since_year: int | None = None,
    top_n: int = 8,
    depth: int = 2,
) -> dict:
    """Hierarchical citation-impact breakdown of an entity, flattened to top-N.

    entity_type is a root type or hit-papers (who cites one paper, by country or
    field). `tree_index` picks a breakdown config (see `levels` in the response
    for what each level means). `since_year` keeps only the entity's papers
    published in or after that year, not citations made since then; the year
    used is echoed as `sinceYear`.
    `citationLinks` counts citation links into a node, `sourceWorks` counts
    the entity's own works under it. `rankless_url` opens this same breakdown
    on the site and `image_url` is its share card (bands sized by citation
    count, as the rows are ranked); a top-level row's `image_url` is the card
    with that branch opened (node 0 cannot be opened and has none), and its
    `nodeId` is what make_card's `paths` and
    `hl` take.
    """
    _check_etype(entity_type, VIEW_TYPES)
    specs = (await _specs())["specs"][entity_type]
    if not 0 <= tree_index < len(specs):
        raise ValueError(f"tree_index must be in 0..{len(specs) - 1}")
    spec = specs[tree_index]
    # A hit paper's tree holds its one paper, which any later year filters out.
    default = (await _specs())["yearBreaks"][0] if entity_type == "hit-papers" else None
    year = since_year or default or spec["defaultYear"]
    res = await get_json(
        f"/trees/{entity_type}/{encode_semantic_id(semantic_id)}",
        {"year": year, "tid": tree_index},
    )
    view = {"tree": tree_index + 1, "since": year}
    card = {**view, "isSpec": 0}
    rows = flatten_tree(res, spec["breakdowns"], top_n, depth)
    for row in rows:
        if row["nodeId"]:
            row["image_url"] = card_url(
                "tree", entity_type, semantic_id, {**card, "paths": row["nodeId"]}
            )
    return {
        "rankless_url": entity_url(entity_type, semantic_id, view),
        "image_url": card_url("tree", entity_type, semantic_id, card),
        "sinceYear": year,
        "levels": [
            {"entityType": b["attributeType"], "sourceSide": b["sourceSide"]}
            for b in spec["breakdowns"][:depth]
        ],
        "breakdown": rows,
    }


async def get_papers(
    entity_type: str,
    semantic_id: str,
    offset: int = 0,
    limit: int = 10,
    sort: str | None = None,
) -> dict:
    """Papers of an entity. sort="citations" ranks by citation count first.

    Each paper has its title, year, citations, `score` (its paper score, see
    get_methodology) and `isHit`. A hit paper links to its rankless page
    (`rankless_url`, `semanticId` for the hit-papers tools); any other paper
    links to OpenAlex (`openalex_url`). For an author with hit papers among
    the rows `image_url` is the card of their hit papers, and a hit row's own
    `image_url` the card with that paper highlighted.
    """
    _check_etype(entity_type)
    res = await get_json(
        f"/works/{entity_type}/{encode_semantic_id(semantic_id)}/{offset}",
        {"n": limit, "sort": sort},
    )
    papers = [_paper(p) for p in res.get("resp", {}).get("papers", [])]
    out = {"rankless_url": entity_url(entity_type, semantic_id), "papers": papers}
    hits = [p for p in papers if "semanticId" in p]
    if hits and entity_type in KINDS["papers"]["types"]:
        out["image_url"] = card_url("papers", entity_type, semantic_id)
        for p in hits:
            p["image_url"] = card_url(
                "papers", entity_type, semantic_id, {"hl": p["semanticId"]}
            )
    return out


async def get_impact_dag(semantic_id: str) -> dict:
    """The hit papers that build on an author's work: which of the most-cited
    papers of their fields and years cite the author's papers.

    `citingHits` are at most 50 hit papers citing the author, ordered by paper
    score. They are a selection, not all of them: the data keeps the 50 with
    the most citations and the strongest journals, favouring papers laureates
    wrote up to their prize year, and never a paper the author co-wrote; do not
    read a share of laureates or fields among them as a share of everything
    citing the author. Each names the laureates among its authors and the
    author's papers it cites (`cites`, indices into `authorPapers`).
    `authorPapers` are those cited papers, each with how many of the listed hits
    cite it (`citedByHits`). A story worth telling is one hit and the paper it
    builds on: a laureate citing the author, a jump into another field, a long
    reach in years. Pass a hit's `semanticId` to get_citation_tree or
    get_entity_profile with entity_type="hit-papers" to follow it further.
    `image_url` is the impact card of the top hits, absent when no hit cites
    the author; a hit's own `image_url` is the card with that hit and the
    author's papers it builds on.
    """
    res = await get_json(f"/paper-profile/{encode_semantic_id(semantic_id)}")
    return _impact_dag(res, semantic_id)


async def get_peers(entity_type: str, semantic_id: str) -> dict:
    """Peer entities (comparable size + field profile) and top subfields.

    `image_url` is the peers card against the first peer, absent when there is
    none; a peer's own `image_url` is the card comparing the entity with that peer.
    """
    _check_etype(entity_type)
    res = await get_json(f"/peers/{entity_type}/{encode_semantic_id(semantic_id)}")
    res["rankless_url"] = entity_url(entity_type, semantic_id)
    if res.get("peers"):
        res["image_url"] = card_url("peers", entity_type, semantic_id)
    for peer in res.get("peers", []):
        peer["image_url"] = card_url(
            "peers", entity_type, semantic_id, {"hl": peer["semanticId"]}
        )
    return truncate_lists(res)


async def lookup_orcid(orcid: str) -> dict:
    """Resolve an ORCID iD (e.g. 0000-0001-7896-6217) to a rankless author."""
    res = await get_json(f"/orcid/{orcid}")
    return add_url(res, "authors")


def _paper(p: dict) -> dict:
    out = {k: p[k] for k in PAPER_FIELDS if p.get(k) not in (None, "")}
    if sem := p.get("hitSemId"):
        out["semanticId"] = sem
        out["rankless_url"] = entity_url("hit-papers", sem)
    else:
        out["openalex_url"] = f"https://openalex.org/W{p['oaId']}"
    return out


def _dag_paths(node: dict | str, prefix: tuple[int, ...] = ()) -> list[tuple[int, ...]]:
    if not isinstance(node, dict):
        return [prefix]
    return [
        path
        for wid, child in node["Node"].items()
        for path in _dag_paths(child, (*prefix, int(wid)))
    ]


def _impact_dag(res: dict, semantic_id: str) -> dict:
    """`/paper-profile`'s DAG (a citing hit paper -> the author's papers it cites)
    as one row per citing hit and one per cited paper of the author."""
    resp = res["papers"]
    papers = {p["wid"]: p for p in resp["papers"]}
    authors = resp["entityAtts"].get("authors", {})
    sources = resp["entityAtts"].get("sources", {})
    meta = resp["authorsMeta"]
    cites: dict[int, set[int]] = {}
    for path in _dag_paths(res["dag"]):
        cites.setdefault(path[0], set()).add(path[-1])
    cited = sorted(
        {w for ws in cites.values() for w in ws}, key=lambda w: _rank(papers[w])
    )
    at = {w: i for i, w in enumerate(cited)}
    hits = []
    for wid in sorted(cites, key=lambda w: _rank(papers[w])):
        p = papers[wid]
        ids = [a["author"][1:] for a in p["authorships"] if a["author"][0] == "F"]
        hits.append(
            {
                **_paper(p),
                "image_url": card_url(
                    "impact", "authors", semantic_id, {"hits": p.get("hitSemId")}
                ),
                "journal": sources.get(str(p.get("source")), {}).get("name"),
                "laureates": [
                    _laureate(authors[i], meta[i])
                    for i in ids
                    if meta.get(i, {}).get("prize")
                ],
                "cites": sorted(at[w] for w in cites[wid]),
            }
        )
    by_hits = {w: sum(w in ws for ws in cites.values()) for w in cited}
    return {
        "rankless_url": entity_url("authors", semantic_id),
        **({"image_url": card_url("impact", "authors", semantic_id)} if hits else {}),
        "citingHits": hits,
        "authorPapers": [
            {**_paper(papers[w]), "citedByHits": by_hits[w]} for w in cited
        ],
    }


def _rank(p: dict) -> tuple:
    return (-(p.get("score") or 0), -p["citations"], p["wid"])


def _laureate(att: dict, meta: dict) -> dict:
    return {
        "name": att["name"],
        "prize": NOBEL_CATEGORIES[meta["prize"] - 1],
        "year": meta["year"],
        "rankless_url": entity_url("authors", att["semantic_id"]),
    }


def _row(row: dict, entity_type: str) -> dict:
    flat = {k: v for k, v in row.items() if k not in ROW_INTERNALS}
    return add_url({**flat, **row.get("values", {})}, entity_type)


async def rank_entities(
    entity_type: str,
    sort: str | None = None,
    where: str | None = None,
    offset: int = 0,
    limit: int = 20,
) -> dict:
    _check_etype(entity_type)
    limit = max(1, min(limit, MAX_RANK_LIMIT))
    params = {"sort": sort, "where": where}
    page = await get_json(f"/slice/{entity_type}/{offset}/{offset + limit}", params)
    meta = page["meta"]
    view = {**params, "from": offset if offset else None}
    return {
        "total": meta["total"],
        "screened": meta["screened"],
        "sort": sort or _default_sorts.get(entity_type),
        "where": where,
        "columns": meta["columns"],
        "rankless_url": table_url(entity_type, view),
        "image_url": card_url("table", entity_type, "", view),
        "rows": [_row(r, entity_type) for r in page["rows"]],
    }


async def annotate_entities(
    entity_type: str,
    semantic_ids: list[str],
    metrics: list[str],
) -> dict:
    _check_etype(entity_type)
    if not semantic_ids or not metrics:
        raise ValueError("semantic_ids and metrics must both be non-empty")
    pins = ",".join(semantic_ids[:MAX_ANNOTATE_IDS])
    pinned = (await get_json(f"/slice/{entity_type}/0/0", {"pin": pins}))["rows"]
    values = await get_json(
        f"/metrics/{entity_type}",
        {
            "ids": ",".join(str(r["dmId"]) for r in pinned),
            "metrics": ",".join(metrics),
        },
    )
    at = {dm: i for i, dm in enumerate(values["ids"])}
    keys = list(values["values"])
    entities = []
    for r in pinned:
        i = at.get(r["dmId"])
        cols = {k: values["values"][k][i] if i is not None else None for k in keys}
        entities.append(
            add_url(
                {"name": r["name"], "semanticId": r["semanticId"], **cols}, entity_type
            )
        )
    out = {"metrics": keys, "entities": entities}
    if _fits_table_card(entity_type, semantic_ids, metrics):
        out["image_url"] = card_url(
            "table", entity_type, "", {"pin": pins, "cols": ",".join(metrics)}
        )
    return out


def _fits_table_card(entity_type: str, pins: list[str], metrics: list[str]) -> bool:
    """Whether one table card holds these pinned entities with these metric columns."""
    limits = KINDS["table"]["params"]
    numeric = _numeric.get(entity_type, set())
    return (
        len(pins) <= limits["pin"]["max"]
        and len(metrics) <= limits["cols"]["max"]
        and all(m.split("(", 1)[0].strip() in numeric for m in metrics)
    )


def _signature(m: dict) -> str:
    param = m.get("param")
    return (
        f"{m['id']}({'from, to' if param == 'window' else param})" if param else m["id"]
    )


def describe(registry: dict) -> None:
    """Fill the table tools' docstrings from the backend's metric registry. A metric's texts
    are per root type, so each wording is listed once, with the types it holds for grouped by
    the metric's kind on each."""
    kinds: dict[str, dict[str, list[str]]] = {}
    for root in (r for r in ROOT_TYPES if r in registry["roots"]):
        reg = registry["roots"][root]
        _default_sorts[root] = reg["defaultSort"]
        _numeric[root] = {
            m["id"]
            for m in reg["metrics"]
            if m["value"]["type"] not in ("entity", "entities")
        }
        for m in reg["metrics"]:
            vtype = m["value"]["type"]
            entity = m["value"].get("entity")
            typed = f"[{vtype} of {entity}]" if entity else f"[{vtype}]"
            line = f"- {_signature(m)} {typed}: {m['meaning']}"
            if m["cost"] == "walk":
                kind = "a walk"
            else:
                kind = "per-entity" if m["kind"] == "intricate" else "global"
            kinds.setdefault(line, {}).setdefault(kind, []).append(root)
    rank_lines = [
        line
        + " "
        + "; ".join(f"{k} for {', '.join(rs)}" for k, rs in by_kind.items())
        + "."
        for line, by_kind in kinds.items()
    ]
    annotate_lines = [
        f"{line} For {', '.join(rs)}."
        for line, by_kind in kinds.items()
        if (rs := by_kind.get("a walk", []) + by_kind.get("per-entity", []))
    ]
    rank_entities.__doc__ = RANK_DOC.format(
        expressions=EXPRESSIONS,
        defaults=", ".join(f"{r} by {s}" for r, s in _default_sorts.items()),
        metrics="\n".join(rank_lines),
    )
    annotate_entities.__doc__ = ANNOTATE_DOC.format(
        max_ids=MAX_ANNOTATE_IDS,
        card_pins=KINDS["table"]["params"]["pin"]["max"],
        card_cols=KINDS["table"]["params"]["cols"]["max"],
        expressions=EXPRESSIONS,
        metrics="\n".join(annotate_lines),
    )


TOOLS = (
    search_entities,
    get_top_entities,
    get_methodology,
    get_entity_profile,
    get_entity_stats,
    get_citation_tree,
    get_papers,
    get_impact_dag,
    get_peers,
    lookup_orcid,
    rank_entities,
    annotate_entities,
)

TOOL_FNS = {fn.__name__: fn for fn in TOOLS}
