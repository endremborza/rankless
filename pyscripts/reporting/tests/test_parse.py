import math

import pandas as pd

from pyscripts.reporting.parse import parse_lines

from .fixtures import (
    ALL,
    LINE_429,
    LINE_EMPTY_UA,
    LINE_GARBAGE,
    LINE_NO_UPSTREAM,
    LINE_POST_CS_BOT,
    LINE_POST_CS_HUMAN,
    LINE_PRE_CS,
)


def test_parse_post_cs_human():
    df, fail = parse_lines([LINE_POST_CS_HUMAN])
    assert fail == 0
    r = df.iloc[0]
    assert r["addr"] == "203.0.113.42"
    assert r["method"] == "GET"
    assert r["path"] == "/v1/names/authors?q=darwin"
    assert r["status"] == 200
    assert r["size"] == 4321
    assert r["cs"] == "MISS"
    assert "Chrome" in r["ua"]
    assert r["referrer"] == "https://www.rankless.org/"
    assert math.isclose(r["urt"], 0.040, rel_tol=1e-3)


def test_parse_post_cs_bot():
    df, fail = parse_lines([LINE_POST_CS_BOT])
    assert fail == 0
    assert df.iloc[0]["path"] == "/sitemap.xml"
    assert "GPTBot" in df.iloc[0]["ua"]
    assert df.iloc[0]["cs"] == "HIT"


def test_parse_pre_cs_compat():
    df, fail = parse_lines([LINE_PRE_CS])
    assert fail == 0
    assert df.iloc[0]["cs"] == ""
    assert df.iloc[0]["path"] == "/institutions/harvard"


def test_parse_no_upstream():
    df, fail = parse_lines([LINE_NO_UPSTREAM])
    assert fail == 0
    r = df.iloc[0]
    assert math.isnan(r["urt"])
    assert math.isnan(r["uct"])
    assert r["cs"] == "BYPASS"


def test_parse_429():
    df, _ = parse_lines([LINE_429])
    assert df.iloc[0]["status"] == 429
    assert df.iloc[0]["size"] == 0


def test_parse_empty_ua_referrer():
    df, _ = parse_lines([LINE_EMPTY_UA])
    r = df.iloc[0]
    assert r["ua"] == ""
    assert r["referrer"] == ""


def test_parse_garbage_counted():
    df, fail = parse_lines([LINE_GARBAGE])
    assert fail == 1
    assert len(df) == 0


def test_parse_batch():
    df, fail = parse_lines([*ALL, LINE_GARBAGE, ""])
    assert fail == 1
    assert len(df) == len(ALL)
    assert pd.api.types.is_datetime64tz_dtype(df["t"])
