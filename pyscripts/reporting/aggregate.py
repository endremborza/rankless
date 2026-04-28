import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from . import archive
from .config import AGGREGATES_DIR


HOURLY_PATH = AGGREGATES_DIR / "hourly.parquet"
DAILY_PATH = AGGREGATES_DIR / "daily.parquet"
SESSIONS_PATH = AGGREGATES_DIR / "sessions.parquet"

GROUP_KEYS = ["bucket", "route_template", "status_family", "bot_class", "cs"]


def _status_family(status: pd.Series) -> pd.Series:
    return (status // 100).astype("uint8").astype(str) + "xx"


def _agg_block(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    bucket = df["t"].dt.floor(freq)
    g = df.assign(
        bucket=bucket,
        status_family=_status_family(df["status"]),
        cs=df["cs"].fillna("").replace("", "-"),
        bot_class=df["bot_class"].fillna("unknown"),
    )
    grouped = g.groupby(GROUP_KEYS, dropna=False, observed=True)
    out = grouped.agg(
        n=("status", "count"),
        bytes=("size", "sum"),
        urt_mean=("urt", "mean"),
        urt_p50=("urt", lambda s: float(np.nanpercentile(s, 50)) if s.notna().any() else float("nan")),
        urt_p95=("urt", lambda s: float(np.nanpercentile(s, 95)) if s.notna().any() else float("nan")),
        urt_p99=("urt", lambda s: float(np.nanpercentile(s, 99)) if s.notna().any() else float("nan")),
        urt_p999=("urt", lambda s: float(np.nanpercentile(s, 99.9)) if s.notna().any() else float("nan")),
    ).reset_index()
    return out


def rebuild(today: dt.date | None = None) -> dict[str, int]:
    """Recompute hourly + daily aggregates from hot+cold archives."""
    parts = []
    hot = archive.read_hot()
    if not hot.empty:
        parts.append(hot)
    cold = archive.read_cold()
    if not cold.empty:
        parts.append(cold)
    AGGREGATES_DIR.mkdir(parents=True, exist_ok=True)
    if not parts:
        for p in (HOURLY_PATH, DAILY_PATH):
            if p.exists():
                p.unlink()
        return {"rows": 0}
    df = pd.concat(parts, ignore_index=True)

    # Cold rows lack `path`/`ua`/`referrer` but have all aggregation keys.
    for col in ("bot_class", "cs"):
        if col not in df.columns:
            df[col] = "unknown" if col == "bot_class" else "-"
    if "route_template" not in df.columns:
        df["route_template"] = "_unknown"

    hourly = _agg_block(df, "h")
    daily = _agg_block(df, "D")
    _write(hourly, HOURLY_PATH)
    _write(daily, DAILY_PATH)
    return {"rows": int(len(df)), "hourly_rows": int(len(hourly)), "daily_rows": int(len(daily))}


def load_hourly() -> pd.DataFrame:
    return pd.read_parquet(HOURLY_PATH) if HOURLY_PATH.exists() else pd.DataFrame()


def load_daily() -> pd.DataFrame:
    return pd.read_parquet(DAILY_PATH) if DAILY_PATH.exists() else pd.DataFrame()


def write_sessions(sessions: pd.DataFrame) -> None:
    AGGREGATES_DIR.mkdir(parents=True, exist_ok=True)
    _write(sessions, SESSIONS_PATH)


def load_sessions() -> pd.DataFrame:
    return pd.read_parquet(SESSIONS_PATH) if SESSIONS_PATH.exists() else pd.DataFrame()


def _write(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, engine="pyarrow", compression="zstd", compression_level=9, index=False)
    import os
    os.replace(tmp, path)
