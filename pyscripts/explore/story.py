"""A run's story: one markdown article written from its reproduced findings.

`deep --story [OCCASION]` ends a run with it. The model (no tools) gets the run's fully
reproduced findings and nothing else, and writes a title and an article with the findings'
cards inline. The run dir gets `story.md`: front matter naming the run, the occasion and
the data the numbers were read from (`data_version`, the backend's `/v1/specs` version),
then the article. Every card it shows is fetched into `cards/` (through
`RANKLESS_RENDER_URL` when the cards render elsewhere than the site), so the story and its
pictures stay what they were on that data; the first of them is the `image` a link to the
story previews. A number in the text that no reproduced value accounts for is listed in
the front matter as `unverified`; numbers in the occasion (the prize year) count as given.
"""

import asyncio
import hashlib
import json
import math
import re
from datetime import date
from pathlib import Path

import httpx

from mcp_server import MAIN_DOMAIN
from mcp_server.cards import CardError, fetch_card
from pyscripts.explore import cli
from wire.rankless_rs.metrics import PAPER_SCORE

STORY_FILE = "story.md"

_TOP_SHARE = f"{PAPER_SCORE['topShare'] * 100:g}%"
SYSTEM = f"""\
You write a story for Rankless ({MAIN_DOMAIN}), a scholarly citation explorer, from findings
whose numbers were verified against its data. The story must read as Rankless: it shows
what only Rankless shows (who a body of work reaches, by field and country; papers scored
against the top-{_TOP_SHARE} bar of their own field and year; the most-cited papers that build on
someone's work) and links to the Rankless pages that show it.

Rules:
- Use only the facts and numbers in the findings below. Never add a number, a year, a
  rank or a ratio that is not there, and never compute one. Write a number as given, or
  rounded with its unit (6,897 or 6.9k); nothing else.
- Link the Rankless pages each claim rests on, inline.
- Show cards only from the findings' `images`, as markdown images where the text reaches
  what they show.
- A finding about a gap or error in Rankless's own data (a split profile, a missing
  paper) is for the team, not the public: leave it out.
- Lead with what is specific to this subject and hard to see elsewhere: a paper's score
  against its field's bar, the hit papers and laureates that build on the work, the
  fields and countries it reaches. Totals alone are not a story.
- Plain, curious, precise. No hype words.

Write a title and a markdown article of 500-800 words (without the title) in sections.

Respond with ONLY a JSON object (no markdown fences):
{{"title": "...", "markdown": "..."}}"""

# A link's target may hold one bracket pair (a DOI such as 10.1016/0370-1573(95)00058-5).
_TARGET = r"\((?:[^()]|\([^()]*\))*\)"
# What is not prose: a bare URL, an image with its alt text, a link's target.
_URL = re.compile(rf"https?://\S+|!\[[^\]]*\]{_TARGET}|\]{_TARGET}")
_CARD = re.compile(r"https?://[^\s\"<>]+/card/[^\s\"<>]+")
# A digit after a letter and a hyphen is part of a name (CTLA-4, IL-2), not a number.
_NUM = re.compile(
    r"(?<![\w.])(?<![A-Za-z]-)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*"
    r"(%|k\b|K\b|M\b|million\b|thousand\b|billion\b)?"
)
_QUERY_NUM = re.compile(r"[?&]\w+=(\d+)")
_LIST_MARK = re.compile(r"^\s*\d+[.)]\s", re.MULTILINE)
_SCALE = {"k": 1e3, "K": 1e3, "thousand": 1e3, "M": 1e6, "million": 1e6, "billion": 1e9}


def write(
    run_dir: Path, findings: list[dict], occasion: str, model: str, data_version: str
) -> Path | None:
    """The story of the run's fully reproduced findings, read from `data_version`; None
    when there is nothing to write from or the reply does not parse."""
    brief = [_brief(f) for f in findings if f.get("_verified")]
    if not brief:
        print("[story] no fully reproduced findings to write from")
        return None
    stats: dict = {}
    raw = cli.query_claude_cli(SYSTEM, _user(brief, occasion), model, stats=stats)
    try:
        reply = cli.parse_json(raw)
        title, markdown = reply["title"], reply["markdown"]
    except (ValueError, KeyError) as exc:
        (run_dir / "story-response.txt").write_text(raw)
        print(f"[story] could not parse the reply ({exc}); raw saved to {run_dir}")
        return None
    known = [n["value"] for f in brief for n in f["numbers"]] + _numbers(occasion)
    # A view's own parameters (a `since` year) are given by the page it links to.
    known += [
        float(n) for f in brief for u in f["pages"] for n in _QUERY_NUM.findall(u)
    ]
    cards = asyncio.run(_bundle(run_dir, card_urls(markdown)))
    meta = {
        "title": title,
        "date": date.today(),
        "occasion": occasion,
        "run": run_dir.name,
        "data_version": data_version,
        "image": next(iter(cards.values()), None),
        "unverified": unverified(f"{title}\n{markdown}", known),
    }
    path = run_dir / STORY_FILE
    path.write_text(render(meta, _localize(markdown, cards)))
    print(
        f"[story] {stats.get('seconds', 0):.0f}s; {len(meta['unverified'])} unverified "
        f"number(s); {len(cards)} card(s) bundled"
    )
    return path


