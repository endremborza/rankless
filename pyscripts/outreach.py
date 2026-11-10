"""The email notice to authors on the site: one personal message per author, sent from
the outreach mailbox (`SENDER`) through Microsoft Graph.

    uv run -m pyscripts outreach render <batch.tsv> [--out DIR] [--backend live]
    uv run -m pyscripts outreach login
    uv run -m pyscripts outreach send <batch.tsv> [--dry-run] [--backend live] [--log FILE]

A batch is a TSV with the header `semantic_id, email, source`, `source` naming where
the address came from (a key of `SOURCE_SENTENCES`, the footer's account of it). The
file's stem names the batch in the send log. The links carry no tag: the profile and
login links lead to the recipient's own profile, whose path identifies the visit. The
content comes from the backend through `mcp_server`; the links point at the site's
canonical host (`LIVE_DOMAIN`), so a mail client follows no redirect.

`send` takes the (author, address) pairs the send log (`SEND_LOG` in the kept root's
`outreach/`) does not hold, at most `DAILY_CAP` in any `DAY_HOURS`. It renders those
messages first and fetches every card they show (prewarming the site's card cache), and
stops before sending anything when one fails. It then claims each pair in the send log
before handing its message to Graph and releases it only when the message certainly did
not go out (Graph refused it or could not be reached), so a row is never sent twice, not
even after a crash or a timeout; it paces at `SENDS_PER_MINUTE`. `--dry-run` does all of
it but the claim and the send.

Graph needs an app registration with the delegated `Mail.Send` permission:
`OUTREACH_CLIENT_ID` names it, `OUTREACH_TENANT` the tenant (default: the sender's
domain). `login` signs in as the sender with a device code once; the refresh token stays
in `TOKEN_PATH`, outside the repo and the synced roots, readable by its owner only.
"""

import asyncio
import base64
import csv
import html
import itertools
import json
import os
import re
import sqlite3
import statistics
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from urllib.parse import urlencode

import httpx
from protocli import Dispatcher

import mcp_server
from mcp_server import card_url, encode_semantic_id, resolve_backend
from mcp_server.cards import RENDER_TIMEOUT_S
from mcp_server.client import aclose, get_json
from mcp_server.response_shaping import plain
from mcp_server.tools import (
    MAX_PAPERS_LIMIT,
    get_entity_profile,
    get_impact_dag,
    get_papers,
)
from pyscripts import paths
from pyscripts.external_data import KEPT
from pyscripts.hosts import LIVE_DOMAIN
from wire.rankless_rs.metrics import PAPER_SCORE, TOP_HIT_PAPERS
from wire.rankless_server.responses import (
    METHODOLOGY,
    TREE_SPECS,
    EntityPeersResp,
    LadderResp,
    PeerSubfieldInfo,
)
from wire.rankless_trees.io import TreeResponse

SENDER = "ccl@uni-corvinus.hu"
SENDER_DOMAIN = SENDER.split("@")[1]
CONTACT = "Veronika Hamar"
HEADLINE = "Where does your research have an impact?"
SOURCE_SENTENCES = {
    "corresponding": "using a corresponding-author email published in one of your recent publications.",
    "orcid": "using the email address you made public on your ORCID record.",
}

