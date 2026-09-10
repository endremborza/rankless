"""Mine the geography-quiz cards for CampusQuest: one mixed round over every
card kind.

The round is batch-prompted: the backend already knows each institution's
name, city and country, so the model's only job is judgment — which anchor a
player recognizes, which wrong answer tempts rather than fills, and which kind
a given institution makes the best card for. The model never states an
answer: a proposal is a question shape (kind, anchor, option entities or decoy
names, reveal sentence). Every answer and constraint is then recomputed from
the institutions' coordinates and places, re-issued through
`mcp_server.verify` as `get_entity_profile` facts and stored on the card as
`facts` (the model states no numbers, so the facts carry no `claimed`); a card
failing any check is dropped, never corrected. Each batch sees a chunk of
anchor candidates from the citation-ordered slice plus the
recognizable-institution roster as its option pool, the roster's tier being
the fame prior the model reasons over. One immutable bundle holds every kind;
`(kind, semId)` is the skip key, so an anchor can carry one card per kind, and
the per-country cap applies per kind.

    uv run -m pyscripts rankless-game-card-mining --backend local --count 100
"""

import asyncio
import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

import mcp_server
from mcp_server import client as be_client
from mcp_server import verify
from pyscripts.explore import cli, object_mining, runner

WORKFLOW = "rankless-game-card-mining"
TITLE = "Game cards"
ETYPE = "institutions"
KINDS = ("country-card", "intruder-card", "nearest-card", "city-card", "local-card")
# option entities a proposal names per kind; the anchor itself is the fourth
# option of the intruder and local kinds
N_OPTIONS = {"nearest-card": 4, "intruder-card": 3, "local-card": 3}
N_DECOYS = 3
NEAREST_MARGIN = 2.0
NEAREST_MAX_KM = 2000.0
EARTH_RADIUS_KM = 6371.0
BATCH_SIZE = 40
TIMEOUT_S = 600
NOTE_LEN = (20, 300)
FACT_TOOL = "get_entity_profile"
FACT_PATHS = ("meta.lat", "meta.lon", "distinctText")

ISO2_PATH = Path("src/lib/assets/data/country-alpha-2-to-3.json")
ROSTER_PATH = Path("src/lib/assets/data/recognizable-institutions.json")

# Names every country has one of: the English translation is arbitrary and the
# pick is a guess, so they anchor nothing. "National <Proper Noun> University"
# stays — those point at a namesake elsewhere.
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
You curate cards for CampusQuest, a geography speed quiz on Rankless, a
scholarly citation explorer: players see one prompt and four tappable options
and answer within seconds. Every card is one of five kinds, each asking one
fixed question:

- country-card — prompt: an institution; options: four countries. "Where is
  it actually?" Good anchors are lesser-known institutions whose names point
  at a SPECIFIC wrong place — another country's city or region, a person, a
  saint or royal title that reads as British, a cross-border region or river.
  Skip names that state or clearly imply their country, best-known city or
  demonym; a name merely in the local language is only a weak signal. Skip
  hospitals unless the name itself is a strong misdirect (a saint, royal or
  person name), never one named after its own city. Skip names shared with
  institutions elsewhere; if you keep one anyway, never use a namesake's
  country as a decoy. Give exactly 3 decoy ISO 3166-1 alpha-2 codes, including
  the country the name evokes most.
- city-card — prompt: an institution; options: four cities. "Which city?"
  Best anchors are famous institutions with unobvious cities (CERN, EMBL, a
  Max Planck institute); the name must not contain its city. Give 3 decoy
  city names a player might guess — real cities, never the true one.
- nearest-card — prompt: an institution; options: four institutions. "Which
  is closest?" The anchor must be recognizable (tier 1); pick four option
  institutions so that one is clearly the nearest (at least twice as close as
  any other) and rough geographic sense can reason it out. Distances are
  computed, never stated.
- intruder-card — prompt: a country; options: four institutions, three in
  that country and one elsewhere. "Which one is not here?" The anchor IS the
  intruder: an institution whose name reads as that country but sits
  elsewhere (misdirecting names are ideal). Give the three in-country
  institutions as options; their names should read as the country.
- local-card — prompt: a city; options: four institutions, one in that city
  and three elsewhere. "Which one is here?" The anchor IS the local one. All
  four must be placeable by an informed player, and no option's name may
  contain the city.

