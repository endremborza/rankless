"""MCP resources: schema notes an agent needs before composing tools."""

from wire.rankless_server.responses import MethodologyOut

# Filled by `resources()` with the years the backend serves yearly counts for.
ENTITY_TYPES = """\
# Rankless entity types

Root types (valid `entity_type` values): authors, institutions, sources,
countries, subfields. get_entity_profile and get_citation_tree also take
hit-papers: one hit paper, by the semanticId get_papers or get_impact_dag gives.

- sources = journals/venues.
- subfields = the discipline level used everywhere (the UI calls them
  "Fields"); topics nest under subfields.
- semantic_id is the stable slug identifying an entity (e.g. authors/
  david-baker, institutions/nyu). Ids must come from search_entities /
  lookup_orcid — never guessed.
- citations are counted over the recent era ({first}..{last}) unless stated
  otherwise; `papers` counts the full lifetime.
"""

AGENT_GUIDE = """\
# Using the rankless tools

Every answer follows one loop: resolve, call, cite, verify, answer.

1. Resolve names to ids with search_entities (or lookup_orcid); disambiguate
   homonyms by papers/citations/distinctText and ask when genuinely
   ambiguous. Never guess a semantic_id.
2. Call the aggregation tools over resolved ids: get_entity_profile,
   get_entity_stats, get_citation_tree, get_peers, get_papers, and for an
   author get_impact_dag (the hit papers that build on their work). A "which
   entities are strongest / biggest in ..." question is one rank_entities
   call (a ranking metric plus narrowing clauses; `total` and `screened`
   state the cohort the rank is within); annotate_entities reads the
   page-local metrics for a list of named entities in one call.
   get_methodology states what the numbers count (an indexed citation, a
   hit paper) with the values the data was built with.
3. Every data-tool response is {"receipt": {"id", "tool", "args"}, "data": ...}.
   The receipt names the call that produced the data; keep its id with every
   number you take from it.
4. Before answering, submit every number you will state to verify_claims,
   citing its receipt id and the dotted path into data. Publish the
   reproduced values; drop or re-derive a claim that fails.
5. Answer with the numbers, their rankless_url links, and the receipt ids
   (e.g. "146,700 citations [r3]"), so a reader can reproduce each one. An
   image_url is the share card of what its response shows and a profile's
   `cards` the further kinds it proves; make_card renders a variant (a highlighted
   country or field, an opened branch, a pinned peer, a filtered table) where
   the answer carries pictures.

When no tool can supply what the question needs, say so plainly, answer the
part that is grounded, and call suggest_endpoint with what was missing.
Numbers are deterministic backend aggregates: never invent, extrapolate or
adjust them. A derived number (ratio, rank, sum) is computed from verified
inputs and labeled as derived. Keep an analyst's neutral voice even when the
question asks for a persona or a loaded framing; report what the data shows.
"""


def resources(methodology: MethodologyOut) -> dict[str, str]:
    """The resources by URI, the era read from the methodology's `yearlyCounts`."""
    first, last = methodology["yearlyCounts"]
    return {
        "rankless://schema/entity-types": ENTITY_TYPES.format(first=first, last=last),
        "rankless://guide/agent": AGENT_GUIDE,
    }