OUTREACH_DIR = "outreach"
SEND_LOG = "sent.sqlite"
PREVIEWS_DIR = "previews"
BATCH_FIELDS = ["semantic_id", "email", "source"]
AUTHORS = "authors"
SITE = f"https://{LIVE_DOMAIN}"
# Countries and fields a fact names at most.
LISTED = 3
# Facts a message shows at most: the first that hold, in `pick_facts` order.
FACTS = 3
# A field standing is a fact from this top share of the field's authors.
STANDING_MAX_SHARE = 0.1
# A country cites in excess from this specialization (its share of the author's citation
# links over its baseline, as the site's specialization view reads it) and
# `EXCESS_MIN_LINKS` links.
EXCESS_MIN = 3.0
EXCESS_MIN_LINKS = 30
# Momentum sets the last `MOMENTUM_YEARS` finished years against the as many before
# them, which need `MOMENTUM_MIN_CITES` citations.
MOMENTUM_YEARS = 5
MOMENTUM_MIN_CITES = 20
# The author's growth has to be this multiple of the peers' median growth.
MOMENTUM_MIN_LEAD = 1.25
ARTICLED_COUNTRIES = {
    "United States",
    "United Kingdom",
    "United Arab Emirates",
    "Netherlands",
    "Philippines",
    "Czech Republic",
    "Dominican Republic",
    "Central African Republic",
    "Democratic Republic of the Congo",
    "Bahamas",
    "Gambia",
    "Maldives",
}
FETCHES_IN_FLIGHT = 4
SENDS_PER_MINUTE = 20
DAILY_CAP = 1000
DAY_HOURS = 24

CLIENT_VAR = "OUTREACH_CLIENT_ID"
TENANT_VAR = "OUTREACH_TENANT"
TOKEN_PATH = (
    Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    / "rankless"
    / "outreach-graph-token.json"
)
TOKEN_MODE = 0o600
LOGIN_URL = "https://login.microsoftonline.com"
GRAPH_URL = "https://graph.microsoft.com/v1.0"
SCOPE = "openid profile offline_access https://graph.microsoft.com/Mail.Send"
DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
# RFC 8628: a `slow_down` answer adds this much to the polling interval.
SLOW_DOWN_S = 5
# An access token is refreshed this long before it expires.
TOKEN_MARGIN_S = 300

CARD_STYLE = paths.asset("card-style.json")
IMAGE_W = 560
IMAGE_H = round(IMAGE_W * CARD_STYLE["height"] / CARD_STYLE["width"])
# The breakdown the `map` card draws by default: the first with countries at level 1.
MAP_TREE = next(
    i
    for i, spec in enumerate(TREE_SPECS["specs"][AUTHORS])
    if spec["breakdowns"][0]["attributeType"] == "countries"
)
# The breakdown by citing field, the field a standing counts citations from.
CITING_FIELDS_TREE = next(
    i
    for i, spec in enumerate(TREE_SPECS["specs"][AUTHORS])
    if (b := spec["breakdowns"][0])["attributeType"] == "subfields"
    and not b["sourceSide"]
)
SINCE = TREE_SPECS["yearBreaks"][0]
LAST_FULL_YEAR = METHODOLOGY["workScreen"]["finalYear"] - 1
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True)
class Recipient:
    semantic_id: str
    email: str
    source: str


@dataclass(frozen=True)
class Bold:
    text: str


@dataclass(frozen=True)
class Link:
    text: str
    href: str


Inline = str | Bold | Link


@dataclass(frozen=True)
class Fact:
    """One finding about the author: its sentence and the card that shows it."""

    parts: tuple[Inline, ...]
    card: str
    alt: str


@dataclass(frozen=True)
class Content:
    name: str
    profile: str
    login: str
    facts: list[Fact]


@dataclass(frozen=True)
class Para:
    parts: tuple[Inline, ...]
    small: bool = False


@dataclass(frozen=True)
class Heading:
    text: str


@dataclass(frozen=True)
class Button:
    text: str
    href: str


@dataclass(frozen=True)
class Image:
    src: str
    alt: str


Block = Para | Heading | Button | Image


class NotSent(Exception):
    """The message did not go out: Graph refused it or could not be reached."""