You never state an answer, a country, a distance or a number: every answer is
recomputed from the data and a card failing any check is dropped. Your
judgment is what makes a card interesting: which anchor a player recognizes,
which wrong answer is tempting rather than filler, and which kind a given
institution makes the best card for.

You get a ROSTER of recognizable institutions (tier 1 globally famous, tier 2
regionally known) usable as options in any card, then CANDIDATES to anchor
cards, each with the kinds it is already carded for — propose other kinds for
those. Entities are referenced by id; options must be ids from the roster or
the candidate list. Propose one card per worthy candidate, of the kind it
supports best; usually only a minority qualifies. Every card gets a "note":
one reveal sentence (shown after answering) saying where it really is and why
the wrong answer tempted.

Respond with ONLY a JSON object (no markdown fences):
{"cards": [{"kind": "...", "anchor": "<id>", "options": ["<id>", ...],
  "decoys": ["...", ...], "note": "..."}]}
`options` holds ids (nearest 4, intruder 3, local 3); `decoys` holds 3 ISO
codes (country-card) or 3 city names (city-card).
"""


@dataclass(frozen=True)
class Place:
    sem_id: str
    name: str
    city: str
    cc: str
    lat: float = 0.0
    lon: float = 0.0
    papers: int = 0
    citations: int = 0


@dataclass(frozen=True)
class World:
    """What a proposal is judged against: the ISO country set, the pool's city
    names by their folded form, and country names by code."""

    iso2: frozenset[str]
    cities: dict[str, str]
    country_names: dict[str, str]


def main(
    *,
    backend: str = "local",
    etype: str = ETYPE,
    count: int = 100,
    pool: int = 3000,
    skip: int = 0,
    per_country: int = 20,
    model: str = "sonnet-5",
    engine: str = runner.DEFAULT_RUNNER,
    session: str = "",
) -> None:
    """Mine geography-quiz cards of every kind into the MCP object store; each
    run is an mcp_session and writes one immutable bundle. Candidates come from
    the citation-ordered slice ranks --skip..--skip+--pool; --count caps new
    cards per run, --per-country caps each kind's pack per country (--session
    joins a worker-claimed session row; --backend as in explore.deep)."""
    if engine != runner.DEFAULT_RUNNER:
        raise SystemExit(
            f"{WORKFLOW} only supports the {runner.DEFAULT_RUNNER!r} engine"
        )
    if etype != ETYPE:
        raise SystemExit(f"{WORKFLOW} mines {ETYPE} only")
    backend_url, backend_label = mcp_server.resolve_backend(backend)
    mcp_server.set_backend(backend_url)
    model = cli.resolve_model(model)
    object_mining.run_bundle(
        workflow=WORKFLOW,
        title=TITLE,
        etype=etype,
        backend=backend,
        backend_label=backend_label,
        model=model,
        count=count,
        kinds=KINDS,
        session=session,
        generate=lambda con: _generate(con, count, pool, skip, per_country, model),
        report_line=report_line,
    )


def is_generic_name(name: str) -> bool:
    return _GENERIC_RE.search(name) is not None


def haversine_km(a: Place, b: Place) -> float:
    d_lat = radians(b.lat - a.lat)
    d_lon = radians(b.lon - a.lon)
    h = sin(d_lat / 2) ** 2 + cos(radians(a.lat)) * cos(radians(b.lat)) * (
        sin(d_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))


def place_parts(distinct_text: str) -> tuple[str, str]:
    """(city, cc) from an institution's `City, 🇭🇺` distinct text."""
    city = distinct_text.split(",")[0].strip() if "," in distinct_text else ""
    return city, object_mining.flag_cc(distinct_text)


def judge(
    kind: str, anchor: Place, options: list[Place], decoys: list[str], world: World
) -> tuple[dict | None, str]:
    """The kind-specific payload fragment a proposal earns from the data, or
    the reason it is dropped. Answers are never taken from the proposal."""
    if kind == "country-card":
        return _judge_country(anchor, decoys, world)
    if kind == "city-card":
        return _judge_city(anchor, decoys, world)
    if kind == "nearest-card":
        return _judge_nearest(anchor, options)
    if kind == "intruder-card":
        return _judge_intruder(anchor, options, world)
    return _judge_local(anchor, options)


def names(haystack: str, needle: str | None) -> bool:
    """Whether every word of `needle` appears as a word of `haystack`, accents
    and case folded — so "Georgia" is found in "University of Georgia" but
    "India" not in "Indiana University"."""
    if not needle:
        return False
    return set(_tokens(needle)) <= set(_tokens(haystack))


