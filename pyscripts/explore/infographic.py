"""Infographics for an occasion's posts: one near-square image per person.

`uv run -m pyscripts infographic <prize.json> [ids…]` reads a prize file and writes, into
`figures/` beside it, per laureate:
  <key>-infographic.png/.svg  a header with the name large enough to read in a feed's
                              thumbnail, then, in the number of columns that comes closest to a
                              square, sections a scholar can read into: the hit papers with their
                              titles, the co-author timeline, the collaboration network with the
                              most frequent co-authors, journals, citing countries, the hit papers
                              that build on the work (the PNG at most `PNG_MAX_SIDE` on a side);
  <key>-<section>.svg         each section on its own, for a designer to rearrange;
  <key>.txt                   every text and number on the image, to paste instead of retype;
With a "joint" block it also writes joint-landscape/-portrait: the named hit papers as
cumulative citation curves against the top bar. Pictures are the INNER box of the site's own
card SVGs, fetched from `RANKLESS_RENDER_URL`; every number is read from `--backend`. A
tree band the card left unlabelled, its name too long for it, gets the name or its ISO 4
abbreviation (`ABBREV`, `SHORT`) when one fits.

The page beside the prize file (`index.md`, a story page in a stories checkout) is written
when it is missing: each laureate's standfirst, infographic and links. After that it is the
editors', and a draw only sets its `data_version` to the backend's `/v1/specs` version the
figures were read from. Drawing some laureates (`ids…`) on another version than the page's
stops, since the page's figures would then come from two.

The prize file (a stories checkout keeps it as `stories/<slug>/prize.json`): `occasion`,
`share_line`, `laureates` and optionally `joint` (`title`, `subtitle`, `papers` as hit-paper
DOIs). A laureate is `{"id": <author slug>}` plus optional keys: `name` (the name as it
should read), `standfirst`, `stats` (`[[value, label], …]`), `aliases` (co-author names as
they should read; records that read the same count as one), `order` and `skip` (section
names), `impact` (the hit DOIs the impact card shows), `with` (co-author ids the network and
the timeline highlight besides the file's other people), `extra` (`{card, title, sub,
caption, crop: "tree"}` panels), `papers` (`{skip: [OpenAlex work ids], mark: <title regex>,
mark_label}`) for the `papers` section, which takes the place of `hits` for a record with
no hit papers, and `timeline` (`{}`, or the `sort`, `n` and `min` of the site's timeline
card; `min` by default the least that fits the rows) for the `timeline` section after the hit
papers, the co-authors by the years of their shared papers.

`--check` prints, per laureate, what a human must look at before anything is posted: other
records under the same name, the span of years, the top co-authors, journals and fields. A
record that holds a namesake's papers shows there; give it `"skip": ["network", "journals",
"countries"]`, paper-level `"stats"` and `"extra"` panels, never its totals.

Must hold before it runs: `rsvg-convert` on PATH and the brand fonts (`static/fonts/`)
registered with fontconfig, as `deploy` installs them on a box.
"""

import html
import itertools
import json
import math
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import date
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from mcp_server import MAIN_DOMAIN, RENDER_URL, resolve_backend
from mcp_server.cards import KINDS
from pyscripts.paths import asset
from wire.rankless_rs.metrics import PAPER_SCORE
from wire.rankless_server.responses import METHODOLOGY, TREE_SPECS

Svg = list[str]
Section = Callable[[dict, float, float, float], tuple[Svg, float]]
# A co-author a person's pictures highlight, as (author id, name).
Mark = tuple[str, str]

FONT_DIR = Path(__file__).resolve().parents[2] / "static/fonts"
FACES = {
    "serif": ("'Hedvig Letters Serif', serif", "HedvigLettersSerif.ttf", "normal"),
    "sans": (
        "'Hedvig Letters Sans', sans-serif",
        "HedvigLettersSans-Regular.ttf",
        "normal",
    ),
    "mono": ("'Space Mono', monospace", "SpaceMono-Regular.ttf", "normal"),
    "monob": ("'Space Mono', monospace", "SpaceMono-Bold.ttf", "bold"),
}
_STYLE = asset("card-style.json")
ACCENT, SPECTRUM = _STYLE["accent"], _STYLE["spectrum"]
INK, MUTED, FAINT, PAPER, HAIR = "#21272a", "#4f4f4f", "#9aa0a6", "#ffffff", "#d9dde1"
PALETTE = [
    "#7d0082",
    "#269ada",
    "#e1b01e",
    "#5842a8",
    "#0aa5cc",
    "#af5850",
    "#21272a",
    "#6b7379",
]
STAT_COLORS = ["#269ada", "#7d0082", "#e1b01e"]
MARKED, UNMARKED = "#7d0082", "#9aa0a6"
# The rows of a card's INNER box a closed tree draws in, as (top, height).
TREE_BAND = (24, 294)
FINAL_YEAR = METHODOLOGY["workScreen"]["finalYear"]
# A paper with more authorship rows than this carries no co-author relation on the site.
TEAM_LIMIT = METHODOLOGY["workScreen"]["teamLimit"]
SINCE_ALL = TREE_SPECS["yearBreaks"][0]
TOP = f"{PAPER_SCORE['topShare'] * 100:g}%"
_HIT = next(t for t in METHODOLOGY["texts"] if t["id"] == "hit_paper")
HIT_MEANING = f"{_HIT['label']}: {_HIT['meaning']}"
JOURNAL = {"Proceedings of the National Academy of Sciences": "PNAS"}
# A tree band's label, when the journal's full name does not fit the band, is its ISO 4
# abbreviation: these words shortened, these dropped, and these names abbreviated whole.
ABBREV = {
    "academy": "Acad.",
    "accelerators": "Accel.",
    "advanced": "Adv.",
    "american": "Am.",
    "angewandte": "Angew.",
    "annual": "Annu.",
    "applied": "Appl.",
    "astroparticle": "Astropart.",
    "astrophysical": "Astrophys.",
    "biochemistry": "Biochem.",
    "biological": "Biol.",
    "biology": "Biol.",
    "biophysical": "Biophys.",
    "biotechnology": "Biotechnol.",
    "bulletin": "Bull.",
    "catalysis": "Catal.",
    "cellular": "Cell.",
    "chemical": "Chem.",
    "chemie": "Chem.",
    "chemistry": "Chem.",
    "communications": "Commun.",
    "edition": "Ed.",
    "experimental": "Exp.",
    "frontiers": "Front.",
    "general": "Gen.",
    "instrumentation": "Instrum.",
    "instruments": "Instrum.",
    "international": "Int.",
    "japan": "Jpn.",
    "journal": "J.",
    "letters": "Lett.",
    "medicine": "Med.",
    "microbiology": "Microbiol.",
    "molecular": "Mol.",
    "national": "Natl.",
    "nature": "Nat.",
    "neuroscience": "Neurosci.",
    "nuclear": "Nucl.",
    "organic": "Org.",
    "organometallic": "Organomet.",
    "physical": "Phys.",
    "physics": "Phys.",
    "physiology": "Physiol.",
    "proceedings": "Proc.",
    "protocols": "Protoc.",
    "research": "Res.",
    "review": "Rev.",
    "reviews": "Rev.",
    "science": "Sci.",
    "sciences": "Sci.",
    "society": "Soc.",
    "synthesis": "Synth.",
}
UNABBREVIATED = {"the", "of", "and", "&", "in", "for", "on"}
SHORT = {
    "Nuclear Instruments and Methods in Physics Research Section A Accelerators "
    "Spectrometers Detectors and Associated Equipment": "NIM A",
}
# A filled tree label: the step between its lines and the box's inner margin in units of the
# tree's 10-unit font, the largest scale of that font it takes, and the smallest it is drawn
# at, in pixels of the infographic.
TREE_LINE, TREE_PAD, TREE_LABEL_MAX, TREE_LABEL_MIN = 15, 1, 0.55, 18
SECTIONS = ("hits", "network", "impact", "journals", "countries")
NETWORK_NODES = KINDS["network"]["params"]["n"]["default"]
TIMELINE = KINDS["timeline"]["params"]
# What each drawn section says, for the text file that goes with an infographic.
COPY: list[str] = []
# The width the sections are drawn at, the margin around the infographic and the gap between
# its columns.
ROOM, MARGIN, GUTTER = 1944, 108, 216
# X shrinks a larger image to this on its longest side.
PNG_MAX_SIDE = 4096
BE = resolve_backend("live")[0]