class SendLog:
    """The (author, address) pairs ever claimed for a send; a dry run reads it only."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS sent (
        semantic_id TEXT NOT NULL,
        email TEXT NOT NULL,
        source TEXT NOT NULL,
        batch TEXT NOT NULL,
        sent_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY (semantic_id, email)
    );
    """

    def __init__(self, path: Path, dry_run: bool = False) -> None:
        if dry_run:
            uri = f"file:{path}?mode=ro" if path.exists() else ":memory:"
            self.con = sqlite3.connect(uri, uri=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.con = sqlite3.connect(path)
        if not dry_run or not path.exists():
            self.con.executescript(self.SCHEMA)

    def has(self, r: Recipient) -> bool:
        return bool(
            self.con.execute(
                "SELECT 1 FROM sent WHERE semantic_id = ? AND email = ?",
                (r.semantic_id, r.email),
            ).fetchone()
        )

    def claim(self, r: Recipient, batch: str) -> bool:
        with self.con:
            return (
                self.con.execute(
                    "INSERT OR IGNORE INTO sent (semantic_id, email, source, batch)"
                    " VALUES (?, ?, ?, ?)",
                    (r.semantic_id, r.email, r.source, batch),
                ).rowcount
                == 1
            )

    def release(self, r: Recipient) -> None:
        with self.con:
            self.con.execute(
                "DELETE FROM sent WHERE semantic_id = ? AND email = ?",
                (r.semantic_id, r.email),
            )

    def sent_within(self, hours: int) -> int:
        return self.con.execute(
            "SELECT COUNT(*) FROM sent WHERE sent_at > datetime('now', ?)",
            (f"-{hours} hours",),
        ).fetchone()[0]


class GraphToken:
    """A Graph access token for the signed-in sender, refreshed from `TOKEN_PATH`."""

    def __init__(self) -> None:
        self.access = ""
        self.expires = 0.0

    def bearer(self) -> str:
        if time.monotonic() > self.expires - TOKEN_MARGIN_S:
            body = _token_request(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": _stored_refresh_token(),
                    "scope": SCOPE,
                }
            )
            self.access = body["access_token"]
            self.expires = time.monotonic() + body["expires_in"]
        return self.access


def read_batch(path: Path) -> list[Recipient]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if reader.fieldnames != BATCH_FIELDS:
            raise SystemExit(f"{path}: the header must be {', '.join(BATCH_FIELDS)}")
        rows = [
            Recipient(r["semantic_id"].strip(), r["email"].strip().lower(), r["source"])
            for r in reader
        ]
    for r in rows:
        if not EMAIL_RE.match(r.email):
            raise SystemExit(f"{path}: {r.email!r} is not an address")
        if r.source not in SOURCE_SENTENCES:
            raise SystemExit(
                f"{path}: source {r.source!r} is none of {', '.join(SOURCE_SENTENCES)}"
            )
    if len({(r.semantic_id, r.email) for r in rows}) < len(rows):
        raise SystemExit(f"{path}: an (author, address) pair repeats")
    return rows


def emailed(url: str) -> str:
    """`url` on the site's canonical host."""
    if not url.startswith(mcp_server.SITE_URL):
        raise ValueError(f"{url} is not on {mcp_server.SITE_URL}")
    return SITE + url[len(mcp_server.SITE_URL) :]


async def content(semantic_id: str, ladder: LadderResp) -> Content:
    sid = encode_semantic_id(semantic_id)
    profile, peers, countries, papers, impact = await asyncio.gather(
        get_entity_profile(AUTHORS, semantic_id),
        get_json(f"/peers/{AUTHORS}/{sid}"),
        get_json(f"/trees/{AUTHORS}/{sid}", {"year": SINCE, "tid": MAP_TREE}),
        get_papers(AUTHORS, semantic_id, limit=MAX_PAPERS_LIMIT, sort="citations"),
        get_impact_dag(semantic_id),
    )
    name = plain(profile["name"])
    partners = [c["name"] for c in profile["relations"].get("collab-nation", [])]
    facts = pick_facts(
        Evidence(
            semantic_id,
            name,
            partners,
            papers["papers"],
            peers,
            ladder,
            countries,
            impact,
        )
    )
    if not facts:
        raise ValueError("no fact holds")
    page = profile["rankless_url"]
    login = f"{mcp_server.SITE_URL}/login?{urlencode({'returnTo': page[len(mcp_server.SITE_URL) :]})}"
    return Content(name, emailed(page), emailed(login), facts)


