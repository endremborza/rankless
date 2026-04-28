import json
import re
from urllib.parse import urlsplit

import pandas as pd

# --- UA family bucketing -------------------------------------------------

_UA_BOT_RE = re.compile(
    r"bot|crawl|slurp|spider|mediapartners|facebookexternalhit|whatsapp|telegram|"
    r"python-(?:requests|urllib)|curl|wget|Go-http-client|java/|okhttp|"
    r"Apache-HttpClient|libwww|AhrefsBot|SemrushBot|MJ12bot|GPTBot|ClaudeBot|"
    r"Bytespider|PerplexityBot|YandexBot|Bingbot|Googlebot|DuckDuckBot",
    re.IGNORECASE,
)

_UA_BROWSER_RE = re.compile(r"Chrome|Safari|Firefox|Edge|Opera|Vivaldi", re.IGNORECASE)

_UA_FAMILY_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"GPTBot", re.I), "gptbot"),
    (re.compile(r"ClaudeBot", re.I), "claudebot"),
    (re.compile(r"PerplexityBot", re.I), "perplexitybot"),
    (re.compile(r"Bytespider", re.I), "bytespider"),
    (re.compile(r"Googlebot", re.I), "googlebot"),
    (re.compile(r"Bingbot", re.I), "bingbot"),
    (re.compile(r"AhrefsBot", re.I), "ahrefsbot"),
    (re.compile(r"SemrushBot", re.I), "semrushbot"),
    (re.compile(r"MJ12bot", re.I), "mj12bot"),
    (re.compile(r"DuckDuckBot", re.I), "duckduckbot"),
    (re.compile(r"YandexBot", re.I), "yandexbot"),
    (re.compile(r"facebookexternalhit", re.I), "facebookbot"),
    (re.compile(r"whatsapp", re.I), "whatsapp"),
    (re.compile(r"telegram", re.I), "telegrambot"),
    (re.compile(r"python-(?:requests|urllib)", re.I), "python-script"),
    (re.compile(r"\bcurl\b", re.I), "curl"),
    (re.compile(r"\bwget\b", re.I), "wget"),
    (re.compile(r"Go-http-client", re.I), "go-script"),
    (re.compile(r"okhttp|Apache-HttpClient|java/", re.I), "java-script"),
    (re.compile(r"libwww", re.I), "libwww"),
    (re.compile(r"\bbot\b|crawler|spider|slurp|mediapartners", re.I), "other-bot"),
    (re.compile(r"Edg/", re.I), "edge"),
    (re.compile(r"Chrome/.*Mobile", re.I), "chrome-mobile"),
    (re.compile(r"Chrome/", re.I), "chrome"),
    (re.compile(r"Firefox/", re.I), "firefox"),
    (re.compile(r"Safari/.*Version/", re.I), "safari"),
    (re.compile(r"Safari/", re.I), "safari-webkit"),
    (re.compile(r"Opera|OPR/", re.I), "opera"),
]


def ua_family(ua: str) -> str:
    if not ua:
        return "empty"
    for rx, name in _UA_FAMILY_PATTERNS:
        if rx.search(ua):
            return name
    return "unknown"


def is_bot_ua(ua: str) -> bool:
    return bool(_UA_BOT_RE.search(ua or ""))


def is_browser_ua(ua: str) -> bool:
    if not ua:
        return False
    return bool(_UA_BROWSER_RE.search(ua)) and "Mozilla" in ua


# --- Referrer ------------------------------------------------------------


def referrer_domain(ref: str) -> str:
    if not ref or ref == "-":
        return ""
    try:
        host = urlsplit(ref).netloc.lower()
    except ValueError:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


# --- Session classification ---------------------------------------------

# Rule outputs: bot_known, bot_likely, human_known, human_likely, unknown.

# Hard-human routes (any hit → human_known).
_HARD_HUMAN_POST_ROUTES = {
    "/api/papers/claim",
    "/api/papers/disown",
    "/api/papers/merge",
    "/api/authors/merge-request",
}
_HARD_HUMAN_GET_ROUTES = {"/callback"}
_SEARCH_ROUTE = "/v1/names/{etype}"
_HTML_PAGE_ROUTES = {
    "/",
    "/{rootType}",
    "/{rootType}/table",
    "/{rootType}/{...semanticId}",
    "/about",
    "/login",
    "/survey",
}
_BROWSER_ASSET_ROUTES = {"/tiles/{...}", "/pic/{...}", "/pathlogo/{...}", "/_app/{...}"}

# Hard-bot routes.
_HARD_BOT_ROUTES = {"/robots.txt", "/sitemap*.xml"}


