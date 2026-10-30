"""The email notice to authors on the site: one personal message per author, sent from
the outreach mailbox (`SENDER`) through Microsoft Graph.

    uv run -m pyscripts outreach render <batch.tsv> [--out DIR] [--backend live]
    uv run -m pyscripts outreach login
    uv run -m pyscripts outreach send <batch.tsv> [--dry-run] [--backend live] [--log FILE]

A batch is a TSV with the header `semantic_id, email, source`, `source` naming where
the address came from (a key of `SOURCE_SENTENCES`, the footer's account of it). The
file's stem names the batch: every link in its messages carries it as `?ref=<batch>`,
so the site's request log counts each batch's visits; the cards carry none, so a card is
one cache entry and an image fetch counts no open. The content comes from the backend
through `mcp_server`; the links point at the site's canonical host (`LIVE_DOMAIN`), so a
mail client follows no redirect.

`send` refuses a batch with a source whose footer sentence is still a `PLACEHOLDER`, and
takes the (author, address) pairs the send log (`SEND_LOG` in the kept root's
`outreach/`) does not hold, at most `DAILY_CAP` in any `DAY_HOURS`. It renders those
messages first and fetches every card they show (prewarming the site's card cache), and
stops before sending anything when one fails. It then claims each pair in the send log
before handing its message to Graph and releases it only when the message certainly did
not go out (Graph refused it or could not be reached), so a row is never sent twice, not
even after a crash or a timeout; it paces at `SENDS_PER_MINUTE`. `--dry-run` does all of
it but the refusal, the claim and the send.

Graph needs an app registration with the delegated `Mail.Send` permission:
`OUTREACH_CLIENT_ID` names it, `OUTREACH_TENANT` the tenant (default: the sender's
domain). `login` signs in as the sender with a device code once; the refresh token stays
in `TOKEN_PATH`, outside the repo and the synced roots, readable by its owner only.
"""

import asyncio
import base64
import csv
import html
import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from urllib.parse import urlencode

import httpx
from protocli import Dispatcher

import mcp_server
from mcp_server import card_url, resolve_backend
from mcp_server.cards import RENDER_TIMEOUT_S
from mcp_server.client import aclose
from mcp_server.response_shaping import plain
from mcp_server.tools import get_citation_tree, get_entity_profile, get_peers
from pyscripts import paths
from pyscripts.external_data import KEPT
from pyscripts.hosts import LIVE_DOMAIN
from wire.rankless_server.responses import TREE_SPECS

SENDER = "ccl@uni-corvinus.hu"
SENDER_DOMAIN = SENDER.split("@")[1]
CONTACT = "Veronika Hamar"
HEADLINE = "Where does your research have an impact?"
PLACEHOLDER = "[WORDING NEEDED]"
SOURCE_SENTENCES = {
    "corresponding": "using a corresponding-author email published in one of your recent publications.",
    "orcid": f"{PLACEHOLDER} using the email address public on your ORCID record.",
}

OUTREACH_DIR = "outreach"
SEND_LOG = "sent.sqlite"
PREVIEWS_DIR = "previews"
BATCH_FIELDS = ["semantic_id", "email", "source"]
AUTHORS = "authors"
SITE = f"https://{LIVE_DOMAIN}"
REF_PARAM = "ref"
# Countries, peers and co-authors each message names.
LISTED = 3
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
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass(frozen=True)
class Recipient:
    semantic_id: str
    email: str
    source: str


@dataclass(frozen=True)
class Content:
    """What one author's message shows; a card is None when the author lacks it."""

    name: str
    profile: str
    login: str
    tree_card: str
    countries: list[str]
    map_card: str | None
    peers: list[str]
    peers_card: str | None
    coauthors: list[str]
    network_card: str | None


@dataclass(frozen=True)
class Bold:
    text: str


@dataclass(frozen=True)
class Link:
    text: str
    href: str


Inline = str | Bold | Link


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


@dataclass(frozen=True)
class Items:
    items: list[str]


Block = Para | Heading | Button | Image | Items


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


def unworded_sources(rows: list[Recipient]) -> list[str]:
    return sorted({r.source for r in rows if PLACEHOLDER in SOURCE_SENTENCES[r.source]})


def emailed(url: str, batch: str | None = None) -> str:
    """`url` on the site's canonical host, carrying the batch as `ref` when given."""
    if not url.startswith(mcp_server.SITE_URL):
        raise ValueError(f"{url} is not on {mcp_server.SITE_URL}")
    url = SITE + url[len(mcp_server.SITE_URL) :]
    if batch is None:
        return url
    return f"{url}{'&' if '?' in url else '?'}{urlencode({REF_PARAM: batch})}"


async def content(semantic_id: str, batch: str) -> Content:
    profile, peer_res, tree = await asyncio.gather(
        get_entity_profile(AUTHORS, semantic_id),
        get_peers(AUTHORS, semantic_id),
        get_citation_tree(
            AUTHORS,
            semantic_id,
            tree_index=MAP_TREE,
            since_year=TREE_SPECS["yearBreaks"][0],
            top_n=LISTED + 1,
            depth=1,
        ),
    )
    countries = [row for row in tree["breakdown"] if row["nodeId"]][:LISTED]
    peers = [p for p in peer_res.get("peers", []) if "semanticId" in p][:LISTED]
    coauthors = [
        a for a in profile["relations"].get("paper-authors", []) if "semanticId" in a
    ][:LISTED]
    page = profile["rankless_url"]
    login = f"{mcp_server.SITE_URL}/login?{urlencode({'returnTo': page[len(mcp_server.SITE_URL) :]})}"

    def card(kind: str, query: dict) -> str:
        return emailed(card_url(kind, AUTHORS, semantic_id, query))

    hl = ",".join(str(row["nodeId"]) for row in countries)
    with_ids = ",".join(a["semanticId"] for a in coauthors)
    return Content(
        name=plain(profile["name"]),
        profile=emailed(page, batch),
        login=emailed(login, batch),
        tree_card=emailed(profile["image_url"]),
        countries=[row["name"] for row in countries],
        map_card=card("map", {"hl": hl}) if countries else None,
        peers=[plain(p["name"]) for p in peers],
        peers_card=emailed(peer_res["image_url"]) if peers else None,
        coauthors=[plain(a["name"]) for a in coauthors],
        network_card=card("network", {"with": with_ids})
        if "network" in profile["cards"]
        else None,
    )