@dataclass(frozen=True)
class Evidence:
    """The backend's answers one author's facts are read from."""

    semantic_id: str
    name: str
    # The profile's partner nations: the countries the author publishes with.
    partners: list[str]
    papers: list[dict]
    peers: EntityPeersResp
    ladder: LadderResp
    countries: TreeResponse
    impact: dict

    def card(self, kind: str, query: dict) -> str:
        return emailed(card_url(kind, AUTHORS, self.semantic_id, query))


def pick_facts(e: Evidence) -> list[Fact]:
    found = (
        f(e)
        for f in (
            _hit_fact,
            _standing_fact,
            _excess_fact,
            _momentum_fact,
            _citing_hits_fact,
        )
    )
    return [f for f in found if f][:FACTS]


def _hit_fact(e: Evidence) -> Fact | None:
    hits = [p for p in e.papers if p.get("isHit")]
    if not hits:
        return None
    top = max(hits, key=lambda p: p["score"])
    return Fact(
        (
            "Your paper ",
            Bold(f"“{plain(top['name'])}”"),
            f" ({top['year']}) has {_times(top['score'] ** 2)} the citations it takes to reach the top {_share(PAPER_SCORE['topShare'])} of its field and year.",
        ),
        emailed(top["image_url"]),
        f"Hit papers by {e.name}",
    )


def _standing_fact(e: Evidence) -> Fact | None:
    """The tightest ladder band the author reaches in any citing field."""
    bands = e.ladder["pctBands"]
    reached: dict[float, list[PeerSubfieldInfo]] = {}
    hero = e.peers["hero"]
    for field, cites in zip(e.peers["topSubfields"], hero["subfieldCitations"]):
        row = e.ladder["ladder"][field["dmId"]]
        passed = [b for b, at in zip(bands, row) if at is not None and cites >= at]
        if passed:
            reached.setdefault(min(passed), []).append(field)
    if not reached or (share := min(reached)) > STANDING_MAX_SHARE:
        return None
    fields = reached[share][:LISTED]
    return Fact(
        (
            "You are in the ",
            Bold(f"top {_share(share)} most cited"),
            f" of all authors {_and([f'in {f["name"]}' for f in fields])}.",
        ),
        e.card(
            "fields",
            {
                "tree": CITING_FIELDS_TREE + 1,
                "since": SINCE,
                "isSpec": 0,
                "hl": ",".join(str(f["dmId"]) for f in fields),
            },
        ),
        f"Fields citing {e.name}",
    )


def _excess_fact(e: Evidence) -> Fact | None:
    """The countries citing the author most against their baseline, partner nations left out."""
    root = e.countries["tree"]
    labels = e.countries["atts"]["countries"]
    ranked = sorted(
        (
            (child["linkCount"] / root["linkCount"] / labels[nid]["specBaseline"], nid)
            for nid, child in root["children"].items()
            if int(nid)
            and child["linkCount"] >= EXCESS_MIN_LINKS
            and labels[nid]["name"] not in e.partners
        ),
        reverse=True,
    )
    top = [nid for spec, nid in ranked if spec >= EXCESS_MIN][:LISTED]
    if not top:
        return None
    lead = (
        f"Outside the countries you publish with ({_and([_country(c) for c in e.partners])}), the"
        if e.partners
        else "The"
    )
    return Fact(
        (
            f"{lead} countries that cite you most for their size are ",
            Bold(_and([_country(labels[nid]["name"]) for nid in top])),
            ".",
        ),
        e.card("map", {"since": SINCE, "isSpec": 1, "hl": ",".join(top)}),
        f"Countries citing {e.name}, by specialization",
    )


