"""Mine the geography-quiz cards for CampusQuest: one mixed round over every
card kind.

The round is batch-prompted and split between a deterministic harness and the
model: the harness decides what is *unusable* — "entity X for kind Y" — and
the model decides what is interesting. Before a candidate reaches the model
the harness folds the curated institution notes, the generic-name filter,
display names shared within the pool, names stating their own city or country
and the roster tiers into a per-anchor menu (the kinds still open, and for
nearest cards the roster institutions around it with distances), so the model
never does geography; every option id and decoy city must come from the roster
lists in the prompt. A proposal is a question shape only (kind, anchor,
option ids or decoy names, reveal sentence): every answer and constraint is
recomputed from the institutions' coordinates and places, re-issued through
`mcp_server.verify` as `get_entity_profile` facts and stored on the card as
`facts` (the model states no numbers, so the facts carry no `claimed`); a card
failing any check is dropped, never corrected. Reviewer rejections
(`status_note`) are quoted to the prompt as taste, the hand-edited
`HOUSE_STYLE` block steers it without code, and the run report lists every
candidate the harness held back and why. One immutable bundle holds every
kind; `(kind, semId)` is the skip key, an anchor carries one card per kind, a
name family one card per run, and the per-country cap applies per kind.

    uv run -m pyscripts rankless-game-card-mining --backend local --count 100
"""

import asyncio
import json
import re
import sqlite3
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
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
MIN_TIER1_OPTIONS = 2
NEAREST_MARGIN = 2.0
NEAREST_MAX_KM = 2000.0
# a nearest option sharing the anchor's coordinates is a same-city card in
# disguise and one dot on the reveal map
NEAREST_MIN_KM = 1.0
NEAREST_MENU = 12
EARTH_RADIUS_KM = 6371.0
BATCH_SIZE = 20
MAX_PROPOSALS = 10
TIMEOUT_S = 600
NOTE_LEN = (20, 300)
TASTE_LIMIT = 40
FACT_TOOL = "get_entity_profile"
FACT_PATHS = ("meta.lat", "meta.lon", "distinctText")

ISO2_PATH = Path("src/lib/assets/data/country-alpha-2-to-3.json")
ROSTER_PATH = Path("src/lib/assets/data/recognizable-institutions.json")
NOTES_PATH = Path("src/lib/assets/data/institution-notes.json")

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

# Words that carry no identity in an institution name: what is left is the
# name family (Duke University, Duke University Hospital and Duke Medical
# Center are one family).
_FAMILY_STOP = frozenset(
    """
    university universitat universite universidad universita universiteit
    college institute institut instituto institution school hospital hospitals
    medical medicine center centre centers centres clinic laboratory laboratories
    foundation academy research science sciences technology national state
    general health of the for and at in de la le les del di da du des der von
    """.split()
)

_TIER_REASONS = frozenset({"tier-1 fame", "not a tier-1 anchor", "not on the roster"})

# Hand-edited taste block, quoted to the model verbatim: what makes a card
# interesting and what makes it boring. Edit the text, not the code.
HOUSE_STYLE = """\
HOUSE STYLE

Interesting:
- a name that points at a specific wrong place: another country's city, region
  or river, a person or saint, a royal title that reads British, a namesake
  abroad
- a famous institution in a city players would not guess (CERN, EMBL, a Max
  Planck institute, a national lab, a university named after its region)
- a nearest card whose tempting option is famous and in the same country but
  far, while the true nearest sits just across a border
- an intruder whose name reads as the asked country better than the locals do
- a local card in a city with more than one famous institution, where every
  option is a name players know
- a reveal note that teaches one thing: where it really is and why the wrong
  answer tempted

Boring:
- hospitals, medical centres and clinics named after a place or an unknown
  person
- names that state their country, city or demonym; institutes named after a
  plain field ("Institute of Physics")
- options that are famous but obviously elsewhere, so the answer is the only
  plausible one
- an anchor whose only interest is being obscure: a player needs a reason to
  guess wrong, not no reason to guess at all
- a second card on the same theme in one batch (three Max Planck cards, three
  hospitals, three campuses of one system)
"""

