"""Social posts written from a verified deep run.

    uv run -m pyscripts.explore.posts <run-dir> [--context "2025 Nobel Prize in ..."]

The run's reproduced findings are the only material: the model (no tools) writes an X
thread, LinkedIn, Facebook and Reddit posts and an article draft from them, and every
number in the result that no reproduced value accounts for is listed for the reviewer.
Numbers in `--context` (the occasion, e.g. the prize year) count as given. The run dir
becomes the publishable unit: `posts.json` (the reply and the checks), every card a post
uses fetched into `cards/` (through `RANKLESS_RENDER_URL` when the cards render
elsewhere than the site), and `posts.md` plus `article.md` referencing them relatively.
"""

import argparse
import asyncio
import hashlib
import json
import math
import re
from pathlib import Path

import httpx

from mcp_server.cards import CardError, fetch_card
from pyscripts.explore import cli

X_LIMIT = 280
X_URL_WEIGHT = 23

SYSTEM = """\
You write social posts for Rankless (rankless.org), a scholarly citation explorer, from
findings whose numbers were verified against its data. The posts must read as Rankless:
they show what only Rankless shows (who a body of work reaches, by field and country;
papers scored against the top-1% bar of their own field and year; the most-cited papers
that build on someone's work) and link to the Rankless pages that show it.

Rules:
- Use only the facts and numbers in the findings below. Never add a number, a year, a
  rank or a ratio that is not there, and never compute one. Write a number as given, or
  rounded with its unit (6,897 or 6.9k); nothing else.
- Every post links to at least one Rankless page from the findings; the thread and the
  HTML post link the pages each claim rests on.
- Attach cards only from the findings' `images`. Up to 4 per X post, 1-3 elsewhere.
- A finding about a gap or error in Rankless's own data (a split profile, a missing
  paper) is for the team, not the public: leave it out of every post.
- Lead with what is specific to this person and hard to see elsewhere: a paper's score
  against its field's bar, the hit papers and laureates that build on the work, the
  fields and countries it reaches. Totals alone are not a story.
- Plain, curious, precise. No hype words, no emoji walls, at most two hashtags per post.

Formats:
- x_thread: 4-7 posts, each at most 280 characters with every URL counted as 23. The
  first post is the hook and carries the best card.
- linkedin: one post, at most 1,300 characters, for researchers and research managers.
- facebook: one post, at most 600 characters, for a general audience.
- reddit: a title (at most 300 characters) and a markdown body for a science subreddit:
  factual, sourced, no marketing tone, the Rankless links as sources.
- html_post: a title and a markdown article of 500-800 words (without the title) with
  sections, the cards as images and the Rankless links inline; the other posts can
  link to it.

Respond with ONLY a JSON object (no markdown fences):
{"x_thread": [{"text": "...", "images": ["<image_url>"]}],
 "linkedin": {"text": "...", "images": []},
 "facebook": {"text": "...", "images": []},
 "reddit": {"title": "...", "body": "...", "images": []},
 "html_post": {"title": "...", "markdown": "..."}}"""

_URL = re.compile(r"https?://\S+|!\[[^\]]*\]\([^)]*\)|\]\([^)]*\)")
_CARD = re.compile(r"https?://[^\s\"<>]+/card/[^\s\"<>]+")
_THREAD_MARK = re.compile(r"\b\d+\s*/\s*\d+\b|^\s*\d+[.)]\s", re.MULTILINE)
_NUM = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*"
    r"(%|k\b|K\b|M\b|million\b|thousand\b|billion\b)?"
)
_QUERY_NUM = re.compile(r"[?&]\w+=(\d+)")
_SCALE = {"k": 1e3, "K": 1e3, "thousand": 1e3, "M": 1e6, "million": 1e6, "billion": 1e9}


def main() -> int:
    p = argparse.ArgumentParser(description="Social posts from a verified deep run.")
    p.add_argument("run_dir", type=Path)
    p.add_argument("--context", default="", help="the occasion, e.g. the prize won.")
    p.add_argument("--model", default=cli.DEFAULT_MODEL)
    args = p.parse_args()

    findings = json.loads((args.run_dir / "findings.json").read_text())["findings"]
    brief = [_brief(f) for f in findings if f.get("_verified")]
    if not brief:
        raise SystemExit("no fully reproduced findings to write from")
    stats: dict = {}
    raw = cli.query_claude_cli(
        SYSTEM,
        _user(brief, args.context),
        cli.resolve_model(args.model),
        stats=stats,
    )
    path = args.run_dir / "posts.json"
    # The paid reply is kept as sent until it parses into every format.
    path.write_text(
        json.dumps({"context": args.context, "stats": stats, "raw": raw}, indent=2)
    )
    posts = cli.parse_json(raw)
    known = [n["value"] for f in brief for n in f["numbers"]] + _numbers(args.context)
    # A view's own parameters (a `since` year) are given by the page it links to.
    known += [
        float(n) for f in brief for u in f["pages"] for n in _QUERY_NUM.findall(u)
    ]
    checks = {name: unverified(text, known) for name, text in _texts(posts)}
    cards = bundle_cards(args.run_dir, posts)
    out = {
        "context": args.context,
        "stats": stats,
        "posts": posts,
        "unverified": checks,
        "cards": cards,
    }
    path.write_text(json.dumps(out, indent=2))
    (args.run_dir / "posts.md").write_text(render(posts, checks, stats, cards))
    (args.run_dir / "article.md").write_text(render_article(posts, cards))
    flagged = sum(len(v) for v in checks.values())
    print(
        f"[posts] {stats.get('seconds', 0):.0f}s; {flagged} unverified number(s); "
        f"{len(cards)} card(s) bundled"
    )
    print(f"-> {args.run_dir / 'posts.md'}")
    return 0


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