def letter(c: Content, source: str) -> list[Block]:
    """One author's message as blocks, rendered by `to_text` and `to_html`."""
    first_name = CONTACT.split()[0]
    blocks: list[Block] = [
        Para((f"Dear {c.name},",)),
        Heading(HEADLINE),
        Para(
            (
                "Rankless profile explores the countries, institutions, and journals that cite your work.",
            )
        ),
        Button("Visit your profile", c.profile),
        Image(c.tree_card, f"Papers by {c.name}, by journal"),
        Para(
            (
                "Rankless is an open data visualization project developed by scholars like you.",
            )
        ),
        Para(
            (
                "It promotes a broader view of impact, by putting publication and citations in a rich geographic and topical context.",
            )
        ),
        Para(
            (
                "Rankless visualizations are built on OpenAlex, a public and open scholarly data set managed by a non-profit organization and built as a successor to Microsoft Academic Graph.",
            )
        ),
    ]
    if c.map_card:
        blocks += [
            Para(
                (
                    "According to these records, your work is cited primarily by scholars in",
                )
            ),
            Items(c.countries),
            Image(c.map_card, f"Countries citing papers by {c.name}"),
        ]
    if c.peers_card:
        blocks += [
            Para(
                ("Your academic peers (based on similarity of impact) are",),
            ),
            Items(c.peers),
            Image(c.peers_card, f"{c.name} compared with academic peers"),
        ]
    if c.network_card:
        blocks += [
            Para(
                ("And your co-authorship history includes several collaborations with",)
            ),
            Items(c.coauthors),
            Image(c.network_card, f"Co-authors of {c.name}"),
        ]
    return blocks + [
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
        Para(("The Rankless Team!",)),
        Para((Bold("Why you received this email:"),), small=True),
        Para(
            (
                "The Center for Collective Learning at Corvinus University of Budapest is contacting you about your scholarly profile "
                f"{SOURCE_SENTENCES[source]} To opt out of further outreach, or to have your profile removed from Rankless without logging in with you ORCID, please send an email to {first_name} at ",
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
        elif isinstance(b, Image):
            out.append(
                f'<p style="margin:0 0 18px"><img src="{html.escape(b.src)}" alt="{html.escape(b.alt)}" width="{IMAGE_W}" height="{IMAGE_H}"'
                ' style="display:block;max-width:100%;height:auto;border:1px solid #e4e4e4"></p>'
            )
        else:
            rows = "".join(
                f'<li style="margin:0 0 4px">{html.escape(i)}</li>' for i in b.items
            )
            out.append(f'<ul style="margin:0 0 14px;font-size:15px">{rows}</ul>')
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
        elif isinstance(b, Items):
            out.append("\n".join(f"- {i}" for i in b.items))
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
    return [u for u in (c.tree_card, c.map_card, c.peers_card, c.network_card) if u]


async def _contents(rows: list[Recipient], batch: str) -> list[Content]:
    gate = asyncio.Semaphore(FETCHES_IN_FLIGHT)

    async def one(r: Recipient) -> Content:
        async with gate:
            try:
                return await content(r.semantic_id, batch)
            except ValueError as exc:
                raise SystemExit(f"{r.semantic_id}: {exc}") from exc

    try:
        return await asyncio.gather(*(one(r) for r in rows))
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


def fetch_contents(rows: list[Recipient], batch: str, backend: str) -> list[Content]:
    mcp_server.set_backend(resolve_backend(backend)[0])
    return asyncio.run(_contents(rows, batch))


def render(batch: str, *, out: str = "", backend: str = "live") -> None:
    """Write each message of the batch as `<semantic id>.eml` and `.html` into --out
    (default: `previews/<batch>` in the kept root's outreach dir)."""
    rows, name = read_batch(Path(batch)), Path(batch).stem
    contents = fetch_contents(rows, name, backend)
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
        resp = _oauth_post(
            "token",
            {
                "grant_type": DEVICE_GRANT,
                "client_id": _client_id(),
                "device_code": grant["device_code"],
            },
        )
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
    if (unworded := unworded_sources(rows)) and not dry_run:
        raise SystemExit(
            f"the footer sentence of source(s) {', '.join(unworded)} is still {PLACEHOLDER}"
        )
    sendlog = SendLog(Path(log) if log else _outreach_dir() / SEND_LOG, dry_run)
    todo = [r for r in rows if not sendlog.has(r)]
    room = max(0, DAILY_CAP - sendlog.sent_within(DAY_HOURS))
    if len(todo) > room:
        print(f"{len(todo)} unsent, {room} left under the daily cap: sending {room}")
        todo = todo[:room]
    if not todo:
        print("nothing to send")
        return
    contents = fetch_contents(todo, name, backend)
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
