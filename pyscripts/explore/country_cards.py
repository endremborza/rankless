"""Generate country-quiz cards for the misleading-institution-names game.

Unlike the per-entity agentic generators (game_cards, impact_stories), this
workflow is batch-prompted: the backend already knows every institution's name
and country, so the LLM's only job is judgment — from a deep slice of mid-tier
institutions, keep the ones whose names mislead about (or say nothing about)
their country, and write three plausible decoy countries plus a one-sentence
post-answer reveal. Decoys are validated against the ISO country set and the
true country; accepted picks land as `country-card` objects, which the
country-game route reads server-side. Run lifecycle, candidate slicing,
and the per-country cap come from the shared engine (`generation.py`).

    uv run -m pyscripts country-cards --backend local --count 60
"""

import asyncio
import json
import re
import sqlite3
from pathlib import Path

import mcp_server
from pyscripts.explore import cli, generation, runner

WORKFLOW = "country-cards"
KIND = "country-card"
TITLE = "Country cards"

BATCH_SIZE = 40
TIMEOUT_S = 600
NOTE_LEN = (20, 300)

ISO2_PATH = "src/lib/assets/data/country-alpha-2-to-3.json"

# Names every country has one of: the English translation is arbitrary and the
# pick is a guess, so they never reach the model. "National <Proper Noun>
# University" stays — those point at a namesake elsewhere.
_GENERIC_RE = re.compile(
    r"^(?:national|state|federal|central|regional|general)\s+"
    r"(?:institutes?|research|councils?|cent(?:er|re)s?|laborator(?:y|ies)|academy|"
    r"physical|cancer|defen[cs]e|medical|health|university of)\b"
    r"|^(?:southern|northern|eastern|western|central|capital|general|first|second|third|fourth)"
    r"\s+(?:medical|military)(?:\s+medical)?\s+university\b"
    r"|\b(?:army|air force|naval|navy)\b.*\b(?:university|college|academy)\b"
    r"|^(?:institutes?|cent(?:er|re)s?) (?:of|for) [a-z ,&-]+$",
    re.I,
)

_SYSTEM = """\
You curate cards for a country-guessing speed quiz on Rankless, a scholarly
citation explorer: players see a real research institution's name and must
pick its country from four options within seconds. Good cards are lesser-known
institutions whose names point at a SPECIFIC wrong place — another country's
city or region, a person, a saint or royal title that reads as British, a
cross-border region or river. The name must give the player somewhere wrong
to go: a name that says nothing makes the pick a coin toss, not a misdirection.
Skip any name that states or clearly implies its country, its best-known city,
or its demonym; a name merely being in the local language is only a weak
signal. Skip generic institutional names outright — "National/State/Central
Institute/Council/Center/Laboratory of X", "<Adjective> Medical University",
numbered or military universities: every country has one and the English
translation is arbitrary. Hospitals and medical schools only when the name
itself is a strong misdirect (a saint, royal or person name), never one named
after its own city; the pack already has plenty of them.
Also skip any name shared with other institutions elsewhere; if you keep such
a name anyway, never use a namesake's country as a decoy — a player who knows
the other bearer would be marked wrong.
Prefer names an educated player would confidently place in the WRONG country.
Be selective: usually only a minority of a list qualifies.

You get lines of `semantic_id<TAB>institution name<TAB>ISO country`. For each
KEPT institution return:
- "decoys": exactly 3 uppercase ISO 3166-1 alpha-2 codes of OTHER countries a
  player might plausibly pick precisely because of the name — include the
  country the name evokes most; never the true country, no duplicates.
- "note": one reveal sentence (shown only after answering) saying where it
  really is and why the name points elsewhere.

Respond with ONLY a JSON object (no markdown fences):
{"picks": [{"semId": "...", "decoys": ["XX", "YY", "ZZ"], "note": "..."}]}
"""


def main(
    *,
    backend: str = "local",
    etype: str = "institutions",
    count: int = 60,
    pool: int = 1500,
    skip: int = 120,
    per_country: int = 3,
    model: str = "sonnet-5",
    engine: str = runner.DEFAULT_RUNNER,
    refresh: bool = False,
    session: str = "",
) -> None:
    """Generate validated country-quiz cards into the MCP object store; each
    run is an mcp_session and writes one immutable bundle. Candidates come from
    the citation-ordered slice ranks --skip..--skip+--pool (mid-tier = not so
    well known); --count caps new cards per run, --per-country keeps the pack
    diverse (--refresh re-mines carded entities; --session joins a
    worker-claimed session row; --backend as in explore.deep)."""
    if engine != runner.DEFAULT_RUNNER:
        raise SystemExit(
            f"{WORKFLOW} only supports the {runner.DEFAULT_RUNNER!r} engine"
        )
    backend_url, backend_label = runner.resolve_backend(backend)
    mcp_server.set_backend(backend_url)
    model = cli.resolve_model(model)
    generation.run_bundle(
        workflow=WORKFLOW,
        title=TITLE,
        etype=etype,
        backend=backend,
        backend_label=backend_label,
        model=model,
        count=count,
        kind=KIND,
        session=session,
        generate=lambda con: _generate(
            con, etype, count, pool, skip, per_country, model, refresh
        ),
        report_line=_report_line,
    )


