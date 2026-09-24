"""The MCP tool implementations: plain async functions over the backend.

Kept independent of the MCP server object so they can be called directly:
`mcp_server.verify` re-issues them deterministically for the `verify_claims`
tool and the offline miners, and `server.py` registers them wrapped in the
receipt envelope (`mcp_server.receipts`).
"""

from mcp_server import (
    ROOT_TYPES,
    SEARCH_TYPES,
    encode_semantic_id,
    entity_url,
    table_url,
)
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

MAX_RANK_LIMIT = 100
MAX_ANNOTATE_IDS = 24
ROW_INTERNALS = ("oaId", "dmId", "values")

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
answered per entity, keyed by the call. Never call it once per entity.

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
    Top-N means and the recent h-indices. `texts` states the paper score and the
    hit paper in words, filled from those values. Explain what a number counts
    from this, never from memory; its values verify like any other data.
    """
    return await get_json("/methodology")


async def get_entity_profile(entity_type: str, semantic_id: str) -> dict:
    """Full profile of one entity: totals, yearly series, top relations, similars.

    `yearlyPapers`/`yearlyCites` cover the recent era (2016..now). `relations`
    holds ranked related entities per relation type (paper-fields,
    citing-fields, paper-journals, paper-authors, ...). `coauthorEdges` lists
    the strongest ties among the entity's top authors (an author's co-authors):
    the papers each pair wrote together anywhere, not only within this entity
    (counts cap at 255).
    """
    _check_etype(entity_type)
    res = await get_json(f"/views/{entity_type}/{encode_semantic_id(semantic_id)}")
    shaped = {k: v for k, v in res.items() if k != "authorNetwork"}
    if "authorNetwork" in res:
        shaped["coauthorEdges"] = coauthor_edges(res)
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
        f"/trees/{entity_type}/{encode_semantic_id(semantic_id)}",
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
        f"/works/{entity_type}/{encode_semantic_id(semantic_id)}/{offset}",
        {"n": limit, "sort": sort},
    )
    papers = [
        {k: p.get(k) for k in ("name", "year", "doi", "citations", "oaId")}
        for p in res.get("resp", {}).get("papers", [])
    ]
    return {"rankless_url": entity_url(entity_type, semantic_id), "papers": papers}


async def get_peers(entity_type: str, semantic_id: str) -> dict:
    """Peer entities (comparable size + field profile) and top subfields."""
    _check_etype(entity_type)
    res = await get_json(f"/peers/{entity_type}/{encode_semantic_id(semantic_id)}")
    res["rankless_url"] = entity_url(entity_type, semantic_id)
    return truncate_lists(res)


async def lookup_orcid(orcid: str) -> dict:
    """Resolve an ORCID iD (e.g. 0000-0001-7896-6217) to a rankless author."""
    res = await get_json(f"/orcid/{orcid}")
    return add_url(res, "authors")


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
    return {
        "total": meta["total"],
        "screened": meta["screened"],
        "sort": sort or _default_sorts.get(entity_type),
        "where": where,
        "columns": meta["columns"],
        "rankless_url": table_url(
            entity_type, {**params, "from": offset if offset else None}
        ),
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
    return {"metrics": keys, "entities": entities}


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
    get_peers,
    lookup_orcid,
    rank_entities,
    annotate_entities,
)

TOOL_FNS = {fn.__name__: fn for fn in TOOLS}