_RULES = """\
You curate cards for CampusQuest, a geography speed quiz on Rankless, a
scholarly citation explorer: players see one prompt and four tappable options
and answer within seconds. Every card is one of five kinds, each asking one
fixed question:

- country-card — prompt: an institution; options: four countries. "Where is
  it actually?" Good anchors are lesser-known institutions whose names point
  at a SPECIFIC wrong place. Give exactly 3 decoy ISO 3166-1 alpha-2 codes,
  including the country the name evokes most; never the true country, never
  one the name contains.
- city-card — prompt: an institution; options: four cities. "Which city?"
  Best anchors are famous institutions with unobvious cities. Give 3 decoy
  cities from the CITIES list a player might guess, never the true one.
- nearest-card — prompt: a recognizable institution; options: four ROSTER
  institutions. "Which is closest?" Use the distances given with the
  candidate: one option must be at least twice as close as each of the other
  three, and rough geographic sense should be able to reason it out.
- intruder-card — prompt: a country; options: four institutions, three in
  that country and one elsewhere. "Which one is not here?" The anchor IS the
  intruder: an institution whose name reads as that country but sits
  elsewhere. Give three ROSTER institutions of one INTRUDER COUNTRY as options;
  their names should read as that country.
- local-card — prompt: a city; options: four institutions, one in that city
  and three elsewhere. "Which one is here?" The anchor IS the local one. Give
  three ROSTER institutions outside the anchor's city, none naming it.

The harness decides what is usable; you decide what is interesting. Each
candidate comes with the kinds still open to it — everything else is already
carded or excluded, so propose nothing outside that list — and, for nearest
cards, the nearest ROSTER institutions with their distance in km. Option ids
come only from the ROSTER; nearest, intruder and local cards need at least two
options of tier 1; decoy cities come only from CITIES. You never state an
answer, a country, a distance or a number: every answer is recomputed from
the data and a card failing any check is dropped.

Propose at most %(max)d cards per batch, the best ones only, one kind per
anchor and one card per name family (Duke University and Duke Medical Center
are one family). Every card gets a "note": one reveal sentence (shown after
answering) saying where it really is and why the wrong answer tempted.

Respond with ONLY a JSON object (no markdown fences):
{"cards": [{"kind": "...", "anchor": "<id>", "options": ["<id>", ...],
  "decoys": ["...", ...], "note": "..."}]}
`options` holds ids (nearest 4, intruder 3, local 3); `decoys` holds 3 ISO
codes (country-card) or 3 city names (city-card).
""" % {"max": MAX_PROPOSALS}


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
    """What a proposal is judged against: the ISO country set, the legal decoy
    cities by their folded form, country names by code, the roster tiers, the
    curated notes, and the pool members whose display name another shares."""

    iso2: frozenset[str]
    cities: dict[str, str]
    country_names: dict[str, str]
    tiers: dict[str, int] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)
    homonyms: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Menu:
    """What the harness lets the model propose for one anchor: the kinds still
    open, the kinds the anchor is unusable for and why, and the roster around
    it with distances for a nearest card."""

    open: tuple[str, ...]
    shut: dict[str, str]
    nearest: tuple[tuple[Place, int], ...] = ()


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


def family(name: str) -> str:
    """The name family an institution belongs to: its first identifying word."""
    rest = [t for t in _tokens(name) if t not in _FAMILY_STOP]
    return rest[0] if rest else _fold(name)


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


def unusable(anchor: Place, world: World) -> dict[str, str]:
    """The kinds `anchor` can never be a card of, with the reason — the
    deterministic half of the mining decision, applied before and after the
    model. A nearest card wants a placeable anchor, so a name stating its city
    shuts every other kind only; a tier-1 name is placeable by definition, so
    it never asks where it is."""
    if note := world.notes.get(anchor.sem_id):
        return dict.fromkeys(KINDS, f"noted: {note}")
    if is_generic_name(anchor.name):
        return dict.fromkeys(KINDS, "generic name")
    if anchor.sem_id in world.homonyms:
        return dict.fromkeys(KINDS, "display name shared within the pool")
    if not anchor.cc:
        return dict.fromkeys(KINDS, "no country")
    shut: dict[str, str] = {}
    if names(anchor.name, anchor.city):
        shut = {k: "names its own city" for k in KINDS if k != "nearest-card"}
    if names(anchor.name, world.country_names.get(anchor.cc)):
        shut.setdefault("country-card", "names its own country")
        shut.setdefault("intruder-card", "names its own country")
    if not anchor.city:
        shut.setdefault("city-card", "no city")
        shut.setdefault("local-card", "no city")
    tier = world.tiers.get(anchor.sem_id)
    if tier == 1:
        shut.setdefault("country-card", "tier-1 fame")
        shut.setdefault("intruder-card", "tier-1 fame")
    else:
        shut.setdefault("nearest-card", "not a tier-1 anchor")
    if tier is None:
        shut.setdefault("local-card", "not on the roster")
    return shut