def _momentum_fact(e: Evidence) -> Fact | None:
    """The author's citation growth across the two windows, when it beats the peers' median
    by `MOMENTUM_MIN_LEAD`."""
    first_counted = METHODOLOGY["yearlyCounts"][0]
    end = LAST_FULL_YEAR - first_counted + 1
    windows = (end - 2 * MOMENTUM_YEARS, end - MOMENTUM_YEARS, end)

    def rate(yearly: list[int]) -> float | None:
        before, after = (sum(yearly[a:b]) for a, b in itertools.pairwise(windows))
        return after / before if before >= MOMENTUM_MIN_CITES else None

    own = rate(e.peers["hero"]["yearlyCites"])
    peers = [r for p in e.peers["peers"] if (r := rate(p["yearlyCites"])) is not None]
    if not (own and peers) or own < MOMENTUM_MIN_LEAD * (
        median := statistics.median(peers)
    ):
        return None
    first, mid, last = (first_counted + w for w in windows)
    return Fact(
        (
            f"From {first}–{mid - 1} to {mid}–{last - 1} your citations ",
            Bold(_change(own)),
            f", while those of your {len(peers)} closest peers on Rankless {_change(median)}.",
        ),
        e.card("yearly", {"from": first, "to": last - 1}),
        f"Citations of {e.name} by year",
    )


def _citing_hits_fact(e: Evidence) -> Fact | None:
    hits = e.impact["citingHits"]
    if not hits:
        return None
    n = len(hits)
    count = f"At least {n}" if n == TOP_HIT_PAPERS else str(n)
    top = hits[0]
    journal = f" in {top['journal']}" if top.get("journal") else ""
    return Fact(
        (
            Bold(f"{count} hit {'paper builds' if n == 1 else 'papers build'}"),
            f" on your work: papers with at least {PAPER_SCORE['hitMultiple']:g} times the citations it takes to reach the top {_share(PAPER_SCORE['topShare'])} of their field and year. The strongest is “{plain(top['name'])}”{journal} ({top['year']}).",
        ),
        emailed(e.impact["image_url"]),
        f"Hit papers citing {e.name}",
    )


def _share(share: float) -> str:
    """A ladder or paper-score share as the site's standing badges word it."""
    return f"{share * 100:g}%"


def _times(ratio: float) -> str:
    return f"{ratio:.0f} times" if ratio >= 10 else f"{ratio:.1f} times"


def _change(ratio: float) -> str:
    if ratio >= 2:
        return f"grew {ratio:.1f}-fold"
    if ratio >= 1:
        return f"grew {round((ratio - 1) * 100)}%"
    return f"fell {round((1 - ratio) * 100)}%"


def _country(name: str) -> str:
    return f"the {name}" if name in ARTICLED_COUNTRIES else name