def _user(brief: list[dict], context: str) -> str:
    head = f"Occasion: {context}\n\n" if context else ""
    return head + "Findings:\n" + json.dumps(brief, indent=2, ensure_ascii=False)


def _texts(posts: dict) -> list[tuple[str, str]]:
    out = [(f"x_thread[{i}]", t["text"]) for i, t in enumerate(posts["x_thread"])]
    out += [("linkedin", posts["linkedin"]["text"])]
    out += [("facebook", posts["facebook"]["text"])]
    out += [("reddit", posts["reddit"]["title"] + "\n" + posts["reddit"]["body"])]
    out += [
        (
            "html_post",
            posts["html_post"]["title"] + "\n" + posts["html_post"]["markdown"],
        )
    ]
    return out


def _numbers(text: str) -> list[float]:
    return [value for _, readings in _parse_numbers(text) for value, _ in readings]


def _parse_numbers(text: str) -> list[tuple[str, list[tuple[float, float]]]]:
    """Each number in prose as written, with its readings as (value, half its last shown
    unit); a percentage reads both as written and as a share."""
    text = _THREAD_MARK.sub(" ", _URL.sub(" ", text))
    out = []
    for m in _NUM.finditer(text):
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


def x_length(text: str) -> int:
    return len(re.sub(r"https?://\S+", "x" * X_URL_WEIGHT, text))


def card_urls(posts: dict) -> list[str]:
    """Every card a post carries, attached or inline in the article, in order."""
    seen: dict[str, None] = {}
    for post in (
        *posts["x_thread"],
        posts["linkedin"],
        posts["facebook"],
        posts["reddit"],
    ):
        for u in post.get("images", []):
            seen[u] = None
    for m in _CARD.finditer(posts["html_post"]["markdown"]):
        seen[_card_in(m.group(0))] = None
    return list(seen)


def _card_in(matched: str) -> str:
    """The card URL in a `_CARD` match: prose punctuation after it and the bracket of a
    markdown link around it are not part of it, a bracket pair inside its path is."""
    url = matched.rstrip(".,;:!?'")
    while url.endswith(")") and url.count(")") > url.count("("):
        url = url[:-1].rstrip(".,;:!?'")
    return url


def bundle_cards(run_dir: Path, posts: dict) -> dict[str, str]:
    """The posts' cards fetched into `<run>/cards/`, as url -> path relative to the run;
    a card that fails to render is reported and left as its URL."""
    return asyncio.run(_bundle(run_dir, card_urls(posts)))


async def _bundle(run_dir: Path, urls: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for url in urls:
        rel = f"cards/{_card_name(url)}"
        dest = run_dir / rel
        if not dest.exists():
            try:
                png = await fetch_card(url)
            except (CardError, httpx.HTTPError) as exc:
                print(f"[posts] card failed: {url}: {exc}")
                continue
            dest.parent.mkdir(exist_ok=True)
            dest.write_bytes(png)
        out[url] = rel
    return out


def _card_name(url: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", url.split("/card/", 1)[-1].lower()).strip("-")
    return f"{stem[:60]}-{hashlib.sha1(url.encode()).hexdigest()[:6]}.png"


def render_article(posts: dict, cards: dict[str, str]) -> str:
    h = posts["html_post"]
    return f"# {h['title']}\n\n{_localize(h['markdown'], cards)}\n"


def _localize(text: str, cards: dict[str, str]) -> str:
    def local(m: re.Match[str]) -> str:
        url = _card_in(m.group(0))
        return cards.get(url, url) + m.group(0)[len(url) :]

    return _CARD.sub(local, text)


def render(
    posts: dict, checks: dict[str, list[str]], stats: dict, cards: dict[str, str]
) -> str:
    def flag(name: str) -> str:
        bad = checks.get(name)
        return f"\n\n> unverified: {', '.join(bad)}" if bad else ""

    def imgs(urls: list[str]) -> str:
        return "".join(f"\n\n![card]({cards.get(u, u)})" for u in urls)

    out = [f"# Posts\n\n_{stats.get('seconds', 0):.0f}s, ${stats.get('usd', 0):.2f}_"]
    out.append("\n## X thread")
    for i, t in enumerate(posts["x_thread"]):
        n = x_length(t["text"])
        over = " **over the limit**" if n > X_LIMIT else ""
        out.append(f"\n### {i + 1} ({n}/{X_LIMIT}{over})\n\n{t['text']}")
        out.append(imgs(t.get("images", [])) + flag(f"x_thread[{i}]"))
    for name in ("linkedin", "facebook"):
        post = posts[name]
        out.append(f"\n## {name} ({len(post['text'])} chars)\n\n{post['text']}")
        out.append(imgs(post.get("images", [])) + flag(name))
    r = posts["reddit"]
    out.append(f"\n## reddit\n\n**{r['title']}**\n\n{r['body']}")
    out.append(imgs(r.get("images", [])) + flag("reddit"))
    out.append(
        "\n## article ([article.md](article.md))\n\n"
        + render_article(posts, cards).rstrip("\n")
        + flag("html_post")
    )
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