def menu(
    anchor: Place,
    world: World,
    roster: list[Place],
    have: dict[str, dict[str, str]],
    caps: dict[str, object_mining.CcCap] | None = None,
    wanted: tuple[str, ...] = KINDS,
) -> Menu:
    """The anchor's menu against the located roster: a kind already carded,
    at its country cap or outside the round's `wanted` kinds is closed, a
    nearest card also needs a roster institution within the ceiling, and
    co-located roster entries are left off the distance list."""
    shut = unusable(anchor, world)
    nearest: tuple[tuple[Place, int], ...] = ()
    if "nearest-card" not in shut:
        around = sorted(
            (
                (o, km)
                for o in roster
                if o.sem_id != anchor.sem_id
                and _located(o)
                and _located(anchor)
                and (km := round(haversine_km(anchor, o))) >= NEAREST_MIN_KM
            ),
            key=lambda x: x[1],
        )[:NEAREST_MENU]
        if not around or around[0][1] > NEAREST_MAX_KM:
            shut["nearest-card"] = (
                f"no roster institution within {NEAREST_MAX_KM:.0f} km"
            )
        else:
            nearest = tuple(around)
    open_ = tuple(k for k in KINDS if k not in shut and anchor.sem_id not in have[k])
    return Menu(open_, shut, nearest)


def judge(
    kind: str, anchor: Place, options: list[Place], decoys: list[str], world: World
) -> tuple[dict | None, str]:
    """The kind-specific payload fragment a proposal earns from the data, or
    the reason it is dropped. Answers are never taken from the proposal."""
    if why := unusable(anchor, world).get(kind):
        return None, why
    if kind == "country-card":
        return _judge_country(anchor, decoys, world)
    if kind == "city-card":
        return _judge_city(anchor, decoys, world)
    if why := _options_reject(options, world):
        return None, why
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


def unusable_line(anchor: Place, shut: dict[str, str]) -> str:
    """One report line per held-back anchor; the roster-tier reasons are
    implied by the roster file and left out unless nothing else shuts it."""
    by_reason: dict[str, list[str]] = {}
    for kind, why in shut.items():
        by_reason.setdefault(why, []).append(kind.removesuffix("-card"))
    if len(shut) < len(KINDS):
        by_reason = {w: k for w, k in by_reason.items() if w not in _TIER_REASONS}
    if not by_reason:
        return ""
    parts = [
        f"{why} ({'all kinds' if len(kinds) == len(KINDS) else ', '.join(kinds)})"
        for why, kinds in by_reason.items()
    ]
    return f"- `{anchor.sem_id}` {anchor.name}: {'; '.join(parts)}"


def _options_reject(options: list[Place], world: World) -> str:
    if off := [o.sem_id for o in options if o.sem_id not in world.tiers]:
        return f"options off the roster {off}"
    if sum(world.tiers[o.sem_id] == 1 for o in options) < MIN_TIER1_OPTIONS:
        return f"fewer than {MIN_TIER1_OPTIONS} tier-1 options"
    return ""


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


def _judge_city(
    anchor: Place, decoys: list[str], world: World
) -> tuple[dict | None, str]:
    if not anchor.city:
        return None, "anchor has no city"
    folded = [_fold(d) for d in decoys]
    if len(decoys) != N_DECOYS or len(set(folded)) != N_DECOYS:
        return None, "need 3 distinct decoy cities"
    if _fold(anchor.city) in folded:
        return None, "the true city is among the decoys"
    if unknown := [d for d, f in zip(decoys, folded) if f not in world.cities]:
        return None, f"decoy cities off the list {unknown}"
    if named := [d for d in decoys if names(anchor.name, d)]:
        return None, f"decoy city named in the institution {named}"
    return {"city": anchor.city, "decoys": [world.cities[f] for f in folded]}, ""