def is_generic_name(name: str) -> bool:
    return _GENERIC_RE.search(name) is not None


def _report_line(o: dict) -> str:
    p = o["payload"]
    return f"- `{o['sem_id']}` — {o['title']} ({p['cc']} vs {', '.join(p['decoys'])})"


def _generate(
    con: sqlite3.Connection,
    etype: str,
    count: int,
    pool: int,
    skip: int,
    per_country: int,
    model: str,
    refresh: bool,
) -> tuple[list[dict], int, list[str]]:
    have = {} if refresh else generation.stored_ccs(con, KIND, etype)
    candidates = asyncio.run(_candidates(etype, skip, pool, have))
    print(
        f"[{WORKFLOW}] {len(candidates)} candidate(s) from slice "
        f"{skip}..{skip + pool}; model={model}; {len(have)} already stored"
    )
    iso2 = set(json.loads(Path(ISO2_PATH).read_text()))
    cap = generation.CcCap(have.values(), per_country)
    log: list[str] = []
    objects: list[dict] = []
    failures = 0
    for start in range(0, len(candidates), BATCH_SIZE):
        if len(objects) >= count:
            break
        chunk = candidates[start : start + BATCH_SIZE]
        try:
            raw = cli.query_claude_cli(
                _SYSTEM, _user_prompt(chunk), model, timeout_s=TIMEOUT_S
            )
            picks = cli.parse_json(raw).get("picks", [])
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            generation.log_note(log, WORKFLOW, f"batch at {start}: failed ({exc})")
            failures += 1
            # dead auth / exhausted usage window fails every batch — bail like
            # generation.py's _MineBreaker; an idempotent rerun resumes later
            if failures >= generation.BREAK_AFTER:
                generation.log_note(
                    log,
                    WORKFLOW,
                    f"aborting after {failures} consecutive batch failures",
                )
                break
            continue
        failures = 0
        by_sem = {c["semId"]: c for c in chunk}
        for pick in picks:
            if len(objects) >= count:
                break
            obj, why = _build_card(pick, by_sem, iso2, etype)
            if obj is None:
                generation.log_note(
                    log, WORKFLOW, f"drop {pick.get('semId', '?')}: {why}"
                )
                continue
            cc = obj["payload"]["cc"]
            if cap.full(cc):
                generation.log_note(
                    log, WORKFLOW, f"drop {obj['sem_id']}: {cc} at per-country cap"
                )
                continue
            cap.add(cc)
            objects.append(obj)
    return objects, len(candidates), log


async def _candidates(
    etype: str, skip: int, pool: int, have: dict[str, str]
) -> list[dict]:
    ranked = await generation.fetch_slice(etype, skip, skip + pool)
    out = []
    for ent in ranked:
        cc = generation.flag_cc(ent.get("distinctText", ""))
        if not cc or ent["semanticId"] in have or is_generic_name(ent["name"]):
            continue
        out.append(
            {
                "semId": ent["semanticId"],
                "name": ent["name"],
                "cc": cc,
                "papers": ent.get("papers", 0),
                "citations": ent.get("citations", 0),
            }
        )
    return out


def _user_prompt(chunk: list[dict]) -> str:
    lines = "\n".join(f"{c['semId']}\t{c['name']}\t{c['cc']}" for c in chunk)
    return (
        "Pick the misleadingly named institutions from this list and respond "
        f"with the JSON only.\n\n{lines}"
    )


def _build_card(
    pick: dict, by_sem: dict[str, dict], iso2: set[str], etype: str
) -> tuple[dict | None, str]:
    target = by_sem.get(pick.get("semId", ""))
    if target is None:
        return None, "semId not in batch"
    decoys = pick.get("decoys")
    if not isinstance(decoys, list) or len(decoys) != 3:
        return None, "need exactly 3 decoys"
    decoys = [str(d).upper() for d in decoys]
    if len(set(decoys)) != 3 or target["cc"] in decoys:
        return None, "duplicate decoys or true country among them"
    if unknown := [d for d in decoys if d not in iso2]:
        return None, f"unknown decoy code(s) {unknown}"
    note = str(pick.get("note", "")).strip()
    if not NOTE_LEN[0] <= len(note) <= NOTE_LEN[1]:
        return None, f"note length {len(note)} outside {NOTE_LEN}"
    return {
        "kind": KIND,
        "obj_key": f"{etype}|{target['semId']}",
        "etype": etype,
        "sem_id": target["semId"],
        "title": target["name"],
        "payload": {
            "semId": target["semId"],
            "name": target["name"],
            "cc": target["cc"],
            "decoys": decoys,
            "note": note,
            "papers": target["papers"],
            "citations": target["citations"],
        },
    }, ""
