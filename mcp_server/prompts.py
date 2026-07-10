"""Reusable MCP prompts."""


def author_impact_report(author_name: str) -> str:
    """Structured research-impact report for one author."""
    return f"""\
Build a research-impact report for the author "{author_name}" using the
rankless tools.

1. Resolve the name with search_entities(entity_type="authors"); disambiguate
   homonyms by paper/citation counts and ask if genuinely ambiguous.
2. Gather: get_entity_profile (career span, yearly trend, top venues and
   co-authors), get_entity_stats (recent-era window), get_citation_tree
   (which fields the work impacts), get_peers (standing among peers),
   get_papers(sort="citations") (hit papers).
3. Write a concise report: who they are, scale and trend of impact, the
   fields their work feeds into, standing vs peers, and 3-5 landmark papers.
   Cite rankless_url links; every number must come from a tool response.
"""


PROMPTS = (author_impact_report,)