# Type and SVG pieces.


@lru_cache(maxsize=None)
def _font(face: str) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / FACES[face][1]), 200)


def width(s: str, size: float, face: str = "sans", spacing: float = 0) -> float:
    return _font(face).getlength(s) * size / 200 + spacing * len(s)


def fit(s: str, room: float, size: float, face: str = "sans") -> float:
    return min(size, size * room / width(s, size, face))


def text(
    x: float,
    y: float,
    s: str,
    size: float,
    face: str = "sans",
    fill: str = INK,
    anchor: str = "start",
    spacing: float = 0,
) -> str:
    family, _, weight = FACES[face]
    extra = f' letter-spacing="{spacing}"' if spacing else ""
    extra += ' font-weight="bold"' if weight == "bold" else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size:.1f}" '
        f'fill="{fill}" text-anchor="{anchor}"{extra}>{html.escape(s)}</text>'
    )


def wrap(
    s: str, room: float, size: float, face: str = "sans", max_lines: int = 3
) -> list[str]:
    lines, line = [], ""
    for w in s.split():
        trial = f"{line} {w}".strip()
        if width(trial, size, face) <= room or not line:
            line = trial
        else:
            lines.append(line)
            line = w
    lines.append(line)
    if len(lines) > max_lines:
        last = " ".join(lines[max_lines - 1 :])
        while width(last + "…", size, face) > room and " " in last:
            last = last.rsplit(" ", 1)[0]
        lines = lines[: max_lines - 1] + [last.rstrip(",;:") + "…"]
    return lines


def hline(x1: float, x2: float, y: float, color: str = HAIR, w: float = 2) -> str:
    return (
        f'<line x1="{x1:.1f}" x2="{x2:.1f}" y1="{y:.1f}" y2="{y:.1f}" '
        f'stroke="{color}" stroke-width="{w}"/>'
    )


def vline(x: float, y1: float, y2: float, color: str = INK, w: float = 3) -> str:
    return (
        f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y1:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-width="{w}"/>'
    )


def strip(w: float, h: float) -> str:
    step = w / len(SPECTRUM)
    return "".join(
        f'<rect x="{i * step:.1f}" y="0" width="{step + 1:.1f}" height="{h}" fill="{c}"/>'
        for i, c in enumerate(SPECTRUM)
    )


def footer(w: float, h: float, m: float, url: str, scale: float = 1.0) -> str:
    return text(m, h - 52 * scale, "Rankless", 62 * scale, "serif") + text(
        w - m, h - 56 * scale, url, 36 * scale, "mono", ACCENT, "end"
    )


