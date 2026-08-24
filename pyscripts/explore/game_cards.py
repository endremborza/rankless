"""Generate verified clue-ladder cards for the guessing game.

A generator workflow over `pyscripts/explore/generation.py`: one agentic
session per entity writes a 6-clue ladder (hardest first) over the MCP tools;
every cited number is re-issued deterministically (`verify.verify_facts`) and
clue text is linted against name/acronym/city leaks. Accepted cards land as
`game-card` objects, which the `/game` route reads server-side.

    uv run -m pyscripts game-cards --backend local --count 24
"""

import unicodedata

from pyscripts.explore import generation, runner, verify

MIN_CLUES = 5
N_CLUES = 6

ACRONYM_SKIP = {"of", "the", "and", "for", "de", "la", "du", "des", "di"}

GENERIC_NAME_TOKENS = {
    "university",
    "universities",
    "institute",
    "institution",
    "institutions",
    "college",
    "school",
    "academy",
    "national",
    "federal",
    "royal",
    "state",
    "technology",
    "technical",
    "science",
    "sciences",
    "research",
    "center",
    "centre",
    "medical",
    "medicine",
    "hospital",
    "laboratory",
    "the",
    "and",
    "for",
    "des",
    "universite",
    "universitat",
    "universidad",
    "universidade",
    "universita",
}

_SYSTEM = """\
You are the puzzle writer for "guess the university" on Rankless, a scholarly
citation explorer. Players see clues one at a time, hardest first, and try to
locate the hidden institution on a world map as early as possible.

You have live MCP tools over the rankless backend (search_entities,
get_top_entities, get_entity_profile, get_entity_stats, get_citation_tree,
get_papers, get_peers). Explore the target before writing: profile, stats,
citation trees, top papers, peers. Hunt for what makes it DISTINCTIVE —
surprising field mixes, David-vs-Goliath standings, landmark papers, odd
collaboration geography.

Write EXACTLY {n_clues} clues, stages 1..{n_clues}, hardest to easiest:
- Stages 1-2: no geographic signal at all — research-profile quirks,
  cross-field surprises, the shape of its output over time.
- Stages 3-4: scale and indirect hints — citation/paper magnitudes, standing
  among peers, dominant fields; collaboration patterns may gesture at a region.
- Stage 5: the continent or broad region may be named.
- Stage 6: the country may be named; a near-giveaway short of the name.
- NEVER, at any stage: the institution's name, its acronym, or its city.
  Never name the country before stage 6.

Clue voice: 1-2 punchy quiz sentences, numbers woven in. Every number or
ranked claim needs a `facts` entry: the exact `tool`, `args`, a dotted `path`
into that call's JSON result, and the value you saw as `claimed`. The calls
are re-issued and clues with unreproducible facts are DROPPED, so make args
and path exact. `path` examples: `windowPapers`, `topSubfields[0].citations`,
`relations.paper-fields[1].score`, `papers[0].year`. Prefer one or two strong
verified numbers per clue over vague flavor.

Respond with ONLY a JSON object (no markdown fences):
{{"clues": [{{"stage": 1, "text": "...",
  "facts": [{{"tool": "...", "args": {{}}, "path": "...", "claimed": 0}}]}}]}}
"""


def main(
    *,
    backend: str = "local",
    etype: str = "institutions",
    count: int = 24,
    pool: int = 250,
    per_country: int = 4,
    sem_ids: str = "",
    model: str = "sonnet-5",
    engine: str = runner.DEFAULT_RUNNER,
    concurrency: int = 3,
    refresh: bool = False,
    session: str = "",
) -> None:
    """Generate verified clue cards into the MCP object store; each run is an
    mcp_session and writes one immutable bundle; --count new cards per run
    (--refresh re-mines carded entities; --sem-ids overrides pool selection;
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
        f'Write the clue ladder for the institution "{target["name"]}" '
        f"({target['distinctText']}), semantic_id `{target['semId']}`. "
        "Explore it with the tools first, then respond with the JSON only."
    )


async def _build_card(target: dict, parsed: dict, log: list[str]) -> dict | None:
    sem = target["semId"]
    kept = []
    for clue in sorted(parsed.get("clues", []), key=lambda c: c.get("stage", 0)):
        bad = await verify.verify_facts(clue.get("facts", []))
        leaks = _leaks(clue.get("text", ""), target)
        if bad or leaks:
            reasons = [f"fact {f['tool']}:{f.get('path')}" for f in bad] + leaks
            generation.log_note(
                log, SPEC.workflow, f"{sem}: drop stage {clue.get('stage')}: {reasons}"
            )
            continue
        kept.append(clue)
    if len(kept) < MIN_CLUES:
        generation.log_note(
            log, SPEC.workflow, f"{sem}: only {len(kept)} clean clues, card rejected"
        )
        return None
    for i, clue in enumerate(kept[:N_CLUES], 1):
        clue["stage"] = i
    return {
        "title": target["name"],
        "payload": {
            "semId": sem,
            "name": target["name"],
            "cc": target["cc"],
            "lat": target["lat"],
            "lon": target["lon"],
            "papers": target["papers"],
            "citations": target["citations"],
            "clues": kept[:N_CLUES],
        },
    }


def _leaks(text: str, target: dict) -> list[str]:
    folded = _fold(text)
    squeezed = folded.replace(" ", "")
    leaks = []
    all_tokens = _tokens(target["name"])
    for token in all_tokens:
        if token not in GENERIC_NAME_TOKENS and len(token) >= 3 and token in folded:
            leaks.append(f"name token {token!r}")
    acronyms = {
        "".join(t[0] for t in all_tokens),
        "".join(t[0] for t in all_tokens if t not in ACRONYM_SKIP),
    }
    for acronym in acronyms:
        if len(acronym) >= 3 and acronym in squeezed:
            leaks.append(f"acronym {acronym!r}")
    city = target.get("distinctText", "").split(",")[0].strip()
    for token in _tokens(city):
        if len(token) >= 3 and token in folded:
            leaks.append(f"city token {token!r}")
    return leaks


def _fold(s: str) -> str:
    stripped = "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )
    return "".join(c if c.isalnum() else " " for c in stripped.lower())


def _tokens(s: str) -> list[str]:
    return [t for t in _fold(s).split() if t]


SPEC = generation.GeneratorSpec(
    workflow="game-cards",
    kind="game-card",
    title="Game cards",
    max_turns=60,
    timeout_s=1200,
    require_coords=True,
    system_prompt=lambda _etype: _SYSTEM.format(n_clues=N_CLUES),
    user_prompt=_user_prompt,
    build_object=_build_card,
)