def render(meta: dict, markdown: str) -> str:
    """The story file: YAML front matter (a JSON value is a YAML value; empty ones are
    left out), then the article."""
    front = "".join(
        f"{key}: {v.isoformat() if isinstance(v, date) else json.dumps(v, ensure_ascii=False)}\n"
        for key, v in meta.items()
        if v
    )
    return f"---\n{front}---\n\n{markdown.strip()}\n"


def _brief(finding: dict) -> dict:
    return {
        "title": finding.get("title"),
        "story": finding.get("description"),
        "numbers": [
            {"label": m.get("label") or m["key"], "value": m["reproduced"]}
            for m in finding.get("metrics", [])
            if m.get("ok") and isinstance(m.get("reproduced"), (int, float))
        ],
        "pages": finding.get("entities", []),
        "images": finding.get("images", []),
    }


def _user(brief: list[dict], occasion: str) -> str:
    head = f"Occasion: {occasion}\n\n" if occasion else ""
    return head + "Findings:\n" + json.dumps(brief, indent=2, ensure_ascii=False)


def _numbers(text: str) -> list[float]:
    return [value for _, readings in _parse_numbers(text) for value, _ in readings]


def _parse_numbers(text: str) -> list[tuple[str, list[tuple[float, float]]]]:
    """Each number in prose as written, with its readings as (value, half its last shown
    unit); a percentage reads both as written and as a share."""
    out = []
    for m in _NUM.finditer(_LIST_MARK.sub(" ", _URL.sub(" ", text))):
        whole, frac, unit = m.group(1), m.group(2) or "", m.group(3)
        scale = _SCALE.get(unit or "", 1.0)
        value = float(whole.replace(",", "") + frac) * scale
        half = 0.5 * 10 ** -(len(frac) - 1 if frac else 0) * scale
        readings = [(value, half)]
        if unit == "%":
            readings.append((value / 100, half / 100))
        out.append((m.group(0).strip(), readings))
    return out


def unverified(text: str, known: list[float]) -> list[str]:
    """Numbers in `text` that no known value accounts for, within the rounding they are
    written with."""
    return [
        written
        for written, readings in _parse_numbers(text)
        if not any(
            math.isclose(value, k, abs_tol=half)
            for value, half in readings
            for k in known
        )
    ]


def card_urls(markdown: str) -> list[str]:
    """Every card the article shows, in order."""
    return list(dict.fromkeys(_card_in(m.group(0)) for m in _CARD.finditer(markdown)))


def _card_in(matched: str) -> str:
    """The card URL in a `_CARD` match: prose punctuation after it and the bracket of a
    markdown link around it are not part of it, a bracket pair inside its path is."""
    url = matched.rstrip(".,;:!?'")
    while url.endswith(")") and url.count(")") > url.count("("):
        url = url[:-1].rstrip(".,;:!?'")
    return url


async def _bundle(run_dir: Path, urls: list[str]) -> dict[str, str]:
    """The cards fetched into `<run>/cards/`, as url -> path relative to the run; a card
    that fails to render is reported and left as its URL."""
    out: dict[str, str] = {}
    for url in urls:
        rel = f"cards/{_card_name(url)}"
        dest = run_dir / rel
        if not dest.exists():
            try:
                png = await fetch_card(url)
            except (CardError, httpx.HTTPError) as exc:
                print(f"[story] card failed: {url}: {exc}")
                continue
            dest.parent.mkdir(exist_ok=True)
            dest.write_bytes(png)
        out[url] = rel
    return out


def _card_name(url: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", url.split("/card/", 1)[-1].lower()).strip("-")
    return f"{stem[:60]}-{hashlib.sha1(url.encode()).hexdigest()[:6]}.png"


def _localize(text: str, cards: dict[str, str]) -> str:
    def local(m: re.Match[str]) -> str:
        url = _card_in(m.group(0))
        return cards.get(url, url) + m.group(0)[len(url) :]

    return _CARD.sub(local, text)
