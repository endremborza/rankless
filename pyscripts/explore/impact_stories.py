"""Generate verified per-entity impact stories.

A generator workflow over `pyscripts/explore/generation.py`: one agentic
session per entity writes a short, numbers-driven narrative of how the target's
research gets used — where its citations flow, who builds on its landmark
papers, its standing among peers. Every cited number is re-issued
(`verify.verify_facts`); a story with any unreproducible fact is dropped.
Accepted stories land as `impact-story` objects; approved ones show publicly on
`/mcp` alongside findings.

    uv run -m pyscripts impact-stories --backend local --etype authors --count 12
"""

from pyscripts.explore import generation, runner, verify

MIN_FACTS = 2

_SYSTEM = """\
You are an impact analyst for Rankless, a scholarly citation explorer. You have
live MCP tools over its backend (search_entities, get_top_entities,
get_entity_profile, get_entity_stats, get_citation_tree, get_papers, get_peers).

Write ONE tight impact story about the target {etype} entity: how its research
is USED. Explore first — its citation tree (where the citing work comes from
and what fields it feeds), its landmark papers and what builds on them, its
standing among peers, surprising downstream adopters. Then write 4-7 specific
sentences with the key numbers woven in, plus a punchy title.

Every number or ranked claim needs a `facts` entry: the exact `tool`, `args`,
a dotted `path` into that call's JSON result, and the value you saw as
`claimed`. The calls are re-issued and a story with any unreproducible fact is
DROPPED, so make args and path exact. Include at least {min_facts} facts.

Respond with ONLY a JSON object (no markdown fences):
{{"title": "...", "story": "...",
  "facts": [{{"tool": "...", "args": {{}}, "path": "...", "claimed": 0}}]}}
"""


def main(
    *,
    backend: str = "local",
    etype: str = "institutions",
    count: int = 12,
    pool: int = 250,
    per_country: int = 4,
    sem_ids: str = "",
    model: str = "sonnet-5",
    engine: str = runner.DEFAULT_RUNNER,
    concurrency: int = 3,
    refresh: bool = False,
    session: str = "",
) -> None:
    """Generate verified impact stories into the MCP object store; each run is
    an mcp_session and writes one immutable bundle; --count new stories per run
    (--refresh re-mines storied entities; --sem-ids overrides pool selection;
    --session joins a worker-claimed session row; --backend as in explore.deep)."""
    generation.run(
        SPEC,
        backend=backend,
        etype=etype,
        count=count,
        pool=pool,
        per_country=per_country,
        sem_ids=sem_ids,
        model=model,
        engine=engine,
        concurrency=concurrency,
        refresh=refresh,
        session=session,
    )


def _user_prompt(target: dict) -> str:
    return (
        f'Write the impact story for "{target["name"]}" '
        f"({target['distinctText']}), semantic_id `{target['semId']}`. "
        "Explore it with the tools first, then respond with the JSON only."
    )


async def _build_story(target: dict, parsed: dict, log: list[str]) -> dict | None:
    sem = target["semId"]
    title = (parsed.get("title") or "").strip()
    story = (parsed.get("story") or "").strip()
    facts = parsed.get("facts", [])
    if not title or not story:
        generation.log_note(log, SPEC.workflow, f"{sem}: empty title/story, dropped")
        return None
    if len(facts) < MIN_FACTS:
        generation.log_note(
            log, SPEC.workflow, f"{sem}: only {len(facts)} facts, dropped"
        )
        return None
    if bad := await verify.verify_facts(facts):
        reasons = [f"{f['tool']}:{f.get('path')}" for f in bad]
        generation.log_note(
            log, SPEC.workflow, f"{sem}: unreproducible facts {reasons}, dropped"
        )
        return None
    return {
        "title": title,
        "payload": {
            "semId": sem,
            "name": target["name"],
            "cc": target["cc"],
            "papers": target["papers"],
            "citations": target["citations"],
            "title": title,
            "story": story,
            "facts": facts,
        },
    }


SPEC = generation.GeneratorSpec(
    workflow="impact-stories",
    kind="impact-story",
    title="Impact stories",
    max_turns=60,
    timeout_s=1200,
    require_coords=False,
    system_prompt=lambda etype: _SYSTEM.format(etype=etype, min_facts=MIN_FACTS),
    user_prompt=_user_prompt,
    build_object=_build_story,
)