def report_line(o: dict) -> str:
    p = o["payload"]
    opts = p.get("options", [])
    if o["kind"] == "country-card":
        detail = f"{p['cc']} vs {', '.join(p['decoys'])}"
    elif o["kind"] == "city-card":
        detail = f"{p['city']} vs {', '.join(p['decoys'])}"
    elif o["kind"] == "nearest-card":
        detail = ", ".join(f"{x['name']} {x['km']} km" for x in opts)
    elif o["kind"] == "intruder-card":
        detail = f"not in {p['country']}: {', '.join(x['name'] for x in opts)}"
    else:
        detail = f"in {p['city']} vs {', '.join(x['name'] for x in opts)}"
    return f"- `{o['sem_id']}` [{o['kind']}] — {o['title']} ({detail})"


def _judge_country(
    anchor: Place, decoys: list[str], world: World
) -> tuple[dict | None, str]:
    codes = [d.upper() for d in decoys]
    if len(codes) != N_DECOYS or len(set(codes)) != N_DECOYS or anchor.cc in codes:
        return None, "need 3 distinct decoy countries other than the true one"
    if unknown := [c for c in codes if c not in world.iso2]:
        return None, f"unknown decoy code(s) {unknown}"
    if named := [c for c in codes if names(anchor.name, world.country_names.get(c))]:
        return None, f"decoy country named in the institution {named}"
    return {"decoys": codes}, ""


def _city_anchor_reject(anchor: Place) -> str:
    if not anchor.city:
        return "anchor has no city"
    if names(anchor.name, anchor.city):
        return "anchor names its own city"
    return ""


def _judge_city(
    anchor: Place, decoys: list[str], world: World
) -> tuple[dict | None, str]:
    if why := _city_anchor_reject(anchor):
        return None, why
    folded = [_fold(d) for d in decoys]
    if len(decoys) != N_DECOYS or len(set(folded)) != N_DECOYS:
        return None, "need 3 distinct decoy cities"
    if _fold(anchor.city) in folded:
        return None, "the true city is among the decoys"
    if unknown := [d for d, f in zip(decoys, folded) if f not in world.cities]:
        return None, f"decoy cities not in the pool {unknown}"
    if named := [d for d in decoys if names(anchor.name, d)]:
        return None, f"decoy city named in the institution {named}"
    return {"city": anchor.city, "decoys": [world.cities[f] for f in folded]}, ""


def _judge_nearest(anchor: Place, options: list[Place]) -> tuple[dict | None, str]:
    if not all(map(_located, [anchor, *options])):
        return None, "an institution has no coordinates"
    ranked = sorted(haversine_km(anchor, o) for o in options)
    if ranked[0] > NEAREST_MAX_KM:
        return None, f"nearest is {ranked[0]:.0f} km away, over the ceiling"
    if ranked[1] <= ranked[0] * NEAREST_MARGIN:
        return None, f"no clear nearest ({ranked[0]:.0f} vs {ranked[1]:.0f} km)"
    return {
        **_coords(anchor),
        "options": [
            {**_option(o), **_coords(o), "km": round(haversine_km(anchor, o))}
            for o in options
        ],
    }, ""


def _judge_intruder(
    anchor: Place, options: list[Place], world: World
) -> tuple[dict | None, str]:
    ccs = {o.cc for o in options}
    if len(ccs) != 1 or "" in ccs:
        return None, "the three locals must share one country"
    country = ccs.pop()
    if not anchor.cc or anchor.cc == country:
        return None, "the intruder is in the asked country"
    if is_generic_name(anchor.name):
        return None, "generic intruder name"
    if names(anchor.name, world.country_names.get(anchor.cc)):
        return None, "the intruder names its own country"
    return {"country": country, "options": [_option(o) for o in options]}, ""


def _judge_local(anchor: Place, options: list[Place]) -> tuple[dict | None, str]:
    if why := _city_anchor_reject(anchor):
        return None, why
    if same := [o.name for o in options if _fold(o.city) == _fold(anchor.city)]:
        return None, f"options in the asked city {same}"
    if named := [o.name for o in options if names(o.name, anchor.city)]:
        return None, f"options naming the city {named}"
    return {
        "city": anchor.city,
        "options": [{**_option(o), "city": o.city} for o in options],
    }, ""