def _judge_nearest(anchor: Place, options: list[Place]) -> tuple[dict | None, str]:
    if not all(map(_located, [anchor, *options])):
        return None, "an institution has no coordinates"
    ranked = sorted(haversine_km(anchor, o) for o in options)
    if ranked[0] < NEAREST_MIN_KM:
        return None, "the nearest shares the anchor's location"
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
    if names(anchor.name, world.country_names.get(anchor.cc)):
        return None, "the intruder names its own country"
    return {"country": country, "options": [_option(o) for o in options]}, ""


def _judge_local(anchor: Place, options: list[Place]) -> tuple[dict | None, str]:
    if not anchor.city:
        return None, "anchor has no city"
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
) -> object_mining.Generated:
    have = {kind: object_mining.stored_ccs(con, kind, ETYPE) for kind in KINDS}
    index, world = asyncio.run(_load_pool(skip, pool))
    log: list[str] = []
    calls: dict[str, object] = {}
    roster = asyncio.run(_locate([index[s] for s in world.tiers], calls, log))
    roster_by_id = {p.sem_id: p for p in roster}
    system = _system_prompt(world, roster, _taste(con))
    held: list[tuple[Place, dict[str, str]]] = []
    candidates: list[Place] = []
    for p in index.values():
        if shut := unusable(p, world):
            held.append((p, shut))
        if any(k not in shut and p.sem_id not in have[k] for k in KINDS):
            candidates.append(p)
    print(
        f"[{WORKFLOW}] {len(candidates)} candidate(s) with an open kind from slice "
        f"{skip}..{skip + pool}, {len(roster)} located on the roster, "
        f"{len(held)} held back for some kind; model={model}; "
        f"{sum(map(len, have.values()))} card(s) already stored"
    )
    caps = {k: object_mining.CcCap(have[k].values(), per_country) for k in KINDS}
    cost = {
        "batches": 0,
        "seconds": 0.0,
        "output_tokens": 0,
        "thinking_tokens": 0,
        "usd": 0.0,
    }
    objects: list[dict] = []
    families: set[str] = set()
    failures = 0
    reached = 0
    for start in range(0, len(candidates), BATCH_SIZE):
        if len(objects) >= count:
            break
        chunk = candidates[start : start + BATCH_SIZE]
        reached = list(index).index(chunk[-1].sem_id) + 1
        placed = asyncio.run(_locate(chunk, calls, log))
        menus = {p.sem_id: menu(p, world, roster, have) for p in placed}
        for p in placed:
            if p.sem_id in menus and not menus[p.sem_id].open:
                held.append((p, menus[p.sem_id].shut))
        menus = {s: m for s, m in menus.items() if m.open}
        if not menus:
            continue
        stats: dict = {}
        try:
            raw = cli.query_claude_cli(
                system,
                _user_prompt([p for p in placed if p.sem_id in menus], menus),
                model,
                timeout_s=TIMEOUT_S,
                stats=stats,
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
        if len(proposals) > MAX_PROPOSALS:
            object_mining.log_note(
                log, WORKFLOW, f"batch at {start}: {len(proposals)} proposals, capped"
            )
            proposals = proposals[:MAX_PROPOSALS]
        accepted = asyncio.run(
            _build_batch(
                proposals,
                menus,
                {p.sem_id: p for p in placed},
                roster_by_id,
                world,
                have,
                caps,
                families,
                count - len(objects),
                log,
                calls,
            )
        )
        objects += accepted
        cost["batches"] += 1
        for key in ("seconds", "output_tokens", "thinking_tokens", "usd"):
            cost[key] += stats.get(key, 0)
        object_mining.log_note(
            log,
            WORKFLOW,
            f"batch at {start}: {len(menus)} candidate(s), {len(proposals)} proposal(s), "
            f"{len(accepted)} accepted; {stats.get('seconds', 0):.0f} s, "
            f"{stats.get('output_tokens', 0):,} output tokens "
            f"({stats.get('thinking_tokens', 0):,} thinking), ${stats.get('usd', 0):.2f}",
        )
    if cost["batches"]:
        object_mining.log_note(log, WORKFLOW, object_mining.cost_line(cost))
    looked = set(list(index)[:reached])
    table = [
        line
        for p, shut in held
        if p.sem_id in looked and (line := unusable_line(p, shut))
    ]
    return object_mining.Generated(
        objects, len(candidates), log, cost=cost, sections={"Held back": table}
    )


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
    tiers = _roster(index)
    name_counts = Counter(_fold(p.name) for p in index.values())
    world = World(
        iso2=frozenset(iso2_to_3),
        cities={_fold(index[s].city): index[s].city for s in tiers if index[s].city},
        country_names={
            cc: c["name"] for c in countries if (cc := iso3_to_2.get(c["semanticId"]))
        },
        tiers=tiers,
        notes=json.loads(NOTES_PATH.read_text()) if NOTES_PATH.exists() else {},
        homonyms=frozenset(
            p.sem_id for p in index.values() if name_counts[_fold(p.name)] > 1
        ),
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


def _taste(con: sqlite3.Connection) -> list[str]:
    """Reviewer rejections of card kinds, one line per distinct reason with
    example cards, latest first."""
    marks = ", ".join("?" * len(KINDS))
    rows = con.execute(
        f"SELECT title, status_note FROM mcp_objects WHERE status = 'rejected'"
        f" AND status_note != '' AND kind IN ({marks})"
        f" ORDER BY updated_at DESC, id DESC",
        KINDS,
    ).fetchall()
    grouped: dict[str, list[str]] = {}
    for title, note in rows:
        grouped.setdefault(note, []).append(title)
    return [
        f"- {note} (e.g. {', '.join(titles[:3])})"
        for note, titles in list(grouped.items())[:TASTE_LIMIT]
    ]


def _system_prompt(world: World, roster: list[Place], taste: list[str]) -> str:
    by_cc: dict[str, list[Place]] = {}
    for p in roster:
        by_cc.setdefault(p.cc, []).append(p)
    roster_block = "\n".join(
        f"# {cc}\n"
        + "\n".join(
            f"{p.sem_id}\t{p.name}\t{p.city}\t{world.tiers[p.sem_id]}" for p in ps
        )
        for cc, ps in sorted(by_cc.items())
    )
    intruder_ccs = " ".join(
        sorted(cc for cc, ps in by_cc.items() if cc and _hosts_intruder(ps, world))
    )
    notes = "\n".join(f"- {sem}: {note}" for sem, note in world.notes.items())
    return "\n\n".join(
        [
            _RULES,
            HOUSE_STYLE,
            "ROSTER — the only legal option ids (id, name, city, tier), by country:\n"
            f"{roster_block}",
            "CITIES — the only legal decoy cities:\n"
            f"{', '.join(sorted(set(world.cities.values())))}",
            f"INTRUDER COUNTRIES — the countries an intruder card may ask about: {intruder_ccs}",
            f"INSTITUTION NOTES — curated, never anchors:\n{notes or '- none'}",
            f"REVIEWER TASTE — cards rejected in review and why:\n{chr(10).join(taste) or '- none yet'}",
        ]
    )


def _hosts_intruder(locals_: list[Place], world: World) -> bool:
    return (
        len(locals_) >= N_OPTIONS["intruder-card"]
        and sum(world.tiers[p.sem_id] == 1 for p in locals_) >= MIN_TIER1_OPTIONS
    )


def _user_prompt(chunk: list[Place], menus: dict[str, Menu]) -> str:
    def line(p: Place) -> str:
        m = menus[p.sem_id]
        near = "; ".join(f"{o.sem_id} {km}" for o, km in m.nearest) or "-"
        return " | ".join(
            [p.sem_id, p.name, p.city or "-", p.cc, ", ".join(m.open), near]
        )

    return (
        "CANDIDATES (id | name | city | country | kinds open to you | "
        "nearest roster institutions with km):\n"
        + "\n".join(line(p) for p in chunk)
        + f"\n\nPropose at most {MAX_PROPOSALS} cards and respond with the JSON only."
    )


async def _locate(
    places: list[Place], calls: dict[str, object], log: list[str]
) -> list[Place]:
    """The places rebuilt from their reproduced profile facts; one whose
    profile fails to reproduce is held back with a log line."""
    facts = [_fact(p, path) for p in places for path in FACT_PATHS]
    try:
        bad = await verify.verify_facts(facts, calls)
    finally:
        await be_client.aclose()
    failed = {f["args"]["semantic_id"] for f in bad}
    for sem in sorted(failed):
        object_mining.log_note(log, WORKFLOW, f"{sem}: profile not reproducible")
    return _placed(
        [p for p in places if p.sem_id not in failed],
        [f for f in facts if f["args"]["semantic_id"] not in failed],
    )


async def _build_batch(
    proposals: list[dict],
    menus: dict[str, Menu],
    anchors: dict[str, Place],
    roster_by_id: dict[str, Place],
    world: World,
    have: dict[str, dict[str, str]],
    caps: dict[str, object_mining.CcCap],
    families: set[str],
    room: int,
    log: list[str],
    calls: dict[str, object],
) -> list[dict]:
    objects: list[dict] = []
    try:
        for prop in proposals:
            if len(objects) >= room:
                break
            sem = str(prop.get("anchor", "?"))
            obj, why = await _build_card(
                prop, menus, anchors, roster_by_id, world, calls
            )
            if obj is None:
                object_mining.log_note(log, WORKFLOW, f"drop {sem}: {why}")
                continue
            kind, cc = obj["kind"], obj["payload"]["cc"]
            fam = family(obj["title"])
            if fam in families:
                object_mining.log_note(
                    log,
                    WORKFLOW,
                    f"drop {sem}: name family {fam!r} already carded this run",
                )
                continue
            if caps[kind].full(cc):
                object_mining.log_note(
                    log, WORKFLOW, f"drop {sem}: {kind} {cc} at per-country cap"
                )
                continue
            caps[kind].add(cc)
            have[kind][sem] = cc
            families.add(fam)
            objects.append(obj)
    finally:
        await be_client.aclose()
    return objects


async def _build_card(
    prop: dict,
    menus: dict[str, Menu],
    anchors: dict[str, Place],
    roster_by_id: dict[str, Place],
    world: World,
    calls: dict[str, object],
) -> tuple[dict | None, str]:
    kind = prop.get("kind")
    if kind not in KINDS:
        return None, f"unknown kind {kind!r}"
    sem = str(prop.get("anchor", ""))
    m = menus.get(sem)
    if m is None:
        return None, "anchor not in this batch"
    if kind not in m.open:
        return None, m.shut.get(kind, f"{kind} already carded")
    ids = [str(s) for s in prop.get("options") or []]
    n = N_OPTIONS.get(kind, 0)
    if len(ids) != n or len(set(ids)) != n or sem in ids:
        return None, f"need {n} distinct option ids"
    if off := [s for s in ids if s not in roster_by_id]:
        return None, f"options off the roster {off}"
    note = str(prop.get("note", "")).strip()
    if not NOTE_LEN[0] <= len(note) <= NOTE_LEN[1]:
        return None, f"note length {len(note)} outside {NOTE_LEN}"
    entities = [anchors[sem], *(roster_by_id[s] for s in ids)]
    facts = [_fact(e, path) for e in entities for path in FACT_PATHS]
    if bad := await verify.verify_facts(facts, calls):
        failed = [f"{f['args']['semantic_id']}:{f['path']}" for f in bad]
        return None, f"unreproducible facts {failed}"
    placed = _placed(entities, facts)
    decoys = [str(d).strip() for d in prop.get("decoys") or []]
    fragment, why = judge(kind, placed[0], placed[1:], decoys, world)
    if fragment is None:
        return None, why
    anchor = placed[0]
    return {
        "kind": kind,
        "obj_key": f"{ETYPE}|{anchor.sem_id}",
        "etype": ETYPE,
        "sem_id": anchor.sem_id,
        "title": anchor.name,
        "payload": {
            "semId": anchor.sem_id,
            "name": anchor.name,
            "cc": anchor.cc,
            "city": anchor.city,
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