def _and(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def letter(c: Content, source: str) -> list[Block]:
    """One author's message as blocks, rendered by `to_text` and `to_html`."""
    first_name = CONTACT.split()[0]
    blocks: list[Block] = [
        Para((f"Dear {c.name},",)),
        Heading(HEADLINE),
        Para(
            (
                "Rankless maps who cites your work: from which countries, fields and journals, across every paper in OpenAlex. This is what stands out in yours.",
            )
        ),
    ]
    for f in c.facts:
        blocks += [Para(f.parts), Image(f.card, f.alt)]
    return blocks + [
        Button("Visit your profile", c.profile),
        Para(
            (
                "Rankless is an open data visualization project developed by scholars like you, built on OpenAlex, a public and open scholarly data set managed by a non-profit organization.",
            )
        ),
        Para(
            (
                "If you want to manage your Rankless profile, ",
                Link("log in with your ORCID.", c.login),
            )
        ),
        Para(
            (
                "Our goal at Rankless is to present a multidimensional view of impact, where every scholar, every country, and every university isn't flattened by a rank.",
            )
        ),
        Para(
            (
                "If you have any questions or comments about the project, the methods, or the visualizations, please don't hesitate to contact "
                f"{CONTACT} at ",
                Link(SENDER, f"mailto:{SENDER}"),
                ".",
            )
        ),
        Para(("Best regards,",)),
        Para(("The Rankless Team",)),
        Para((Bold("Why you received this email:"),), small=True),
        Para(
            (
                "The Center for Collective Learning at Corvinus University of Budapest is contacting you about your scholarly profile "
                f"{SOURCE_SENTENCES[source]} There will be no follow-up to this email unless you opt in on the Rankless site or specifically request it. To have your profile removed from Rankless without logging in with your ORCID, please send an email to {first_name} at ",
                Link(SENDER, f"mailto:{SENDER}"),
                ".",
            ),
            small=True,
        ),
    ]


def _inline_html(part: Inline) -> str:
    if isinstance(part, Bold):
        return f"<strong>{html.escape(part.text)}</strong>"
    if isinstance(part, Link):
        return f'<a href="{html.escape(part.href)}" style="color:{CARD_STYLE["accent"]}"><strong>{html.escape(part.text)}</strong></a>'
    return html.escape(part)


def _inline_text(part: Inline) -> str:
    if isinstance(part, Bold):
        return part.text
    if isinstance(part, Link):
        return (
            part.text
            if part.href == f"mailto:{part.text}"
            else f"{part.text} <{part.href}>"
        )
    return part


def to_html(blocks: list[Block]) -> str:
    out = []
    for b in blocks:
        if isinstance(b, Para):
            style = "font-size:12px;color:#666" if b.small else "font-size:15px"
            out.append(
                f'<p style="margin:0 0 14px;{style}">{"".join(map(_inline_html, b.parts))}</p>'
            )
        elif isinstance(b, Heading):
            out.append(
                f'<h1 style="margin:0 0 14px;font-size:22px">{html.escape(b.text)}</h1>'
            )
        elif isinstance(b, Button):
            out.append(
                f'<p style="margin:18px 0"><a href="{html.escape(b.href)}" style="background:{CARD_STYLE["accent"]};color:#fff;'
                f'padding:12px 22px;border-radius:4px;text-decoration:none;font-weight:bold;display:inline-block">{html.escape(b.text)}</a></p>'
            )
        else:
            out.append(
                f'<p style="margin:0 0 18px"><img src="{html.escape(b.src)}" alt="{html.escape(b.alt)}" width="{IMAGE_W}" height="{IMAGE_H}"'
                ' style="display:block;max-width:100%;height:auto;border:1px solid #e4e4e4"></p>'
            )
    body = "\n".join(out)
    return (
        f'<!doctype html>\n<html><head><meta charset="utf-8"><title>{html.escape(HEADLINE)}</title></head>\n'
        '<body style="margin:0;padding:0;background:#fff">\n'
        '<div style="max-width:600px;margin:0 auto;padding:24px 20px;font-family:Arial,Helvetica,sans-serif;color:#222;line-height:1.45">\n'
        f"{body}\n</div>\n</body></html>\n"
    )


def to_text(blocks: list[Block]) -> str:
    out = []
    for b in blocks:
        if isinstance(b, Para):
            out.append("".join(map(_inline_text, b.parts)))
        elif isinstance(b, Heading):
            out.append(b.text)
        elif isinstance(b, Button):
            out.append(f"{b.text}: {b.href}")
    return "\n\n".join(out) + "\n"


def message(c: Content, r: Recipient) -> EmailMessage:
    blocks = letter(c, r.source)
    msg = EmailMessage(policy=SMTP)
    msg["From"] = SENDER
    msg["To"] = r.email
    msg["Subject"] = HEADLINE
    msg.set_content(to_text(blocks))
    msg.add_alternative(to_html(blocks), subtype="html")
    return msg


def cards(c: Content) -> list[str]:
    return [f.card for f in c.facts]


async def _contents(rows: list[Recipient]) -> list[Content]:
    gate = asyncio.Semaphore(FETCHES_IN_FLIGHT)

    async def one(r: Recipient, ladder: LadderResp) -> Content:
        async with gate:
            try:
                return await content(r.semantic_id, ladder)
            except ValueError as exc:
                raise SystemExit(f"{r.semantic_id}: {exc}") from exc

    try:
        ladder = await get_json(f"/ladder/{AUTHORS}")
        return await asyncio.gather(*(one(r, ladder) for r in rows))
    finally:
        await aclose()


async def _broken_cards(urls: list[str]) -> list[str]:
    """The card URLs that do not render as a PNG, each fetched once."""
    gate = asyncio.Semaphore(FETCHES_IN_FLIGHT)
    async with httpx.AsyncClient(timeout=RENDER_TIMEOUT_S) as client:

        async def bad(url: str) -> bool:
            async with gate:
                resp = await client.get(url)
            return (
                resp.status_code != 200
                or resp.headers.get("content-type", "").split(";")[0] != "image/png"
            )

        verdicts = await asyncio.gather(*(bad(u) for u in urls))
    return [u for u, b in zip(urls, verdicts) if b]


def fetch_contents(rows: list[Recipient], backend: str) -> list[Content]:
    mcp_server.set_backend(resolve_backend(backend)[0])
    return asyncio.run(_contents(rows))


def render(batch: str, *, out: str = "", backend: str = "live") -> None:
    """Write each message of the batch as `<semantic id>.eml` and `.html` into --out
    (default: `previews/<batch>` in the kept root's outreach dir)."""
    rows, name = read_batch(Path(batch)), Path(batch).stem
    contents = fetch_contents(rows, backend)
    out_dir = Path(out) if out else _outreach_dir() / PREVIEWS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    for r, c in zip(rows, contents):
        msg, base = message(c, r), r.semantic_id.replace("/", "-")
        (out_dir / f"{base}.eml").write_bytes(msg.as_bytes())
        (out_dir / f"{base}.html").write_text(msg.get_body(("html",)).get_content())
    print(f"{len(rows)} message(s) -> {out_dir}")


def login() -> None:
    """Sign in as the sender with a device code (${client}: the Graph app's client id;
    ${tenant}: the tenant, default {domain}); keeps the refresh token in {token}."""
    code = _oauth_post("devicecode", {"client_id": _client_id(), "scope": SCOPE})
    code.raise_for_status()
    grant = code.json()
    print(grant["message"])
    interval, deadline = grant["interval"], time.monotonic() + grant["expires_in"]
    while time.monotonic() < deadline:
        time.sleep(interval)
        try:
            resp = _oauth_post(
                "token",
                {
                    "grant_type": DEVICE_GRANT,
                    "client_id": _client_id(),
                    "device_code": grant["device_code"],
                },
            )
        except httpx.ConnectError:
            continue
        body = resp.json()
        if resp.is_success:
            who = _id_token_user(body["id_token"])
            if who.lower() != SENDER:
                raise SystemExit(f"signed in as {who}, not {SENDER}: nothing kept")
            _store_refresh_token(body["refresh_token"])
            print(f"signed in as {who}; refresh token in {TOKEN_PATH}")
            return
        if body.get("error") == "authorization_pending":
            continue
        if body.get("error") == "slow_down":
            interval += SLOW_DOWN_S
            continue
        raise SystemExit(
            f"login failed: {body.get('error')}: {body.get('error_description')}"
        )
    raise SystemExit("the device code expired before sign-in")


login.__doc__ = (login.__doc__ or "").format(
    client=CLIENT_VAR, tenant=TENANT_VAR, domain=SENDER_DOMAIN, token=TOKEN_PATH
)


def send(
    batch: str, *, dry_run: bool = False, backend: str = "live", log: str = ""
) -> None:
    """Send the batch's messages not sent before, at most DAILY_CAP a day, paced."""
    rows, name = read_batch(Path(batch)), Path(batch).stem
    sendlog = SendLog(Path(log) if log else _outreach_dir() / SEND_LOG, dry_run)
    todo = [r for r in rows if not sendlog.has(r)]
    room = max(0, DAILY_CAP - sendlog.sent_within(DAY_HOURS))
    if len(todo) > room:
        print(f"{len(todo)} unsent, {room} left under the daily cap: sending {room}")
        todo = todo[:room]
    if not todo:
        print("nothing to send")
        return
    contents = fetch_contents(todo, backend)
    if broken := asyncio.run(_broken_cards([u for c in contents for u in cards(c)])):
        raise SystemExit(
            "cards that do not render, nothing sent:\n" + "\n".join(broken)
        )
    token = None if dry_run else GraphToken()
    for i, (r, c) in enumerate(zip(todo, contents)):
        msg = message(c, r)
        if token is None:
            print(f"would send {r.email} ({r.semantic_id}, {r.source})")
            continue
        bearer = token.bearer()
        if not sendlog.claim(r, name):
            continue
        try:
            _graph_send(bearer, msg)
        except NotSent as exc:
            sendlog.release(r)
            raise SystemExit(str(exc)) from exc
        print(f"sent {r.email} ({r.semantic_id}, {r.source})")
        if i + 1 < len(todo):
            time.sleep(60 / SENDS_PER_MINUTE)


def _graph_send(bearer: str, msg: EmailMessage) -> None:
    """Graph's MIME send: the message goes out as rendered, from the signed-in mailbox."""
    try:
        resp = httpx.post(
            f"{GRAPH_URL}/me/sendMail",
            content=base64.b64encode(msg.as_bytes()),
            headers={"Authorization": f"Bearer {bearer}", "Content-Type": "text/plain"},
            timeout=60,
        )
    except httpx.ConnectError as exc:
        raise NotSent(f"Graph unreachable for {msg['To']}: {exc!r}") from exc
    if resp.status_code != 202:
        raise NotSent(
            f"Graph refused {msg['To']}: {resp.status_code} {resp.text[:500]}"
        )


def _outreach_dir() -> Path:
    return KEPT.path() / OUTREACH_DIR


def _client_id() -> str:
    client = os.environ.get(CLIENT_VAR)
    if not client:
        raise SystemExit(
            f"${CLIENT_VAR} is unset: the Graph app registration's client id"
        )
    return client


def _oauth_post(endpoint: str, data: dict[str, str]) -> httpx.Response:
    tenant = os.environ.get(TENANT_VAR) or SENDER_DOMAIN
    return httpx.post(
        f"{LOGIN_URL}/{tenant}/oauth2/v2.0/{endpoint}", data=data, timeout=30
    )


def _token_request(data: dict[str, str]) -> dict:
    resp = _oauth_post("token", {**data, "client_id": _client_id()})
    body = resp.json()
    if not resp.is_success:
        raise SystemExit(
            f"token refresh failed ({body.get('error')}): run `outreach login` again"
        )
    if "refresh_token" in body:
        _store_refresh_token(body["refresh_token"])
    return body


def _id_token_user(id_token: str) -> str:
    payload = id_token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    return claims["preferred_username"]


def _store_refresh_token(token: str) -> None:
    TOKEN_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, TOKEN_MODE)
    os.fchmod(fd, TOKEN_MODE)
    with os.fdopen(fd, "w") as f:
        json.dump({"refresh_token": token}, f)


def _stored_refresh_token() -> str:
    if not TOKEN_PATH.exists():
        raise SystemExit(f"no sign-in kept in {TOKEN_PATH}: run `outreach login`")
    return json.loads(TOKEN_PATH.read_text())["refresh_token"]


_dispatcher = Dispatcher(
    "pyscripts outreach", {"render": render, "login": login, "send": send}
)