def _option(p: Place) -> dict:
    return {"semId": p.sem_id, "name": p.name, "cc": p.cc}


def _coords(p: Place) -> dict:
    return {"lat": round(p.lat, 3), "lon": round(p.lon, 3)}


def _located(p: Place) -> bool:
    return p.lat != 0 or p.lon != 0


def _fold(s: str) -> str:
    stripped = "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )
    return "".join(c if c.isalnum() else " " for c in stripped.lower()).strip()


def _tokens(s: str) -> list[str]:
    return _fold(s).split()


def _generate(
    con: sqlite3.Connection,
    count: int,
    pool: int,
    skip: int,
    per_country: int,
    model: str,
) -> tuple[list[dict], int, list[str]]:
    have = {kind: object_mining.stored_ccs(con, kind, ETYPE) for kind in KINDS}
    index, world = asyncio.run(_load_pool(skip, pool))
    tiers = _roster(index)
    candidates = [p for p in index.values() if p.cc and not is_generic_name(p.name)]
    print(
        f"[{WORKFLOW}] {len(candidates)} candidate(s) from slice {skip}..{skip + pool}, "
        f"{len(tiers)} on the roster; model={model}; "
        f"{sum(map(len, have.values()))} card(s) already stored"
    )
    caps = {k: object_mining.CcCap(have[k].values(), per_country) for k in KINDS}
    log: list[str] = []
    objects: list[dict] = []
    failures = 0
    for start in range(0, len(candidates), BATCH_SIZE):
        if len(objects) >= count:
            break
        chunk = candidates[start : start + BATCH_SIZE]
        try:
            raw = cli.query_claude_cli(
                _SYSTEM,
                _user_prompt(index, tiers, chunk, have),
                model,
                timeout_s=TIMEOUT_S,
            )
            proposals = cli.parse_json(raw).get("cards", [])
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            object_mining.log_note(log, WORKFLOW, f"batch at {start}: failed ({exc})")
            failures += 1
            # a dead auth or exhausted usage window fails every batch; an
            # idempotent rerun resumes later
            if failures >= object_mining.BREAK_AFTER:
                object_mining.log_note(
                    log, WORKFLOW, f"aborting after {failures} consecutive failures"
                )
                break
            continue
        failures = 0
        objects += asyncio.run(
            _build_batch(proposals, index, world, have, caps, count - len(objects), log)
        )
    return objects, len(candidates), log


async def _load_pool(skip: int, pool: int) -> tuple[dict[str, Place], World]:
    try:
        ranked = await be_client.get_json(f"/slice/{ETYPE}/{skip}/{skip + pool}")
        countries = await be_client.get_json("/slice/countries/0/400")
    finally:
        await be_client.aclose()
    index: dict[str, Place] = {}
    for ent in ranked:
        city, cc = place_parts(ent.get("distinctText", ""))
        index[ent["semanticId"]] = Place(
            ent["semanticId"],
            ent["name"],
            city,
            cc,
            papers=ent.get("papers", 0),
            citations=ent.get("citations", 0),
        )
    iso2_to_3: dict[str, str] = json.loads(ISO2_PATH.read_text())
    iso3_to_2 = {v.lower(): k for k, v in iso2_to_3.items()}
    world = World(
        iso2=frozenset(iso2_to_3),
        cities={_fold(p.city): p.city for p in index.values() if p.city},
        country_names={
            cc: c["name"] for c in countries if (cc := iso3_to_2.get(c["semanticId"]))
        },
    )
    return index, world


def _roster(index: dict[str, Place]) -> dict[str, int]:
    """Tier by roster id, for the ids the pool carries."""
    if not ROSTER_PATH.exists():
        raise SystemExit(f"{ROSTER_PATH} missing: the roster is the round's fame prior")
    tiers: dict[str, int] = json.loads(ROSTER_PATH.read_text())
    if missing := [s for s in tiers if s not in index]:
        print(f"[{WORKFLOW}] {len(missing)} roster id(s) outside the pool: {missing}")
    return {s: t for s, t in tiers.items() if s in index}


