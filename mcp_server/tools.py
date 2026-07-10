"""The MCP tool implementations: plain async functions over the backend.

Kept independent of the MCP server object so they can be called directly —
the explore-path evidence verifier re-issues these deterministically
(pyscripts/explore/paths/deep_stories.py).
"""

from mcp_server import ROOT_TYPES, SEARCH_TYPES, entity_url
from mcp_server.client import get_json
from mcp_server.response_shaping import add_url, flatten_tree, truncate_lists

VIEW_DROP_KEYS = ("authorNetwork",)

_specs_cache: dict | None = None


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


async def get_entity_profile(entity_type: str, semantic_id: str) -> dict:
    """Full profile of one entity: totals, yearly series, top relations, similars.

    `yearlyPapers`/`yearlyCites` cover the recent era (2016..now). `relations`
    holds ranked related entities per relation type (paper-fields,
    citing-fields, paper-journals, paper-authors, ...).
    """
    _check_etype(entity_type)
    res = await get_json(f"/views/{entity_type}/{semantic_id}")
    shaped = {k: v for k, v in res.items() if k not in VIEW_DROP_KEYS}
    shaped["rankless_url"] = entity_url(entity_type, semantic_id)
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
        f"/stats/{entity_type}/{semantic_id}",
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

    `tree_index` picks a breakdown config (see `levels` in the response for
    what each level means); `since_year` is a single lower cutoff.
    `citationLinks` counts citation links into a node, `sourceWorks` counts
    the entity's own works under it.
    """
    _check_etype(entity_type)
    specs = (await _specs())["specs"][entity_type]
    if not 0 <= tree_index < len(specs):
        raise ValueError(f"tree_index must be in 0..{len(specs) - 1}")
    spec = specs[tree_index]
    res = await get_json(
        f"/trees/{entity_type}/{semantic_id}",
        {"year": since_year or spec["defaultYear"], "tid": tree_index},
    )
    return {
        "rankless_url": entity_url(entity_type, semantic_id),
        "sinceYear": since_year or spec["defaultYear"],
        "levels": [
            {"entityType": b["attributeType"], "sourceSide": b["sourceSide"]}
            for b in spec["breakdowns"][:depth]
        ],
        "breakdown": flatten_tree(res, spec["breakdowns"], top_n, depth),
    }


async def get_papers(
    entity_type: str,
    semantic_id: str,
    offset: int = 0,
    limit: int = 10,
    sort: str | None = None,
) -> dict:
    """Papers of an entity. sort="citations" ranks by citation count first.

    Returns paper title, year, doi and citation count.
    """
    _check_etype(entity_type)
    res = await get_json(
        f"/works/{entity_type}/{semantic_id}/{offset}", {"n": limit, "sort": sort}
    )
    papers = [
        {k: p.get(k) for k in ("name", "year", "doi", "citations", "oaId")}
        for p in res.get("resp", {}).get("papers", [])
    ]
    return {"rankless_url": entity_url(entity_type, semantic_id), "papers": papers}


async def get_peers(entity_type: str, semantic_id: str) -> dict:
    """Peer entities (comparable size + field profile) and top subfields."""
    _check_etype(entity_type)
    res = await get_json(f"/peers/{entity_type}/{semantic_id}")
    res["rankless_url"] = entity_url(entity_type, semantic_id)
    return truncate_lists(res)


async def lookup_orcid(orcid: str) -> dict:
    """Resolve an ORCID iD (e.g. 0000-0001-7896-6217) to a rankless author."""
    res = await get_json(f"/orcid/{orcid}")
    return add_url(res, "authors")


TOOLS = (
    search_entities,
    get_top_entities,
    get_entity_profile,
    get_entity_stats,
    get_citation_tree,
    get_papers,
    get_peers,
    lookup_orcid,
)

TOOL_FNS = {fn.__name__: fn for fn in TOOLS}
