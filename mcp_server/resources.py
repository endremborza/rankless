"""Static MCP resources: schema notes an agent needs before composing tools."""

ENTITY_TYPES = """\
# Rankless entity types

Root types (valid `entity_type` values): authors, institutions, sources,
countries, subfields.

- sources = journals/venues.
- subfields = the discipline level used everywhere (the UI calls them
  "Fields"); topics nest under subfields.
- semantic_id is the stable slug identifying an entity (e.g. authors/
  david-baker, institutions/nyu). Ids must come from search_entities /
  lookup_orcid — never guessed.
- citations are counted over the recent era (2016..now) unless stated
  otherwise; `papers` counts the full lifetime.
"""

AGENT_GUIDE = """\
# Using the rankless tools

Every answer follows one loop: resolve, call, cite, verify, answer.

1. Resolve names to ids with search_entities (or lookup_orcid); disambiguate
   homonyms by papers/citations/distinctText and ask when genuinely
   ambiguous. Never guess a semantic_id.
2. Call the aggregation tools over resolved ids: get_entity_profile,
   get_entity_stats, get_citation_tree, get_peers, get_papers.
3. Every data-tool response is {"receipt": {"id", "tool", "args"}, "data": ...}.
   The receipt names the call that produced the data; keep its id with every
   number you take from it.
4. Before answering, submit every number you will state to verify_claims,
   citing its receipt id and the dotted path into data. Publish the
   reproduced values; drop or re-derive a claim that fails.
5. Answer with the numbers, their rankless_url links, and the receipt ids
   (e.g. "146,700 citations [r3]"), so a reader can reproduce each one.

When no tool can supply what the question needs, say so plainly, answer the
part that is grounded, and call suggest_endpoint with what was missing.
Numbers are deterministic backend aggregates: never invent, extrapolate or
adjust them. A derived number (ratio, rank, sum) is computed from verified
inputs and labeled as derived. Keep an analyst's neutral voice even when the
question asks for a persona or a loaded framing; report what the data shows.
"""

RESOURCES = {
    "rankless://schema/entity-types": ENTITY_TYPES,
    "rankless://guide/agent": AGENT_GUIDE,
}