def write(
    out: Path, name: str, w: float, h: float, body: Svg, png: bool = True
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    w, h = round(w), round(h)
    svg = out / f"{name}.svg"
    svg.write_text(
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{w}" height="{h}" fill="{PAPER}"/>' + "".join(body) + "</svg>"
    )
    if png:
        target = out / f"{name}.png"
        k = min(1, PNG_MAX_SIDE / max(w, h))
        subprocess.run(
            [
                "rsvg-convert",
                "-f",
                "png",
                "-w",
                str(round(w * k)),
                "-h",
                str(round(h * k)),
            ]
            + [str(svg), "-o", str(target)],
            check=True,
        )
        print(target)


def commas(n: float) -> str:
    return f"{n:,.0f}"


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def plain(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def journal(name: str) -> str:
    if name.startswith("Physical review. D"):
        return "Physical Review D"
    return JOURNAL.get(name, name)


def journal_names(papers: list[dict], sources: dict[int, str]) -> dict[str, str]:
    """Each source's display name; sources that display alike carry the years of the
    author's papers in them."""
    years: dict[str, list[int]] = {}
    for p in papers:
        years.setdefault(sources.get(p["source"], "?"), []).append(p["year"])
    alike = Counter(journal(raw) for raw in years)
    return {
        raw: journal(raw) if alike[journal(raw)] == 1 else f"{journal(raw)}, {span(ys)}"
        for raw, ys in years.items()
    }


def span(years: list[int]) -> str:
    lo, hi = min(years), max(years)
    return str(lo) if lo == hi else f"{lo}–{hi}"


def listed(names: list[str], most: int = 4) -> str:
    if len(names) > most:
        names = [*names[: most - 1], f"{len(names) - most + 1} others"]
    if len(names) == 1:
        return names[0]
    return " and ".join([", ".join(names[:-1]), names[-1]])


def year_scale(x0: int, left: float, right: float) -> Callable[[float], float]:
    def sx(yr: float) -> float:
        return left + (yr - x0) / max(1, FINAL_YEAR - x0) * (right - left)

    return sx


# The site and its data.


@lru_cache(maxsize=None)
def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (rankless-infographic)"}
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in (502, 503, 504) or attempt == 4:
                raise
            time.sleep(2 + attempt * 2)
    raise AssertionError("unreachable")


def get(path: str, **q: object) -> dict:
    query = "?" + urllib.parse.urlencode(q) if q else ""
    return json.loads(fetch(BE + path + query))


def card_svg(ref: str) -> str:
    path, _, query = ref.partition("?")
    return fetch(
        f"{RENDER_URL}/card/{path}.svg" + (f"?{query}" if query else "")
    ).decode()


def card_inner(ref: str, prefix: str) -> tuple[str, float, float]:
    """The picture a card draws in its INNER box (the frame's first nested `<svg>`), its ids
    under `prefix`, with the box's width and height."""
    svg = card_svg(ref)
    box = re.search(
        r'<svg x="[\d.]+" y="[\d.]+" width="([\d.]+)" height="([\d.]+)">', svg
    )
    if box is None:
        raise SystemExit(f"{ref}: no INNER box in the card")
    depth, pos = 1, box.end()
    for m in re.finditer(r"<svg\b|</svg>", svg[box.end() :]):
        depth += 1 if m.group(0) != "</svg>" else -1
        if depth == 0:
            pos = box.end() + m.start()
            break
    inner = svg[box.end() : pos]
    inner = re.sub(r'\bid="([^"]+)"', rf'id="{prefix}\1"', inner)
    inner = re.sub(r"url\((['\"]?)#([^)'\"]+)\1\)", rf"url(\1#{prefix}\2\1)", inner)
    inner = re.sub(r'\bhref="#([^"]+)"', rf'href="#{prefix}\1"', inner)
    return inner, float(box.group(1)), float(box.group(2))


def panel(
    ref: str,
    x: float,
    y: float,
    w: float,
    prefix: str,
    crop: str | None = None,
    names: dict[str, str] | None = None,
) -> tuple[str, float]:
    """A card's picture `w` wide at (x, y); `crop="tree"` shows only `TREE_BAND`, with a
    label in every band the card left without one (`names` maps a band's name to how it
    reads), `crop="content"` the rows down to its lowest text."""
    inner, iw, ih = card_inner(ref, prefix)
    vy, vh = (0, ih)
    if crop == "tree":
        vy, vh = TREE_BAND
        inner = fill_tree_labels(
            inner, card_tree_bands(ref), names or {}, w / iw, iw, ih
        )
    elif crop == "content":
        vh = (
            max(float(y) for y in re.findall(r'<text\b[^>]*?\sy="([\d.]+)"', inner))
            + 12
        )
    h = w * vh / iw
    return (
        f'<svg x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'viewBox="0 {vy} {iw:g} {vh}"><svg width="{iw:g}" height="{ih:g}">'
        f"{inner}</svg></svg>",
        h,
    )


_TREE_BOX = re.compile(r'<svg viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"')
_BAND = re.compile(
    r'(<g style="transform:\s*matrix\([^)]*\)[^"]*"[^>]*>(.*?)</g>)(?:<!--[^>]*-->)*'
    r'<rect x="([\d.]+)" y="([\d.]+)" height="([\d.]+)" width="([\d.]+)"',
    re.S,
)


def fill_tree_labels(
    inner: str,
    bands: list[tuple[str, int]],
    names: dict[str, str],
    k: float,
    iw: float,
    ih: float,
) -> str:
    """A tree card's INNER picture, drawn at `k` times its size, with a label in each
    level-1 band the card left without one: the first of the band's name as `names` reads
    it, its journal name and its abbreviation that fits at `TREE_LABEL_MIN` or larger.
    `bands` are the tree's (name, citation links) largest first, the card's bands from left
    to right up to the order of equal ones; a band whose size other unlabelled bands share
    stays unlabelled."""
    box = _TREE_BOX.search(inner)
    if box is None:
        raise SystemExit("no tree in the tree card")
    px = 10 * k * min(iw / float(box.group(1)), ih / float(box.group(2)))
    left_to_right = sorted(_BAND.finditer(inner), key=lambda m: float(m.group(3)))
    drawn = [
        html.unescape(
            " ".join(
                w for w in re.findall(r"<text[^>]*>([^<]*)</text>", m.group(2)) if w
            )
        )
        for m in left_to_right
    ]
    spaced = {(" ".join(n.split()), c) for n, c in bands}
    edits = []
    for m, label_drawn, (_, size) in zip(left_to_right, drawn, bands):
        if label_drawn:
            if (label_drawn, size) not in spaced:
                raise SystemExit(f"tree band {label_drawn!r} has no band of its size")
            continue
        tied = [n for n, c in bands if c == size and " ".join(n.split()) not in drawn]
        if len(tied) != 1:
            print(f"  {len(tied)} unlabelled bands of {size} citation links")
            continue
        name = tied[0]
        x, y, h, w = (float(m.group(i)) for i in (3, 4, 5, 6))
        short = SHORT.get(name) or abbreviation(journal(name))
        texts = [names.get(name, journal(name)), journal(name), short]
        label = band_label(
            [t for t in dict.fromkeys(texts) if t], x, y, w, h, TREE_LABEL_MIN / px
        )
        if label is None:
            print(f"  no label fits the band of {name}")
            continue
        edits.append((m.start(1), m.end(1), label))
    for start, end, label in sorted(edits, reverse=True):
        inner = inner[:start] + label + inner[end:]
    return inner


def band_label(
    texts: list[str], x: float, y: float, w: float, h: float, least: float
) -> str | None:
    """The first of `texts` that fits a band's box at `least` of the tree font or larger, as
    large as the box takes: its words broken into lines and turned upright when that fits
    larger, centred across the box and set on its bottom."""
    for t in texts:
        k, turned, lines = band_fit(t.split(), w, h)
        if k < least:
            continue
        thick = TREE_LINE * (len(lines) - 1) + 10
        if turned:
            X, Y = x + w / 2 + k * (thick - 5) / 2, y + h - TREE_PAD
            matrix = f"0,{-k:.4f},{k:.4f},0,{X:.3f},{Y:.3f}"
        else:
            X, Y = x + TREE_PAD, y + h - TREE_PAD - 2.5 * k
            matrix = f"{k:.4f},0,0,{k:.4f},{X:.3f},{Y:.3f}"
        rows = "".join(
            f'<text y="{TREE_LINE * (i - len(lines) + 1)}">{html.escape(line)}</text>'
            for i, line in enumerate(lines)
        )
        return f'<g transform="matrix({matrix})" fill="{INK}">{rows}</g>'
    return None


def band_fit(words: list[str], w: float, h: float) -> tuple[float, bool, list[str]]:
    """The largest scale of the tree font `words` fit a w × h box at, whether turned upright,
    and the lines they break into."""
    best = (0.0, False, [" ".join(words)])
    for cuts in range(2 ** (len(words) - 1)):
        lines, line = [], [words[0]]
        for i, word in enumerate(words[1:]):
            if cuts >> i & 1:
                lines.append(" ".join(line))
                line = []
            line.append(word)
        lines.append(" ".join(line))
        long = max(width(t, 10, "mono") for t in lines)
        thick = TREE_LINE * (len(lines) - 1) + 10
        for turned, along, across in ((False, w, h), (True, h, w)):
            k = min(
                (along - 2 * TREE_PAD) / long,
                (across - 2 * TREE_PAD) / thick,
                TREE_LABEL_MAX,
            )
            if k > best[0]:
                best = (k, turned, lines)
    return best


def abbreviation(name: str) -> str:
    words = [w.rstrip(".,:") for w in name.split()]
    return " ".join(
        ABBREV.get(w.lower(), w) for w in words if w.lower() not in UNABBREVIATED
    )


def card_tree_bands(ref: str) -> list[tuple[str, int]]:
    """The level-1 bands of the tree a tree card draws, largest first."""
    path, _, query = ref.partition("?")
    q = dict(urllib.parse.parse_qsl(query))
    root, rest = path.split("/", 1)
    tid = int(q.get("tree", 1)) - 1
    att = TREE_SPECS["specs"][root][tid]["breakdowns"][0]["attributeType"]
    since = int(q.get("since", SINCE_ALL))
    return tree_bands(root, rest.rsplit("/", 1)[0], tid, att, since)


def tree_bands(
    root_type: str, sem: str, tid: int, att: str, since: int = SINCE_ALL
) -> list[tuple[str, int]]:
    """A tree's level-1 bands from `since` as (name, citation links), largest first; `tid`
    counts from 0."""
    r = get(
        f"/trees/{root_type}/{urllib.parse.quote(sem, safe='')}",
        year=since,
        tid=tid,
    )
    names = r["atts"][att]
    bands = sorted(r["tree"]["children"].items(), key=lambda kv: -kv[1]["linkCount"])
    return [(names[k]["name"], v["linkCount"]) for k, v in bands]


def coauthors(
    papers: list[dict], me: str, shown: Callable[[str], str]
) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    """The years of the shared papers per co-author id, in the order the papers first name
    them, and per shown name, over the papers the site draws co-author relations from
    (`TEAM_LIMIT`)."""
    by_id: dict[str, list[int]] = {}
    collab: dict[str, list[int]] = {}
    for p in papers:
        if p["authorCount"] > TEAM_LIMIT or p["year"] <= 0:
            continue
        ids = [a["author"] for a in p["authorships"] if a["author"] != me]
        for k in ids:
            by_id.setdefault(k, []).append(p["year"])
        for n in {shown(k) for k in ids}:
            collab.setdefault(n, []).append(p["year"])
    return by_id, collab


def author(spec: dict) -> dict:
    """An author as the infographic needs it: the view, every paper, the hit papers by
    citations and the co-authors by shared papers. The papers come in the backend's default
    order, the one the site's cards read them in."""
    sem = spec["id"]
    view = get(f"/views/authors/{sem}")
    papers: list[dict] = []
    names: dict[str, str] = {}
    sems: dict[str, str] = {}
    sources: dict[int, str] = {}
    while len(papers) < view["papers"]:
        resp = get(f"/works/authors/{sem}/{len(papers)}")["resp"]
        if not resp["papers"]:
            raise SystemExit(f"{sem}: works end at {len(papers)} of {view['papers']}")
        papers += resp["papers"]
        authors = resp["entityAtts"]["authors"].items()
        names |= {f"F{k}": v["name"] for k, v in authors}
        sems |= {f"F{k}": v["semantic_id"] for k, v in authors}
        names |= resp["discAuthorNames"]
        sources |= {int(k): v["name"] for k, v in resp["entityAtts"]["sources"].items()}
    me = f"F{view['dmId']}"
    alias = spec.get("aliases", {})

    def shown(a: str) -> str:
        return alias.get(names.get(a, a), names.get(a, a))

    by_id, collab = coauthors(papers, me, shown)
    name = spec.get("name") or plain(view["name"])
    by_cites = sorted(papers, key=lambda p: -p["citations"])
    hits = [
        {
            "title": plain(p["name"]),
            "journal": journal(sources.get(p["source"], "")),
            "year": p["year"],
            "citations": p["citations"],
            "multiple": p["citations"] / p["bar"],
            "score": p["score"],
            "cum": [
                sum(p["yearlyCites"][: i + 1]) for i in range(len(p["yearlyCites"]))
            ],
            "doi": p["hitSemId"],
            "authors": [a["author"] for a in p["authorships"]],
        }
        for p in by_cites
        if p["isHit"]
    ]
    return {
        "sem": sem,
        "me": me,
        "view": view,
        "name": name,
        "record": plain(view["name"]),
        "last": name.split()[-1],
        "papers": [
            {
                "oa": p["oaId"],
                "title": plain(p["name"]),
                "journal": journal(sources.get(p["source"], "")),
                "year": p["year"],
                "citations": p["citations"],
                "top1": bool(p.get("bar")) and p["citations"] >= p["bar"],
                "authors": p["authorCount"],
                "with": [
                    shown(x["author"]) for x in p["authorships"] if x["author"] != me
                ],
            }
            for p in by_cites
        ],
        "skip_papers": spec.get("papers", {}).get("skip", []),
        "collab": collab,
        "years": (min(p["year"] for p in papers), max(p["year"] for p in papers)),
        "hits": hits,
        "coauthors": sorted(
            ((n, len(ys)) for n, ys in collab.items()), key=lambda r: -r[1]
        )[:40],
        "team": {
            k: {"name": shown(k), "sem": sems.get(k), "years": ys}
            for k, ys in by_id.items()
            if k in names
        },
        "journals": Counter(
            sources.get(p["source"], "?") for p in papers
        ).most_common(),
        "journal_names": journal_names(papers, sources),
    }


# The sections of a laureate's infographic. Each returns its SVG parts and its bottom edge.


def section_head(
    x: float, y: float, title: str, sub: str, caption: str, room: float
) -> tuple[Svg, float]:
    COPY.append(f"{title}\n{caption}")
    size = fit(title, room, 66, "serif")
    out = [text(x - 3, y, title, size, "serif")]
    if sub and width(title, size, "serif") + 30 + width(sub, 32) <= room:
        out.append(
            text(x + width(title, size, "serif") + 30, y, sub, 32, "sans", FAINT)
        )
    for line in wrap(caption, room, 38, "sans", 3):
        y += 54
        out.append(text(x, y, line, 38, "sans", MUTED))
    return out, y + 34


def spread(ys: list[float], gap: float, lo: float, hi: float) -> list[float]:
    """Positions as near `ys` as a minimum `gap` allows, in the same order, within lo..hi."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    pos = [min(max(ys[i], lo), hi) for i in order]
    for k in range(1, len(pos)):
        pos[k] = max(pos[k], pos[k - 1] + gap)
    if pos and pos[-1] > hi:
        pos[-1] = hi
        for k in range(len(pos) - 2, -1, -1):
            pos[k] = min(pos[k], pos[k + 1] - gap)
    out = [0.0] * len(ys)
    for k, i in enumerate(order):
        out[i] = pos[k]
    return out


def year_ticks(x0: int) -> range:
    span = FINAL_YEAR - x0
    tick = 1 if span <= 8 else 2 if span <= 16 else 5 if span <= 40 else 10
    return range(x0 + (-x0) % tick, FINAL_YEAR + 1, tick)


def year_axis(
    x0: int, sx: Callable[[float], float], top: float, bottom: float, grid: bool = False
) -> Svg:
    out = []
    for yr in year_ticks(x0):
        if grid:
            out.append(vline(sx(yr), top, bottom, HAIR, 2))
        else:
            out.append(vline(sx(yr), bottom, bottom + 12))
        out.append(text(sx(yr), bottom + 50, str(yr), 30, "mono", MUTED, "middle"))
    return out


def value_grid(
    ticks: list[int], sy: Callable[[float], float], left: float, right: float
) -> Svg:
    out = []
    for v in ticks:
        out.append(hline(left, right, sy(v)))
        out.append(text(left - 18, sy(v) + 10, commas(v), 28, "mono", FAINT, "end"))
    out.append(hline(left, right, sy(0), INK, 3))
    return out


def numbered_dot(cx: float, cy: float, n: int, color: str, ring: bool = False) -> Svg:
    stroke = f' stroke="{PAPER}" stroke-width="4"' if ring else ""
    return [
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="27" fill="{color}"{stroke}/>',
        text(cx, cy + 11, str(n), 30, "monob", PAPER, "middle"),
    ]


def hits_chart(
    hits: list[dict], left: float, right: float, top: float, bottom: float
) -> Svg:
    """Cumulative citations by calendar year, each curve ending in its paper's number."""
    x0 = min(p["year"] for p in hits)
    peak = max(p["citations"] for p in hits)
    ladder = (100, 250, 500, 1000, 2500, 5000, 10000, 25000, 50000)
    step = next(s for s in ladder if peak / s <= 5)
    ymax = math.ceil(peak / step) * step
    sx = year_scale(x0, left, right)

    def sy(v: float) -> float:
        return bottom - v / ymax * (bottom - top)

    out = value_grid(list(range(step, ymax + 1, step)), sy, left, right)
    out += year_axis(x0, sx, top, bottom)
    ends = [sy(p["cum"][-1]) for p in hits]
    marks = spread(ends, 62, top + 28, bottom - 28)
    for i in reversed(range(len(hits))):
        p, color = hits[i], PALETTE[i % len(PALETTE)]
        pts = " ".join(
            f"{sx(p['year'] + k):.1f},{sy(c):.1f}" for k, c in enumerate(p["cum"])
        )
        out.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="{11 if i == 0 else 7}" stroke-linecap="round" '
            'stroke-linejoin="round"/>'
        )
        out.append(
            f'<line x1="{right:.1f}" y1="{ends[i]:.1f}" x2="{right + 58:.1f}" '
            f'y2="{marks[i]:.1f}" stroke="{color}" stroke-width="2" stroke-dasharray="3 7"/>'
        )
        out += numbered_dot(right + 84, marks[i], i + 1, color)
    return out


def hits_section(a: dict, x: float, y: float, room: float) -> tuple[Svg, float]:
    hits = a["hits"][:8]
    n = len(hits)
    if len(a["hits"]) > n:
        which = f"The {n} most-cited of {len(a['hits'])} hit papers"
    else:
        which = f"{a['last']}'s {plural(n, 'hit paper')}"
    caption = f"{which}, with the multiple of the top-{TOP} bar each has reached. {HIT_MEANING}"
    out, y = section_head(
        x, y, "Hit papers", "cumulative citations by year", caption, room
    )
    out += hits_chart(hits, x + 130, x + room - 130, y + 20, y + 640)
    y += 760
    rows = math.ceil(n / 2)
    col_w = (room - 90) / 2
    for i, p in enumerate(hits):
        ex, ey = x + (i // rows) * (col_w + 90), y + (i % rows) * 182
        color = PALETTE[i % len(PALETTE)]
        out += numbered_dot(ex + 27, ey + 22, i + 1, color)
        lines = wrap(p["title"], col_w - 80, 35, "sans", 2)
        for k, line in enumerate(lines):
            out.append(text(ex + 80, ey + 33 + k * 44, line, 35, "sans", INK))
        meta = hit_meta(p)
        out.append(
            text(
                ex + 80,
                ey + 33 + len(lines) * 44 + 2,
                meta,
                fit(meta, col_w - 80, 28),
                "sans",
                color,
            )
        )
    return out, y + rows * 182


def hit_meta(p: dict) -> str:
    return (
        f"{p['journal']} · {p['year']} · {commas(p['citations'])} citations · "
        f"{p['multiple']:.1f}× bar"
    )


def papers_chart(
    papers: list[dict],
    top: list[dict],
    marked: list[dict],
    left: float,
    right: float,
    top_y: float,
    bottom: float,
) -> Svg:
    """Every paper as a dot by year and citations (square-root scale), the listed ones
    numbered."""
    x0 = min(p["year"] for p in papers)
    peak = max(p["citations"] for p in papers)
    ladder = (0, 10, 50, 100, 200, 300, 500, 1000, 2000, 5000, 10000, 20000, 50000)
    ticks = [t for t in ladder if t < peak] + [next(t for t in ladder if t >= peak)]
    sx = year_scale(x0, left, right)

    def sy(v: float) -> float:
        return bottom - math.sqrt(v / ticks[-1]) * (bottom - top_y)

    out = value_grid(ticks[1:], sy, left, right)
    out += year_axis(x0, sx, top_y, bottom)
    ids = {id(p) for p in marked}
    for p in sorted(papers, key=lambda p: id(p) in ids):
        color = MARKED if id(p) in ids else UNMARKED
        out.append(
            f'<circle cx="{sx(p["year"]):.1f}" cy="{sy(p["citations"]):.1f}" r="9" '
            f'fill="{color}" fill-opacity="0.55"/>'
        )
    for i in reversed(range(len(top))):
        p = top[i]
        color = MARKED if id(p) in ids else INK
        out += numbered_dot(sx(p["year"]), sy(p["citations"]), i + 1, color, ring=True)
    return out


def listed_papers(a: dict) -> list[dict]:
    return [p for p in a["papers"] if p["oa"] not in a["skip_papers"]][:8]


def papers_section(opts: dict) -> Section:
    mark = re.compile(opts["mark"], re.I) if opts.get("mark") else None

    def draw(a: dict, x: float, y: float, room: float) -> tuple[Svg, float]:
        papers = a["papers"]
        top = listed_papers(a)
        marked = [p for p in papers if mark and mark.search(p["title"])]
        ids = {id(p) for p in marked}
        caption = (
            f"One dot for each of the {len(papers)} papers, by year and citations. "
            f"Numbered: the {len(top)} most-cited research papers."
        )
        if marked:
            first = min(p["year"] for p in marked)
            caption += (
                f" Purple: the {len(marked)} papers with {opts['mark_label']} in the "
                f"title, the first in {first}."
            )
        out, y = section_head(
            x, y, "Most-cited papers", "citations by year of publication", caption, room
        )
        out += papers_chart(
            papers, top, marked, x + 130, x + room - 40, y + 40, y + 640
        )
        y += 780
        rows = math.ceil(len(top) / 2)
        col_w = (room - 90) / 2
        for i, p in enumerate(top):
            ex, ey = x + (i // rows) * (col_w + 90), y + (i % rows) * 226
            color = MARKED if id(p) in ids else INK
            out += numbered_dot(ex + 27, ey + 22, i + 1, color)
            lines = wrap(p["title"], col_w - 80, 35, "sans", 2)
            for k, line in enumerate(lines):
                out.append(text(ex + 80, ey + 33 + k * 44, line, 35, "sans", INK))
            ty = ey + 33 + len(lines) * 44 + 2
            meta, team = paper_meta(p), paper_team(p)
            out.append(
                text(ex + 80, ty, meta, fit(meta, col_w - 80, 28), "sans", color)
            )
            out.append(
                text(ex + 80, ty + 40, team, fit(team, col_w - 80, 28), "sans", MUTED)
            )
        return out, y + rows * 226 - 30

    return draw


def paper_meta(p: dict) -> str:
    meta = f"{p['journal']} · {p['year']} · {commas(p['citations'])} citations"
    return meta + (f" · top {TOP} of its field and year" if p["top1"] else "")


def paper_team(p: dict) -> str:
    if p["authors"] > TEAM_LIMIT:
        return f"one of {commas(p['authors'])} authors"
    return f"with {listed(p['with'])}" if p["with"] else "sole author"


def row_key(sort: str, years: list[int]) -> tuple[int, int]:
    n, first, last = len(years), min(years), max(years)
    return {"first": (first, -n), "recent": (-last, -n), "count": (-n, first)}[sort]


def timeline_opts(a: dict, spec: dict, marks: list[Mark]) -> dict:
    """The timeline card's `sort`, `n` and `min` for `a`: the prize file's, `min` by default
    the least that leaves no more co-authors than the rows the marked ones leave free."""
    opts = {
        "sort": TIMELINE["sort"]["default"],
        "n": TIMELINE["n"]["default"],
        **spec.get("timeline", {}),
    }
    if "min" not in opts:
        on = {k for k, _ in marks}
        counts = sorted(
            (len(c["years"]) for k, c in a["team"].items() if k not in on), reverse=True
        )
        free = opts["n"] - len(on)
        opts["min"] = max(
            TIMELINE["min"]["default"], counts[free] + 1 if len(counts) > free else 0
        )
    return opts


def timeline_rows(
    a: dict, opts: dict, marks: list[Mark]
) -> list[tuple[str, list[int]]]:
    """The rows the site's timeline card draws for `opts`, as (co-author id, years of the
    shared papers): sorted, the first `n` that clear `min`, every marked one kept in place."""
    on = {k for k, _ in marks}
    free = opts["n"] - len(on)
    rows = []
    by = opts["sort"]
    for k, c in sorted(a["team"].items(), key=lambda kv: row_key(by, kv[1]["years"])):
        if k in on or (len(c["years"]) >= opts["min"] and free > 0):
            rows.append((k, c["years"]))
            free -= k not in on
    return rows


def timeline_section(opts: dict, marks: list[Mark]) -> Section:
    def draw(a: dict, x: float, y: float, room: float) -> tuple[Svg, float]:
        least = opts["min"]
        rows = timeline_rows(a, opts, marks)
        clear = sum(len(c["years"]) >= least for c in a["team"].values())
        shown = sum(len(ys) >= least for _, ys in rows)
        caption = (
            f"{a['last']}'s co-authors with at least {plural(least, 'shared paper')}, by the "
            "years of their papers together"
            + (f", {shown} of {clear}" if clear > shown else "")
            + "."
        )
        if marks:
            caption += " Highlighted: " + "; ".join(
                f"{name}, {coauthor_span(a, k)}" for k, name in marks
            )
            caption += "."
        out, y = section_head(x, y, "Co-author timeline", "", caption, room)
        query = {k: opts[k] for k in ("sort", "n", "min")}
        if marks:
            query["with"] = ",".join(a["team"][k]["sem"] for k, _ in marks)
        q = urllib.parse.urlencode(query, safe=",")
        ref = f"authors/{a['sem']}/timeline?{q}"
        svg, h = panel(ref, x, y, room, "t-", "content")
        return out + [svg], y + h + 10

    return draw


def coauthor_span(a: dict, k: str) -> str:
    years = a["team"][k]["years"]
    return f"{plural(len(years), 'shared paper')}, {span(years)}"


def marks_of(a: dict, cfg: dict, spec: dict) -> list[Mark]:
    """The co-authors `a`'s network and timeline highlight: the file's other people `a`
    shares papers with, then the `with` ones."""
    named = {f["me"]: f["name"] for f in cfg["fellows"] if f["me"] in a["team"]}
    by_sem = {c["sem"]: k for k, c in a["team"].items() if c["sem"]}
    for s in spec.get("with", []):
        if s not in by_sem:
            raise SystemExit(
                f"{a['sem']}: {s} shares no paper the site draws co-authors from"
            )
        named.setdefault(by_sem[s], a["team"][by_sem[s]]["name"])
    return list(named.items())


def network_section(marks: list[Mark]) -> Section:
    def draw(a: dict, x: float, y: float, room: float) -> tuple[Svg, float]:
        top_name, top_n = a["coauthors"][0]
        caption = f"Most frequent co-author: {top_name}, {top_n} shared papers."
        caption += "".join(
            f" With {name}: {len(a['team'][k]['years'])}." for k, name in marks
        )
        sub = "co-authors sized by shared papers; ties are their joint papers"
        out, y = section_head(x, y, "Collaboration network", sub, caption, room)
        nodes = {
            r["semanticId"]
            for r in a["view"]["relations"]["paper-authors"][:NETWORK_NODES]
        }
        on = [a["team"][k]["sem"] for k, _ in marks if a["team"][k]["sem"] in nodes]
        ref = f"authors/{a['sem']}/network" + (f"?with={','.join(on)}" if on else "")
        svg, h = panel(ref, x, y, room, "n-")
        out.append(svg)
        items = [(n, f"{c} shared papers") for n, c in a["coauthors"][:8]]
        parts, y = name_list(items, x, y + h + 56, room)
        return out + parts, y

    return draw


def name_list(
    items: list[tuple[str, str]], x: float, y: float, room: float
) -> tuple[Svg, float]:
    """Up to eight names with a detail line each, in four columns: the data labels a picture
    cannot fit."""
    out, col_w = [], room / 4
    for i, (name, detail) in enumerate(items[:8]):
        ex, ey = x + (i % 4) * col_w, y + (i // 4) * 118
        out.append(
            text(ex, ey, wrap(name, col_w - 30, 34, "sans", 1)[0], 34, "sans", INK)
        )
        size = fit(detail, col_w - 30, 27, "mono")
        out.append(text(ex, ey + 38, detail, size, "mono", MUTED))
    return out, y + math.ceil(len(items[:8]) / 4) * 118 + 50


def card_section(
    title: str,
    sub: str,
    caption: str,
    ref: str,
    prefix: str,
    crop: str | None = None,
    items: list[tuple[str, str]] | None = None,
    names: dict[str, str] | None = None,
) -> Section:
    """A heading, a card's picture and, with `items`, the names and numbers behind it."""

    def draw(a: dict, x: float, y: float, room: float) -> tuple[Svg, float]:
        out, y = section_head(x, y, title, sub, caption, room)
        svg, h = panel(ref, x, y, room, prefix, crop, names)
        if not items:
            return out + [svg], y + h + 10
        parts, y = name_list(items, x, y + h + 56, room)
        return out + [svg] + parts, y

    return draw


def journal_bands(a: dict) -> list[tuple[str, int]]:
    return tree_bands("authors", a["sem"], 0, "sources")


def country_bands(a: dict) -> list[tuple[str, int]]:
    return tree_bands("authors", a["sem"], 1, "countries")


def journal_items(a: dict) -> list[tuple[str, str]]:
    papers_in = dict(a["journals"])
    return [
        (
            a["journal_names"].get(n, journal(n)),
            f"{commas(c)} citations · {plural(papers_in.get(n, 0), 'paper')}",
        )
        for n, c in journal_bands(a)[:8]
    ]


def country_items(a: dict) -> list[tuple[str, str]]:
    return [(n, f"{commas(c)} citation links") for n, c in country_bands(a)[:8]]


def laureate_sections(
    a: dict, spec: dict, marks: list[Mark]
) -> list[tuple[str, Section]]:
    sem, last = a["sem"], a["last"]
    js, cs = journal_bands(a), country_bands(a)

    def jname(raw: str) -> str:
        return a["journal_names"].get(raw, journal(raw))

    impact = f"authors/{sem}/impact" + (
        f"?hits={spec['impact']}" if spec.get("impact") else ""
    )
    built: dict[str, Section] = {
        "hits": hits_section,
        "papers": papers_section(spec.get("papers", {})),
        "timeline": timeline_section(timeline_opts(a, spec, marks), marks),
        "network": network_section(marks),
        "impact": card_section(
            f"Papers that build on {last}'s work",
            "",
            f"The highest-scoring hit papers that cite {last}, each joined to the papers "
            f"of {last} it builds on.",
            impact,
            "i-",
        ),
        "journals": card_section(
            f"Journals where {last} publishes",
            "bands sized by the citations those papers received",
            f"Papers in {jname(js[0][0])} drew {commas(js[0][1])} citations"
            + "".join(f", in {jname(n)} {commas(c)}" for n, c in js[1:3])
            + ".",
            f"authors/{sem}/tree?tree=1&since={SINCE_ALL}&isSpec=0",
            "j-",
            "tree",
            journal_items(a),
            a["journal_names"],
        ),
        "countries": card_section(
            f"Countries that cite {last}",
            "shaded by citations",
            "Citation links from papers with authors in "
            + "; ".join(f"{n}: {commas(c)}" for n, c in cs[:3])
            + ".",
            f"authors/{sem}/map",
            "c-",
            None,
            country_items(a),
        ),
    }
    first = "hits" if a["hits"] else "papers"
    default = [first, *(["timeline"] if "timeline" in spec else []), *SECTIONS[1:]]
    order = spec.get("order") or default
    out = [(k, built[k]) for k in order if k not in spec.get("skip", [])]
    for i, e in enumerate(spec.get("extra", [])):
        draw = card_section(
            e["title"],
            e.get("sub", ""),
            e["caption"],
            e["card"],
            f"e{i}-",
            e.get("crop"),
        )
        out.append((f"extra{i + 1}", draw))
    return out


def section_lists(a: dict, name: str, spec: dict, marks: list[Mark]) -> list[str]:
    """The lists a section draws, one item a line."""
    if name == "papers":
        return [
            f"{i}. {p['title']} | {paper_meta(p)} | {paper_team(p)}"
            for i, p in enumerate(listed_papers(a), 1)
        ]
    if name == "timeline":
        return [
            f"{a['team'][k]['name']} | {coauthor_span(a, k)}"
            for k, _ in timeline_rows(a, timeline_opts(a, spec, marks), marks)
        ]
    if name == "hits":
        return [
            f"{i}. {p['title']} | {hit_meta(p)}" for i, p in enumerate(a["hits"][:8], 1)
        ]
    if name == "network":
        return [f"{n} | {c} shared papers" for n, c in a["coauthors"][:8]]
    if name == "journals":
        return [f"{n} | {d}" for n, d in journal_items(a)]
    if name == "countries":
        return [f"{n} | {d}" for n, d in country_items(a)]
    return []


def laureate_stats(a: dict, spec: dict) -> list[tuple[str, str]]:
    if "stats" in spec:
        return [(value, label) for value, label in spec["stats"]]
    v = a["view"]
    return [
        *([(str(len(a["hits"])), "hit papers")] if a["hits"] else []),
        (commas(v["citations"]), "citations"),
        (commas(v["papers"]), "papers"),
    ]


def laureate_standfirst(a: dict, cfg: dict, spec: dict) -> str:
    v = a["view"]
    return spec.get("standfirst") or (
        f"{cfg['share_line']} In Rankless's index: {commas(v['papers'])} papers, "
        f"{commas(v['citations'])} citations, {len(a['hits'])} hit papers."
    )


def file_key(a: dict) -> str:
    return a["last"].lower()


def laureate_header(
    a: dict, cfg: dict, spec: dict, W: float, z: float
) -> tuple[Svg, float]:
    """The occasion, the name, the standfirst and three numbers across the top, `z` times the
    size they have over one column; with its bottom edge."""
    stats, standfirst = laureate_stats(a, spec), laureate_standfirst(a, cfg, spec)
    stats_w = 430 * z
    left = W - 2 * MARGIN - stats_w - 50 * z
    body = [
        strip(W, 18 * z),
        text(
            MARGIN, 150 * z, cfg["occasion"], 40 * z, "monob", "#5842a8", spacing=7 * z
        ),
    ]
    size = fit(a["name"], left, 300 * z, "serif")
    y = 200 * z + size * 0.84
    body.append(text(MARGIN - 8 * z, y, a["name"], size, "serif"))
    y += 40 * z
    for line in wrap(standfirst, left, 46 * z, "sans", 4):
        y += 62 * z
        body.append(text(MARGIN, y, line, 46 * z, "sans", MUTED))
    sx = W - MARGIN - stats_w
    body.append(vline(sx, 120 * z, max(y, 730 * z), HAIR, 2 * z))
    for i, (value, label) in enumerate(stats):
        cy, cx = (230 + i * 205) * z, sx + stats_w / 2 + 20 * z
        vsize = fit(value, stats_w - 60 * z, 104 * z, "serif")
        body.append(text(cx, cy, value, vsize, "serif", STAT_COLORS[i % 3], "middle"))
        lsize = fit(label, stats_w - 50 * z, 33 * z)
        body.append(text(cx, cy + 52 * z, label, lsize, "sans", MUTED, "middle"))
    return body, max(y, (230 + (len(stats) - 1) * 205 + 52) * z) + 70 * z


def deal(heights: list[float], k: int) -> list[list[int]]:
    """The sections dealt into `k` columns, each column keeping their order: the dealing with
    the shortest tallest column, the first section in the first column."""
    best: tuple[float, list[list[int]]] | None = None
    for cols in itertools.product(range(k), repeat=len(heights)):
        dealt = [[i for i, c in enumerate(cols) if c == j] for j in range(k)]
        tallest = max(sum(heights[i] for i in col) for col in dealt)
        if best is None or tallest < best[0]:
            best = (tallest, dealt)
    assert best is not None
    return best[1]


def laureate_infographic(a: dict, cfg: dict, spec: dict, out: Path) -> None:
    """One image per person: the header across the top and the sections below it in the
    number of columns that comes closest to a square."""
    key = file_key(a)
    marks = marks_of(a, cfg, spec)
    stats, standfirst = laureate_stats(a, spec), laureate_standfirst(a, cfg, spec)
    texts = [
        cfg["occasion"],
        a["name"],
        standfirst,
        *(f"{v} {lb}" for v, lb in stats),
        "",
    ]
    blocks: list[tuple[Section, float]] = []
    for name, draw in laureate_sections(a, spec, marks):
        COPY.clear()
        solo, end = draw(a, 60, 100, ROOM)
        write(out, f"{key}-{name}", ROOM + 120, end + 50, solo, png=False)
        texts += [*COPY, *section_lists(a, name, spec, marks), ""]
        blocks.append((draw, end + 70))
    heights = [h for _, h in blocks]

    def layout(k: int) -> tuple[float, float, list[list[int]]]:
        W = k * ROOM + (k - 1) * GUTTER + 2 * MARGIN
        _, top = laureate_header(a, cfg, spec, W, W / (ROOM + 2 * MARGIN))
        cols = deal(heights, k)
        H = (
            top
            + max(sum(heights[i] for i in c) for c in cols)
            + 330 * W / (ROOM + 2 * MARGIN)
        )
        return W, H, cols

    W, H, cols = min(
        (layout(k) for k in range(1, 4)), key=lambda g: abs(math.log(g[0] / g[1]))
    )
    z = W / (ROOM + 2 * MARGIN)
    body, top = laureate_header(a, cfg, spec, W, z)
    bottom = top
    for j, col in enumerate(cols):
        x, y = MARGIN + j * (ROOM + GUTTER), top
        for i in col:
            draw, h = blocks[i]
            body.append(hline(x, x + ROOM, y))
            body += draw(a, x, y + 110, ROOM)[0]
            y += h
        bottom = max(bottom, y)
        if j:
            body.append(vline(x - GUTTER / 2, top, bottom, HAIR, 2))
    body.append(hline(MARGIN, W - MARGIN, bottom))
    note = (
        "Citations are those Rankless indexes from OpenAlex, so they run below Google "
        f"Scholar's. {HIT_MEANING}"
    )
    y = bottom
    for line in wrap(note, W - 2 * MARGIN, 30 * z, "sans", 3):
        y += 46 * z
        body.append(text(MARGIN, y, line, 30 * z, "sans", FAINT))
    H = y + 230 * z
    body.append(footer(W, H, MARGIN, f"{MAIN_DOMAIN}/authors/{a['sem']}", 1.4 * z))
    write(out, f"{key}-infographic", W, H, body)
    (out / f"{key}.txt").write_text("\n".join(texts) + "\n")


# The joint image: named hit papers against the top bar.


def joint_papers(cfg: dict, authors: list[dict]) -> list[dict]:
    by_doi = {p["doi"]: p for a in authors for p in a["hits"]}
    who = {a["me"]: a["name"] for a in authors}
    colors = ["#7d0082", "#269ada", "#e1b01e", "#5842a8"]
    ps = sorted(
        (by_doi[d] for d in cfg["joint"]["papers"]), key=lambda p: -p["citations"]
    )
    return [
        {**p, "who": [who[x] for x in p["authors"] if x in who], "color": colors[i]}
        for i, p in enumerate(ps)
    ]


def joint_chart(
    ps: list[dict],
    left: float,
    right: float,
    top: float,
    bottom: float,
    label_size: float = 54,
    stroke: float = 13,
    bar_k: float = 1.0,
) -> Svg:
    x0 = min(p["year"] for p in ps)
    peak = max(p["citations"] for p in ps)
    step = next(s for s in (250, 500, 1000, 2500, 5000, 10000) if peak / s <= 5)
    ymax = math.ceil(peak / step) * step
    sx = year_scale(x0, left, right)

    def sy(v: float) -> float:
        return bottom - v / ymax * (bottom - top)

    out = value_grid(list(range(step, ymax + 1, step)), sy, left, right)
    for yr in [x0, *(y for y in range(x0 + (-x0) % 5, FINAL_YEAR, 5) if y - x0 > 2)]:
        out.append(vline(sx(yr), bottom, bottom + 12))
        out.append(text(sx(yr), bottom + 50, str(yr), 30, "mono", MUTED, "middle"))
    bar = sum(p["citations"] / p["multiple"] for p in ps) / len(ps)
    out.append(
        f'<line x1="{left}" x2="{right}" y1="{sy(bar):.1f}" y2="{sy(bar):.1f}" '
        f'stroke="{INK}" stroke-width="4" stroke-dasharray="4 14" stroke-linecap="round"/>'
    )
    label = f"TOP-{TOP} BAR"
    out.append(
        text(
            left + 16,
            sy(bar) - 62 * bar_k,
            label,
            30 * bar_k,
            "monob",
            INK,
            spacing=3 * bar_k,
        )
    )
    approx = f"≈ {round(bar / 50) * 50:,.0f} citations"
    out.append(text(left + 16, sy(bar) - 22 * bar_k, approx, 29 * bar_k, "sans", MUTED))
    for p in reversed(ps):
        pts = " ".join(
            f"{sx(p['year'] + i):.1f},{sy(c):.1f}" for i, c in enumerate(p["cum"])
        )
        out.append(
            f'<polyline points="{pts}" fill="none" stroke="{p["color"]}" '
            f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round"/>'
        )
        ex, ey = sx(FINAL_YEAR), sy(p["cum"][-1])
        out.append(
            f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="{stroke * 1.5:.1f}" fill="{p["color"]}"/>'
        )
        out.append(
            text(
                ex + 36,
                ey + label_size * 0.34,
                commas(p["citations"]),
                label_size,
                "monob",
                p["color"],
            )
        )
    return out


def joint_block(p: dict, x: float, y: float, room: float, k: float = 1.0) -> Svg:
    head = f"{p['year']} · {p['journal'].upper()}"
    out = [text(x, y + 30 * k, head, 27 * k, "monob", p["color"], spacing=2 * k)]
    mult = f"{p['multiple']:.1f}×"
    out.append(text(x - 4 * k, y + 130 * k, mult, 108 * k, "serif", p["color"]))
    bx = x + width(mult, 108 * k, "serif") + 22 * k
    out.append(text(bx, y + 92 * k, f"the top-{TOP} bar of", 31 * k, "sans", MUTED))
    out.append(text(bx, y + 130 * k, "its field and year", 31 * k, "sans", MUTED))
    lines = wrap(p["title"], room, 28 * k, "sans", 2)
    for i, line in enumerate(lines):
        out.append(text(x, y + (176 + 35 * i) * k, line, 28 * k, "sans", INK))
    who = " · ".join(p["who"])
    out.append(text(x, y + (176 + 35 * len(lines) + 3) * k, who, 26 * k, "sans", MUTED))
    return out


def joint_images(cfg: dict, authors: list[dict], out: Path) -> None:
    ps, j = joint_papers(cfg, authors), cfg["joint"]
    note = (
        f"Cumulative citations by year, as indexed by Rankless. Top-{TOP} bar: the "
        f"citations a paper of the same field and year needs to enter the top {TOP}."
    )
    W, H, M = 2400, 1350, 96
    body = [
        strip(W, 14),
        text(M, 112, cfg["occasion"], 32, "monob", "#5842a8", spacing=6),
    ]
    body.append(
        text(M - 6, 262, j["title"], fit(j["title"], W - 2 * M, 156, "serif"), "serif")
    )
    body.append(
        text(M, 334, j["subtitle"], fit(j["subtitle"], W - 2 * M, 41), "sans", MUTED)
    )
    body += joint_chart(ps, 200, 1400, 420, 1108)
    for i, line in enumerate(wrap(note, 1200, 24, "sans", 2)):
        body.append(text(200, 1196 + i * 31, line, 24, "sans", FAINT))
    for i, p in enumerate(ps):
        y = 388 + i * 290
        if i:
            body.append(hline(1700, W - M, y - 22))
        body += joint_block(p, 1700, y, W - M - 1700)
    body.append(footer(W, H, M, MAIN_DOMAIN))
    write(out, "joint-landscape", W, H, body)

    W, H, M = 2160, 2700, 108
    body = [
        strip(W, 18),
        text(M, 150, cfg["occasion"], 40, "monob", "#5842a8", spacing=7),
    ]
    for i, name in enumerate(j["title"].split(" · ")):
        body.append(text(M - 8, 360 + i * 196, name, 208, "serif"))
    for i, line in enumerate(wrap(j["subtitle"], W - 2 * M, 50, "sans", 3)):
        body.append(text(M, 880 + i * 66, line, 50, "sans", MUTED))
    body += joint_chart(ps, 250, 1700, 1080, 1900, label_size=72, stroke=17, bar_k=1.25)
    col = (W - 2 * M - 2 * 54) / 3
    for i, p in enumerate(ps):
        body += joint_block(p, M + i * (col + 54), 2060, col, 1.22)
    for i, line in enumerate(wrap(note, W - 2 * M, 30, "sans", 2)):
        body.append(text(M, 2452 + i * 40, line, 30, "sans", FAINT))
    body.append(footer(W, H, M, MAIN_DOMAIN, 1.35))
    write(out, "joint-portrait", W, H, body)


# What a human looks at before anything is posted.


def checklist(a: dict) -> None:
    v = a["view"]
    orcid = v.get("meta", {}).get("orcid") or "none"
    print(
        f"\n== {a['name']}  ({a['sem']})  {v['papers']} papers, "
        f"{commas(v['citations'])} citations, {len(a['hits'])} hit papers, papers from "
        f"{a['years'][0]} to {a['years'][1]}, ORCID {orcid}"
    )
    same = [
        (r["semanticId"], r["papers"], r["citations"])
        for r in get("/names/authors", q=a["record"])
        if r["semanticId"] != a["sem"] and r["name"].split()[-1] == a["last"]
    ]
    print("  other records under the name:", same[:6] or "none")
    print("  top co-authors:", ", ".join(f"{n} ({c})" for n, c in a["coauthors"][:14]))
    print(
        "  journals by papers:", ", ".join(f"{n} ({c})" for n, c in a["journals"][:10])
    )
    fields = v["relations"]["paper-fields"]
    print(
        "  fields of the papers:",
        ", ".join(f"{r['name']} ({r['score']})" for r in fields),
    )
    print("  hit papers:")
    for p in a["hits"][:8]:
        print(
            f"    {p['year']} {p['citations']:>6} {p['multiple']:.1f}x  "
            f"{p['title'][:90]}  [{p['journal']}]"
        )


# The page the figures are shown on.

_STAMP = re.compile(r"^data_version: .*$", re.M)


def page_skeleton(cfg: dict, authors: list[dict], version: str) -> str:
    """A story page showing every figure, with only text the figures already carry."""
    names = listed([a["name"] for a in authors], most=len(authors))
    lines = [
        "---",
        f"title: {json.dumps(names, ensure_ascii=False)}",
        f"date: {date.today()}",
        f"occasion: {json.dumps(cfg['occasion'], ensure_ascii=False)}",
        f"data_version: {json.dumps(version)}",
        "---",
        "",
    ]
    if "joint" in cfg:
        j = cfg["joint"]
        lines += [
            j["subtitle"],
            "",
            f"![{j['title']}](figures/joint-landscape.png)",
            "",
        ]
    for spec, a in zip(cfg["laureates"], authors):
        img = f"figures/{file_key(a)}-infographic"
        profile = f"https://{MAIN_DOMAIN}/authors/{a['sem']}"
        lines += [
            f"## {a['name']}",
            "",
            laureate_standfirst(a, cfg, spec),
            "",
            f"[![{a['name']} on Rankless]({img}.png)]({img}.png)",
            "",
            f"[{a['name']} on Rankless]({profile}) · [SVG]({img}.svg) · "
            f"[all text](figures/{file_key(a)}.txt)",
            "",
        ]
    return "\n".join(lines)


def page_version(page: Path) -> str | None:
    m = _STAMP.search(page.read_text()) if page.exists() else None
    return json.loads(m.group(0).split(": ", 1)[1]) if m else None


def stamp_page(page: Path, cfg: dict, authors: list[dict], version: str) -> None:
    if not page.exists():
        page.write_text(page_skeleton(cfg, authors, version))
        print(page)
        return
    s, n = _STAMP.subn(
        f"data_version: {json.dumps(version)}", page.read_text(), count=1
    )
    if n != 1:
        raise SystemExit(f"{page} has no data_version line to stamp")
    page.write_text(s)


def main(prize: str, *only: str, check: bool = False, backend: str = "live") -> None:
    """Infographics for the laureates of a prize file (`only`: those ids, or `joint`)."""
    global BE
    BE = resolve_backend(backend)[0]
    source = Path(prize)
    cfg = json.loads(source.read_text())
    authors = {s["id"]: author(s) for s in cfg["laureates"]}
    if check:
        for a in authors.values():
            checklist(a)
        return
    page, out = source.parent / "index.md", source.parent / "figures"
    version = get("/specs")["version"]
    if only and page_version(page) not in (None, version):
        raise SystemExit(
            f"{page} shows figures from {page_version(page)}, the backend serves "
            f"{version}: draw every laureate"
        )
    out.mkdir(parents=True, exist_ok=True)
    if "joint" in cfg and (not only or "joint" in only):
        joint_images(cfg, list(authors.values()), out)
    for spec in cfg["laureates"]:
        if not only or spec["id"] in only:
            a = authors[spec["id"]]
            fellows = [f for f in authors.values() if f is not a]
            laureate_infographic(a, {**cfg, "fellows": fellows}, spec, out)
    stamp_page(page, cfg, list(authors.values()), version)