def _user_prompt(
    index: dict[str, Place],
    tiers: dict[str, int],
    chunk: list[Place],
    have: dict[str, dict[str, str]],
) -> str:
    def line(p: Place) -> str:
        return f"{p.sem_id}\t{p.name}\t{p.city}\t{p.cc}\t{tiers.get(p.sem_id, '')}"

    roster = "\n".join(line(index[s]) for s in tiers)
    candidates = "\n".join(
        f"{line(p)}\t{','.join(k for k in KINDS if p.sem_id in have[k])}" for p in chunk
    )
    return (
        "ROSTER (id, name, city, country, tier):\n"
        f"{roster}\n\n"
        "CANDIDATES (id, name, city, country, tier, kinds already carded):\n"
        f"{candidates}\n\n"
        "Propose the cards and respond with the JSON only."
    )


async def _build_batch(
    proposals: list[dict],
    index: dict[str, Place],
    world: World,
    have: dict[str, dict[str, str]],
    caps: dict[str, object_mining.CcCap],
    room: int,
    log: list[str],
) -> list[dict]:
    calls: dict[str, object] = {}
    objects: list[dict] = []
    try:
        for prop in proposals:
            if len(objects) >= room:
                break
            obj, why = await _build_card(prop, index, world, calls)
            sem = str(prop.get("anchor", "?"))
            if obj is None:
                object_mining.log_note(log, WORKFLOW, f"drop {sem}: {why}")
                continue
            kind, cc = obj["kind"], obj["payload"]["cc"]
            if sem in have[kind]:
                object_mining.log_note(
                    log, WORKFLOW, f"drop {sem}: {kind} already carded"
                )
                continue
            if caps[kind].full(cc):
                object_mining.log_note(
                    log, WORKFLOW, f"drop {sem}: {kind} {cc} at per-country cap"
                )
                continue
            caps[kind].add(cc)
            have[kind][sem] = cc
            objects.append(obj)
    finally:
        await be_client.aclose()
    return objects


async def _build_card(
    prop: dict, index: dict[str, Place], world: World, calls: dict[str, object]
) -> tuple[dict | None, str]:
    kind = prop.get("kind")
    if kind not in KINDS:
        return None, f"unknown kind {kind!r}"
    anchor = index.get(str(prop.get("anchor", "")))
    if anchor is None:
        return None, "anchor not in the pool"
    ids = [str(s) for s in prop.get("options") or []]
    n = N_OPTIONS.get(kind, 0)
    if len(ids) != n or len(set(ids)) != n or anchor.sem_id in ids:
        return None, f"need {n} distinct option ids"
    if unknown := [s for s in ids if s not in index]:
        return None, f"option ids not in the pool {unknown}"
    note = str(prop.get("note", "")).strip()
    if not NOTE_LEN[0] <= len(note) <= NOTE_LEN[1]:
        return None, f"note length {len(note)} outside {NOTE_LEN}"
    entities = [anchor, *(index[s] for s in ids)]
    facts = [_fact(e, path) for e in entities for path in FACT_PATHS]
    if bad := await verify.verify_facts(facts, calls):
        failed = [f"{f['args']['semantic_id']}:{f['path']}" for f in bad]
        return None, f"unreproducible facts {failed}"
    placed = _placed(entities, facts)
    decoys = [str(d).strip() for d in prop.get("decoys") or []]
    fragment, why = judge(kind, placed[0], placed[1:], decoys, world)
    if fragment is None:
        return None, why
    return {
        "kind": kind,
        "obj_key": f"{ETYPE}|{anchor.sem_id}",
        "etype": ETYPE,
        "sem_id": anchor.sem_id,
        "title": anchor.name,
        "payload": {
            "semId": anchor.sem_id,
            "name": anchor.name,
            "cc": placed[0].cc,
            "note": note,
            "papers": anchor.papers,
            "citations": anchor.citations,
            "facts": facts,
            **fragment,
        },
    }, ""


def _fact(p: Place, path: str) -> dict:
    return {
        "tool": FACT_TOOL,
        "args": {"entity_type": ETYPE, "semantic_id": p.sem_id},
        "path": path,
        "claimed": None,
    }


def _placed(entities: list[Place], facts: list[dict]) -> list[Place]:
    """Places rebuilt from the reproduced facts, three per entity in
    FACT_PATHS order."""
    out = []
    for i, e in enumerate(entities):
        lat, lon, distinct = (f["reproduced"] for f in facts[3 * i : 3 * i + 3])
        city, cc = place_parts(str(distinct))
        out.append(
            Place(
                e.sem_id,
                e.name,
                city,
                cc,
                float(lat),
                float(lon),
                e.papers,
                e.citations,
            )
        )
    return out
