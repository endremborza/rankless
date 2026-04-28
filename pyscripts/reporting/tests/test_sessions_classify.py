import shutil
import tempfile
from pathlib import Path

import pandas as pd

from pyscripts.reporting import archive, config
from pyscripts.reporting.archive import annotate_routes
from pyscripts.reporting.classify import (
    annotate_events,
    classify_sessions,
    is_bot_ua,
    is_browser_ua,
    referrer_domain,
    ua_family,
)
from pyscripts.reporting.parse import parse_lines
from pyscripts.reporting.sessions import assign_sessions

from .fixtures import ALL


def _setup_tmp_root() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="reports-v2-test-"))
    config.REPORTS_ROOT = tmp
    config.SALTS_PATH = tmp / "salts.json"
    config.STATE_PATH = tmp / "state.json"
    from pyscripts.reporting import state as state_mod
    state_mod.SALTS_PATH = config.SALTS_PATH
    state_mod.STATE_PATH = config.STATE_PATH
    return tmp


def test_ua_family_buckets():
    assert ua_family("") == "empty"
    assert ua_family("Mozilla/5.0 ... Chrome/124.0") == "chrome"
    assert ua_family("Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)") == "gptbot"
    assert ua_family("AhrefsBot/7.0") == "ahrefsbot"
    assert ua_family("python-requests/2.31.0") == "python-script"
    assert ua_family("Mozilla/5.0 ... Firefox/124.0") == "firefox"


def test_is_bot_ua():
    assert is_bot_ua("AhrefsBot/7.0")
    assert is_bot_ua("Mozilla/5.0 (compatible; GPTBot/1.0)")
    assert is_bot_ua("python-requests/2.31.0")
    assert not is_bot_ua("Mozilla/5.0 ... Chrome/124.0")


def test_is_browser_ua():
    assert is_browser_ua("Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0")
    assert is_browser_ua("Mozilla/5.0 (Macintosh) Safari/605.1.15")
    assert not is_browser_ua("AhrefsBot/7.0")
    assert not is_browser_ua("")


def test_referrer_domain():
    assert referrer_domain("https://www.google.com/search?q=x") == "google.com"
    assert referrer_domain("https://twitter.com/foo") == "twitter.com"
    assert referrer_domain("-") == ""
    assert referrer_domain("") == ""


def test_assign_sessions_basic():
    tmp = _setup_tmp_root()
    try:
        df, _ = parse_lines(ALL)
        df = assign_sessions(df)
        assert "session_id" in df.columns
        assert df["session_id"].notna().all()
        # Different (addr, ua) → different sessions
        assert df["session_id"].nunique() == df.groupby(["addr", "ua"]).ngroups
    finally:
        shutil.rmtree(tmp)


def test_assign_sessions_idle_split():
    tmp = _setup_tmp_root()
    try:
        # Two requests from same (addr, ua), 60min apart → 2 sessions
        ts = pd.to_datetime(
            ["2026-04-28T10:00:00Z", "2026-04-28T11:30:00Z"], utc=True
        )
        df = pd.DataFrame(
            {
                "t": ts,
                "addr": ["1.2.3.4", "1.2.3.4"],
                "ua": ["Chrome", "Chrome"],
                "method": ["GET", "GET"],
                "path": ["/", "/"],
                "status": [200, 200],
                "size": [100, 100],
                "referrer": ["", ""],
                "rt": [0.1, 0.1],
                "uct": [0.01, 0.01],
                "uht": [0.01, 0.01],
                "urt": [0.05, 0.05],
                "cs": ["HIT", "HIT"],
            }
        )
        df = assign_sessions(df)
        assert df["session_id"].nunique() == 2
    finally:
        shutil.rmtree(tmp)


def test_classify_known_bot_ua():
    tmp = _setup_tmp_root()
    try:
        df, _ = parse_lines(ALL)
        df = annotate_routes(df)
        df = assign_sessions(df)
        sessions = classify_sessions(df)
        # GPTBot session
        gpt = sessions[sessions["ua"].str.contains("GPTBot", na=False)]
        assert (gpt["bot_class"] == "bot_known").all()
        # AhrefsBot hits robots.txt — also bot_known
        ahrefs = sessions[sessions["ua"].str.contains("AhrefsBot", na=False)]
        assert (ahrefs["bot_class"] == "bot_known").all()
        # python-requests is bot
        py = sessions[sessions["ua"].str.contains("python-requests", na=False)]
        assert (py["bot_class"] == "bot_known").all()
    finally:
        shutil.rmtree(tmp)


def test_classify_search_user_human_known():
    tmp = _setup_tmp_root()
    try:
        df, _ = parse_lines(ALL)
        df = annotate_routes(df)
        df = assign_sessions(df)
        sessions = classify_sessions(df)
        # Chrome session that hit /v1/names/authors?q=darwin → human_known
        chrome = sessions[
            sessions["ua"].str.contains("Chrome/124", na=False)
        ]
        assert (chrome["bot_class"] == "human_known").all()
    finally:
        shutil.rmtree(tmp)


def test_classify_empty_ua_is_bot():
    tmp = _setup_tmp_root()
    try:
        df, _ = parse_lines(ALL)
        df = annotate_routes(df)
        df = assign_sessions(df)
        sessions = classify_sessions(df)
        empty = sessions[sessions["ua"] == ""]
        assert (empty["bot_class"] == "bot_known").all()
    finally:
        shutil.rmtree(tmp)


def test_annotate_events_adds_columns():
    tmp = _setup_tmp_root()
    try:
        df, _ = parse_lines(ALL)
        df = annotate_routes(df)
        df = assign_sessions(df)
        sessions = classify_sessions(df)
        annotated = annotate_events(df, sessions)
        for c in ("ua_family", "bot_class", "referrer_domain"):
            assert c in annotated.columns
        assert (annotated["bot_class"] != "unknown").any()
    finally:
        shutil.rmtree(tmp)