def classify_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """One row per session_id with bot_class + signals_json. Requires session_id, route_template, ua, method, t, status, cs."""
    if df.empty:
        return pd.DataFrame(
            columns=[
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
        )

    df = df.copy()
    df["_is_search"] = (df["route_template"] == _SEARCH_ROUTE) & df["path"].str.contains(
        r"\?q=.+", regex=True, na=False
    )
    df["_is_html_page"] = df["route_template"].isin(_HTML_PAGE_ROUTES)
    df["_is_browser_asset"] = df["route_template"].isin(_BROWSER_ASSET_ROUTES)

    rows = []
    for sid, g in df.groupby("session_id", sort=False):
        rows.append(_classify_one(sid, g))
    return pd.DataFrame(rows)


def _classify_one(sid: str, g: pd.DataFrame) -> dict:
    ua = g["ua"].iloc[0] if "ua" in g.columns else ""
    addr = g["addr"].iloc[0] if "addr" in g.columns else ""
    n_req = len(g)
    routes = g["route_template"].unique().tolist()
    diversity = len(routes)
    start = g["t"].min()
    end = g["t"].max()
    span = (end - start).total_seconds()

    signals: list[str] = []
    score = 0
    bot_class = "unknown"

    # --- hard-bot signals ---
    if not ua or ua in {"-", ""}:
        signals.append("hard:empty_ua")
        bot_class = "bot_known"
    if is_bot_ua(ua):
        signals.append(f"hard:bot_ua={ua_family(ua)}")
        bot_class = "bot_known"
    if any(r in _HARD_BOT_ROUTES for r in routes):
        signals.append("hard:robots_or_sitemap")
        if bot_class == "unknown":
            bot_class = "bot_known"
    if (g["method"] == "HEAD").all():
        signals.append("hard:all_HEAD")
        if bot_class == "unknown":
            bot_class = "bot_known"

    # --- hard-human signals (override bot only if not already bot_known) ---
    posts = g[g["method"].isin(["POST", "PUT", "DELETE"])]
    if posts["route_template"].isin(_HARD_HUMAN_POST_ROUTES).any():
        signals.append("hard:ledger_action")
        if bot_class != "bot_known":
            bot_class = "human_known"
    if g["route_template"].isin(_HARD_HUMAN_GET_ROUTES).any() and g["path"].str.contains(
        "code=", na=False
    ).any():
        signals.append("hard:orcid_callback")
        if bot_class != "bot_known":
            bot_class = "human_known"
    if g["_is_search"].any():
        signals.append("hard:search_used")
        if bot_class != "bot_known":
            bot_class = "human_known"
    if g["_is_html_page"].any() and g["_is_browser_asset"].any():
        signals.append("hard:browser_asset_loaded")
        if bot_class == "unknown":
            bot_class = "human_known"

    if bot_class != "unknown":
        return _row(sid, addr, ua, start, end, n_req, diversity, bot_class, signals)

    # --- soft signals: score-based ---
    if is_browser_ua(ua):
        signals.append("soft:+2 browser_ua")
        score += 2
    elif ua and "Mozilla" in ua and not _UA_BROWSER_RE.search(ua):
        signals.append("soft:-2 mozilla_only")
        score -= 2
    if g["referrer"].fillna("").ne("").any():
        signals.append("soft:+1 referrer_present")
        score += 1
    if diversity >= 3:
        signals.append(f"soft:+1 route_diversity={diversity}")
        score += 1
    if n_req >= 20 and span <= 30:
        signals.append(f"soft:-2 burst_{n_req}_in_{int(span)}s")
        score -= 2
    hours = g["t"].dt.hour.unique()
    if len(hours) <= 12:
        signals.append("soft:+1 diurnal_window")
        score += 1
    elif len(hours) >= 20:
        signals.append("soft:-1 flat_24h")
        score -= 1
    cs_hits = (g["cs"] == "HIT").sum() if "cs" in g.columns else 0
    if (
        cs_hits / max(n_req, 1) > 0.9
        and not g["_is_browser_asset"].any()
        and n_req >= 5
    ):
        signals.append("soft:-1 cache_only_no_assets")
        score -= 1

    if score >= 3:
        bot_class = "human_likely"
    elif score <= -3:
        bot_class = "bot_likely"
    else:
        bot_class = "unknown"

    return _row(sid, addr, ua, start, end, n_req, diversity, bot_class, signals + [f"soft:score={score}"])


def _row(sid, addr, ua, start, end, n, diversity, cls, signals):
    return {
        "session_id": sid,
        "addr": addr,
        "ua": ua,
        "ua_family": ua_family(ua),
        "start": start,
        "end": end,
        "n_req": n,
        "route_diversity": diversity,
        "bot_class": cls,
        "signals_json": json.dumps(signals),
    }


def annotate_events(df: pd.DataFrame, sessions: pd.DataFrame) -> pd.DataFrame:
    """Add ua_family, bot_class, referrer_domain to event rows by joining the sessions table."""
    if df.empty:
        for c in ("ua_family", "bot_class", "referrer_domain"):
            df[c] = pd.Series([], dtype="object")
        return df
    df = df.copy()
    df["ua_family"] = df["ua"].map(ua_family)
    df["referrer_domain"] = df["referrer"].map(referrer_domain)
    sess_map = sessions.set_index("session_id")["bot_class"].to_dict()
    df["bot_class"] = df["session_id"].map(sess_map).fillna("unknown")
    return df
