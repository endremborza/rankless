import pandas as pd

from pyscripts import stress

PAGE_HOST, BE_HOST = "alpha.rankless.org", "alpha-api.rankless.org"
UA = stress.CAPACITY_UA


def _row(conc: int, t0: float, rps: float, err: float = 0.0) -> dict:
    return {
        "conc": conc,
        "total": conc * 2,
        "t0": t0,
        "t1": t0 + 10,
        "rps": rps,
        "p50_ms": 300,
        "err_pct": err,
    }


def _log_df(entries: list[tuple[float, str, int, float | None, str, str]]):
    cols = ["t", "host", "code", "urt", "agent", "cs"]
    df = pd.DataFrame(dict(zip(cols, map(list, zip(*entries)))))
    return df.assign(t=pd.to_datetime(df["t"], unit="s", utc=True))


def test_merge_log_windows_splits_ua_and_hosts():
    rows = [_row(1, 100.0, 10.0), _row(2, 120.0, 18.0)]
    df = _log_df(
        [(101.0, PAGE_HOST, 200, 0.2, UA, "BYPASS")] * 100  # ours, level 1
        + [(102.0, PAGE_HOST, 200, 0.8, "GoogleBot", "MISS")] * 20  # external
        + [(125.0, PAGE_HOST, 200, 0.4, UA, "HIT")] * 50  # ours, level 2, HIT!
        + [(126.0, BE_HOST, 200, 0.05, "bun", "MISS")] * 40  # SSR fetches
        + [(126.5, BE_HOST, 200, None, "bun", "HIT")] * 10  # cached: urt='-'
        + [(127.0, PAGE_HOST, 502, 1.0, "GoogleBot", "MISS")] * 3
        + [(128.0, PAGE_HOST, 429, None, "bun", "MISS")]
        + [(150.0, PAGE_HOST, 500, 1.0, UA, "MISS")] * 9  # outside both windows
    )
    stress.merge_log_windows(df, rows, PAGE_HOST, BE_HOST, UA)
    assert rows[0]["log_rps"] == 12.0 and rows[0]["ext_rps"] == 2.0
    assert rows[0]["urt_p50_ms"] == 200  # ours only, not the bot's 800ms
    assert rows[0]["log_5xx"] == 0 and rows[0]["be_rps"] == 0.0
    assert rows[1]["be_rps"] == 5.0 and rows[1]["be_p50_ms"] == 50  # NaN urt skipped
    assert rows[1]["log_5xx"] == 3 and rows[1]["log_429"] == 1
    assert rows[1]["our_hits"] == 50  # cache bypass broken -> flagged


def test_yardsticks_onsets_use_urt():
    rows = [
        {"conc": 1, "urt_p50_ms": 200, "p50_ms": 999, "err_pct": 0.0, "log_5xx": 0},
        {"conc": 2, "urt_p50_ms": 290, "p50_ms": 999, "err_pct": 0.0, "log_5xx": 0},
        {"conc": 4, "urt_p50_ms": 310, "p50_ms": 999, "err_pct": 0.0, "log_5xx": 0},
        {"conc": 8, "urt_p50_ms": 700, "p50_ms": 999, "err_pct": 0.0, "log_5xx": 2},
    ]
    degrade, first_err, key = stress.yardsticks(rows)
    assert key == "urt_p50_ms"
    assert degrade is not None and degrade["conc"] == 4  # 310 > 1.5x200; 290 is not
    assert first_err is not None and first_err["conc"] == 8


def test_yardsticks_client_fallback_and_not_reached():
    rows = [
        {"conc": 1, "urt_p50_ms": None, "p50_ms": 200, "err_pct": 0.0, "log_5xx": 0},
        {"conc": 2, "urt_p50_ms": None, "p50_ms": 250, "err_pct": 0.0, "log_5xx": 0},
    ]
    degrade, first_err, key = stress.yardsticks(rows)
    assert key == "p50_ms"
    assert degrade is None and first_err is None
