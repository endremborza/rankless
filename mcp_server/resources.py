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

1. Resolve first: turn every name into a semantic_id via search_entities (or
   lookup_orcid). Disambiguate homonyms by papers/citations/distinctText.
2. Aggregate second: get_entity_profile / get_entity_stats / get_citation_tree
   / get_peers / get_papers over resolved ids.
3. Every response carries rankless_url backlinks - cite them so humans can
   verify.
4. All numbers are deterministic backend aggregates; the same call always
   returns the same value. Never invent or extrapolate numbers.
"""

RESOURCES = {
    "rankless://schema/entity-types": ENTITY_TYPES,
    "rankless://guide/agent": AGENT_GUIDE,
}
