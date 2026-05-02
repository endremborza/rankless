"""Bot/human session classification.

Public surface (also used by the explainer page):
- `BotClass` constants and ordered classes.
- `UA_FAMILIES`, `HARD_RULES`, `SOFT_RULES` — introspectable rule data.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlsplit

import polars as pl


# --- bot-class labels ----------------------------------------------------


class BotClass:
    BOT_KNOWN = "bot_known"
    BOT_LIKELY = "bot_likely"
    UNKNOWN = "unknown"
    HUMAN_LIKELY = "human_likely"
    HUMAN_KNOWN = "human_known"


# Ordered most-bot → most-human (matches the visual stacking & legend).
BOT_CLASS_ORDER: list[str] = [
    BotClass.BOT_KNOWN,
    BotClass.BOT_LIKELY,
    BotClass.UNKNOWN,
    BotClass.HUMAN_LIKELY,
    BotClass.HUMAN_KNOWN,
]
HUMAN_CLASSES: set[str] = {BotClass.HUMAN_KNOWN, BotClass.HUMAN_LIKELY}
BOT_CLASSES: set[str] = {BotClass.BOT_KNOWN, BotClass.BOT_LIKELY}

BOT_CLASS_COLORS: dict[str, str] = {
    BotClass.BOT_KNOWN: "#f38ba8",
    BotClass.BOT_LIKELY: "#eba0ac",
    BotClass.UNKNOWN: "#9399b2",
    BotClass.HUMAN_LIKELY: "#94e2d5",
    BotClass.HUMAN_KNOWN: "#a6e3a1",
}


# --- UA family bucketing -------------------------------------------------


@dataclass(frozen=True)
class UAFamily:
    name: str
    pattern: re.Pattern
    is_bot: bool


def _rx(s: str) -> re.Pattern:
    return re.compile(s, re.IGNORECASE)


UA_FAMILIES: list[UAFamily] = [
    UAFamily("gptbot", _rx(r"GPTBot"), True),
    UAFamily("claudebot", _rx(r"ClaudeBot"), True),
    UAFamily("perplexitybot", _rx(r"PerplexityBot"), True),
    UAFamily("bytespider", _rx(r"Bytespider"), True),
    UAFamily("googlebot", _rx(r"Googlebot"), True),
    UAFamily("bingbot", _rx(r"Bingbot"), True),
    UAFamily("ahrefsbot", _rx(r"AhrefsBot"), True),
    UAFamily("semrushbot", _rx(r"SemrushBot"), True),
    UAFamily("mj12bot", _rx(r"MJ12bot"), True),
    UAFamily("duckduckbot", _rx(r"DuckDuckBot"), True),
    UAFamily("yandexbot", _rx(r"YandexBot"), True),
    UAFamily("facebookbot", _rx(r"facebookexternalhit"), True),
    UAFamily("whatsapp", _rx(r"whatsapp"), True),
    UAFamily("telegrambot", _rx(r"telegram"), True),
    UAFamily("python-script", _rx(r"python-(?:requests|urllib)"), True),
    UAFamily("curl", _rx(r"\bcurl\b"), True),
    UAFamily("wget", _rx(r"\bwget\b"), True),
    UAFamily("go-script", _rx(r"Go-http-client"), True),
    UAFamily("java-script", _rx(r"okhttp|Apache-HttpClient|java/"), True),
    UAFamily("libwww", _rx(r"libwww"), True),
    UAFamily("other-bot", _rx(r"\bbot\b|crawler|spider|slurp|mediapartners"), True),
    UAFamily("edge", _rx(r"Edg/"), False),
    UAFamily("chrome-mobile", _rx(r"Chrome/.*Mobile"), False),
    UAFamily("chrome", _rx(r"Chrome/"), False),
    UAFamily("firefox", _rx(r"Firefox/"), False),
    UAFamily("safari", _rx(r"Safari/.*Version/"), False),
    UAFamily("safari-webkit", _rx(r"Safari/"), False),
    UAFamily("opera", _rx(r"Opera|OPR/"), False),
]

_UA_BROWSER_RE = re.compile(r"Chrome|Safari|Firefox|Edge|Opera|Vivaldi", re.IGNORECASE)


def ua_family(ua: str) -> str:
    if not ua:
        return "empty"
    for fam in UA_FAMILIES:
        if fam.pattern.search(ua):
            return fam.name
    return "unknown"


def is_bot_ua(ua: str) -> bool:
    if not ua:
        return False
    return any(fam.is_bot and fam.pattern.search(ua) for fam in UA_FAMILIES)


def is_browser_ua(ua: str) -> bool:
    if not ua:
        return False
    return bool(_UA_BROWSER_RE.search(ua)) and "Mozilla" in ua


# --- referrer ------------------------------------------------------------


def referrer_domain(ref: str) -> str:
    if not ref or ref == "-":
        return ""
    try:
        host = urlsplit(ref).netloc.lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


# --- route categories ---------------------------------------------------

ROUTE_HARD_HUMAN_POST = {
    "/api/papers/claim",
    "/api/papers/disown",
    "/api/papers/merge",
    "/api/authors/merge-request",
}
ROUTE_HARD_HUMAN_GET = {"/callback"}
ROUTE_SEARCH = "/v1/names/{etype}"
ROUTE_HTML_PAGES = {
    "/",
    "/{rootType}",
    "/{rootType}/table",
    "/{rootType}/{...semanticId}",
    "/about",
    "/login",
    "/survey",
}
ROUTE_BROWSER_ASSETS = {"/tiles/{...}", "/pic/{...}", "/pathlogo/{...}", "/_app/{...}"}
ROUTE_HARD_BOT = {"/robots.txt", "/sitemap*.xml"}
ROUTE_SVELTEKIT_DATA = {
    "/__data.json",
    "/{rootType}/__data.json",
    "/{rootType}/table/__data.json",
    "/{rootType}/{semanticId}/__data.json",
}

WRITE_METHODS = ("POST", "PUT", "DELETE")


# --- rule data structures -----------------------------------------------


@dataclass
class _Ctx:
    g: pl.DataFrame
    ua: str
    routes: set[str]
    methods: set[str]
    n: int
    span_s: float
    is_search: pl.Series
    is_html: pl.Series
    is_asset: pl.Series
    is_data: pl.Series


@dataclass(frozen=True)
class HardRule:
    name: str
    side: str  # "bot" or "human"
    description: str
    fn: Callable[[_Ctx], bool]


@dataclass(frozen=True)
class SoftRule:
    name: str
    score: int
    description: str
    fn: Callable[[_Ctx], bool]


HARD_RULES: list[HardRule] = [
    HardRule(
        "empty_ua",
        "bot",
        "User-Agent header missing or empty.",
        lambda c: not c.ua,
    ),
    HardRule(
        "bot_ua",
        "bot",
        "User-Agent matches a known bot/crawler/script family.",
        lambda c: is_bot_ua(c.ua),
    ),
    HardRule(
        "robots_or_sitemap",
        "bot",
        f"Hit one of the bot-only routes: {sorted(ROUTE_HARD_BOT)}.",
        lambda c: bool(c.routes & ROUTE_HARD_BOT),
    ),
    HardRule(
        "all_HEAD",
        "bot",
        "Every request in the session uses the HEAD method.",
        lambda c: c.methods == {"HEAD"},
    ),
    HardRule(
        "ledger_action",
        "human",
        f"Authenticated write to a ledger endpoint ({sorted(ROUTE_HARD_HUMAN_POST)}).",
        lambda c: (
            c.g["method"].is_in(list(WRITE_METHODS)).any()
            and c.g.filter(pl.col("method").is_in(list(WRITE_METHODS)))[
                "route_template"
            ]
            .is_in(list(ROUTE_HARD_HUMAN_POST))
            .any()
        ),
    ),
    HardRule(
        "orcid_callback",
        "human",
        f"Hit {sorted(ROUTE_HARD_HUMAN_GET)} carrying an OAuth `code=` param.",
        lambda c: (
            c.g["route_template"].is_in(list(ROUTE_HARD_HUMAN_GET)).any()
            and c.g["path"].str.contains("code=").any()
        ),
    ),
    HardRule(
        "search_used",
        "human",
        f"Used the search endpoint `{ROUTE_SEARCH}` with a non-empty `q=` param.",
        lambda c: bool(c.is_search.any()),
    ),
    HardRule(
        "browser_asset_loaded",
        "human",
        "Loaded an HTML page and at least one browser-only asset (tiles/pic/etc.).",
        lambda c: bool(c.is_html.any() and c.is_asset.any()),
    ),
    HardRule(
        "sveltekit_prefetch",
        "human",
        "Session contains SvelteKit __data.json requests, indicating browser hover-prefetch activity.",
        lambda c: bool(c.is_data.any()),
    ),
]


SOFT_RULES: list[SoftRule] = [
    SoftRule(
        "browser_ua",
        +2,
        "User-Agent looks like a real browser (`Mozilla` + Chrome/Safari/Firefox/etc.).",
        lambda c: is_browser_ua(c.ua),
    ),
    SoftRule(
        "mozilla_only",
        -2,
        "User-Agent claims `Mozilla` but lacks any real browser token.",
        lambda c: bool(c.ua) and "Mozilla" in c.ua and not _UA_BROWSER_RE.search(c.ua),
    ),
    SoftRule(
        "referrer_present",
        +1,
        "At least one request carries a non-empty Referer.",
        lambda c: c.g["referrer"].fill_null("").ne("").any(),
    ),
    SoftRule(
        "route_diversity",
        +1,
        "Touched 3 or more distinct route templates.",
        lambda c: len(c.routes) >= 3,
    ),
    SoftRule(
        "burst",
        -2,
        "20+ requests inside a 30-second window (machine-paced).",
        lambda c: c.n >= 20 and c.span_s <= 30,
    ),
    SoftRule(
        "diurnal_window",
        +1,
        "Active across at most 12 distinct hours-of-day (looks human-bound).",
        lambda c: len(c.g["t"].dt.hour().unique()) <= 12,
    ),
    SoftRule(
        "flat_24h",
        -1,
        "Active across 20+ distinct hours-of-day (no diurnal pause).",
        lambda c: len(c.g["t"].dt.hour().unique()) >= 20,
    ),
    SoftRule(
        "cache_only_no_assets",
        -1,
        ">90% cache hits, 5+ requests, never loaded a browser asset.",
        lambda c: (
            c.n >= 5
            and "cs" in c.g.columns
            and (c.g["cs"] == "HIT").sum() / max(c.n, 1) > 0.9
            and not c.is_asset.any()
        ),
    ),
    SoftRule(
        "html_no_prefetch",
        -2,
        "Visited 5+ HTML pages but triggered no SvelteKit prefetch (no hover activity).",
        lambda c: c.is_html.sum() >= 5 and not c.is_data.any(),
    ),
    SoftRule(
        "high_rate_same_route",
        -2,
        "10+ requests to the same route template within 60 seconds (machine-paced crawl).",
        lambda c: _has_high_rate(c.g),
    ),
    SoftRule(
        "www_no_api",
        -2,
        "At least one request to the frontend domain with zero api.rankless.org (/v1/) calls.",
        lambda c: c.n >= 1 and not any(rt.startswith("/v1/") for rt in c.routes),
    ),
]

SOFT_HUMAN_THRESHOLD = 4
SOFT_BOT_THRESHOLD = -3


# --- session classification ---------------------------------------------

_SESSION_OUT_COLS = [
    "session_id",
    "addr",
    "ua",
    "ua_family",
    "start",
    "end",
    "n_req",
    "route_diversity",
    "bot_class",
    "signals_json",
]


def classify_sessions(df: pl.DataFrame) -> pl.DataFrame:
    """One row per session_id with bot_class + signals_json. Requires session_id, route_template, ua, method, t, status, cs."""
    if df.is_empty():
        return pl.DataFrame(
            {col: pl.Series([], dtype=pl.String) for col in _SESSION_OUT_COLS}
        )

    enriched = df.with_columns(
        [
            (
                (pl.col("route_template") == ROUTE_SEARCH)
                & pl.col("path").str.contains(r"\?q=.+")
            ).alias("_is_search"),
            pl.col("route_template").is_in(list(ROUTE_HTML_PAGES)).alias("_is_html"),
            pl.col("route_template")
            .is_in(list(ROUTE_BROWSER_ASSETS))
            .alias("_is_asset"),
            pl.col("route_template")
            .is_in(list(ROUTE_SVELTEKIT_DATA))
            .alias("_is_data"),
        ]
    )

    rows = [
        _classify_one(sid, g)
        for sid, g in (
            (part["session_id"][0], part)
            for part in enriched.partition_by("session_id", maintain_order=False)
        )
    ]
    return pl.DataFrame(
        rows,
        schema={
            "session_id": pl.String,
            "addr": pl.String,
            "ua": pl.String,
            "ua_family": pl.String,
            "start": pl.Datetime("us", "UTC"),
            "end": pl.Datetime("us", "UTC"),
            "n_req": pl.Int64,
            "route_diversity": pl.Int64,
            "bot_class": pl.String,
            "signals_json": pl.String,
        },
    )


def _has_high_rate(g: pl.DataFrame, min_count: int = 10, window_s: int = 60) -> bool:
    thresh_us = window_s * 1_000_000

    out = (
        g.sort(["route_template", "t"])
        .with_columns(
            span=pl.col("t").shift(-(min_count - 1)).over("route_template")
            - pl.col("t")
        )
        .filter(pl.col("span").is_not_null())
        .group_by("route_template")
        .agg((pl.col("span") < thresh_us).any().alias("has_burst"))
    )

    return out["has_burst"].any()


def _make_ctx(g: pl.DataFrame) -> _Ctx:
    start = g["t"].min()
    end = g["t"].max()
    span_s = (end - start).total_seconds() if start and end else 0.0
    return _Ctx(
        g=g,
        ua=g["ua"][0] if "ua" in g.columns else "",
        routes=set(g["route_template"].unique().to_list()),
        methods=set(g["method"].unique().to_list()),
        n=len(g),
        span_s=span_s,
        is_search=g["_is_search"],
        is_html=g["_is_html"],
        is_asset=g["_is_asset"],
        is_data=g["_is_data"],
    )


def _apply_hard(ctx: _Ctx, signals: list[str]) -> str | None:
    bot_hit = False
    human_hit = False
    for rule in HARD_RULES:
        try:
            fired = bool(rule.fn(ctx))
        except Exception:
            fired = False
        if not fired:
            continue
        signals.append(f"hard:{rule.name}")
        if rule.side == "bot":
            bot_hit = True
        else:
            human_hit = True
    if bot_hit:
        return BotClass.BOT_KNOWN
    if human_hit:
        return BotClass.HUMAN_KNOWN
    return None


def _apply_soft(ctx: _Ctx, signals: list[str]) -> str:
    score = 0
    for rule in SOFT_RULES:
        if rule.fn(ctx):
            signals.append(
                f"soft:{'+' if rule.score > 0 else ''}{rule.score} {rule.name}"
            )
            score += rule.score
    signals.append(f"soft:score={score}")
    if score >= SOFT_HUMAN_THRESHOLD:
        return BotClass.HUMAN_LIKELY
    if score <= SOFT_BOT_THRESHOLD:
        return BotClass.BOT_LIKELY
    return BotClass.UNKNOWN


def _classify_one(sid: str, g: pl.DataFrame) -> dict:
    ctx = _make_ctx(g)
    signals: list[str] = []
    bot_class = _apply_hard(ctx, signals) or _apply_soft(ctx, signals)
    addr = g["addr"][0] if "addr" in g.columns else ""
    return {
        "session_id": sid,
        "addr": addr,
        "ua": ctx.ua,
        "ua_family": ua_family(ctx.ua),
        "start": g["t"].min(),
        "end": g["t"].max(),
        "n_req": ctx.n,
        "route_diversity": len(ctx.routes),
        "bot_class": bot_class,
        "signals_json": json.dumps(signals),
    }


def annotate_events(df: pl.DataFrame, sessions: pl.DataFrame) -> pl.DataFrame:
    """Add ua_family, bot_class, referrer_domain to event rows by joining the sessions table."""
    if df.is_empty():
        return df.with_columns(
            [
                pl.lit(None).cast(pl.String).alias("ua_family"),
                pl.lit(None).cast(pl.String).alias("bot_class"),
                pl.lit(None).cast(pl.String).alias("referrer_domain"),
            ]
        )

    sess_map = dict(
        zip(sessions["session_id"].to_list(), sessions["bot_class"].to_list())
    )

    return df.with_columns(
        [
            pl.col("ua")
            .map_elements(ua_family, return_dtype=pl.String)
            .alias("ua_family"),
            pl.col("referrer")
            .map_elements(referrer_domain, return_dtype=pl.String)
            .alias("referrer_domain"),
            pl.col("session_id")
            .map_elements(
                lambda sid: sess_map.get(sid, BotClass.UNKNOWN), return_dtype=pl.String
            )
            .alias("bot_class"),
        ]
    )
