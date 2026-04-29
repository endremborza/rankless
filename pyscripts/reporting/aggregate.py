import datetime as dt
import os
from pathlib import Path

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
    prepared = df.assign(
        bucket=df["t"].dt.floor(freq),
        status_family=_status_family(df["status"]),
        cs=df["cs"].fillna("").replace("", "-"),
        bot_class=df["bot_class"].fillna("unknown"),
    )
    grouped = prepared.groupby(GROUP_KEYS, dropna=False, observed=True)
    base = grouped.agg(
        n=("status", "count"),
        bytes=("size", "sum"),
        urt_mean=("urt", "mean"),
    ).reset_index()
    qs = (
        grouped["urt"]
        .quantile([0.5, 0.95, 0.99, 0.999])
        .unstack(-1)
        .rename(columns={0.5: "urt_p50", 0.95: "urt_p95", 0.99: "urt_p99", 0.999: "urt_p999"})
        .reset_index()
    )
    return base.merge(qs, on=GROUP_KEYS, how="left")


def _fill_missing_cols(df: pd.DataFrame) -> None:
    for col in ("bot_class", "cs"):
        if col not in df.columns:
            df[col] = "unknown" if col == "bot_class" else "-"
    if "route_template" not in df.columns:
        df["route_template"] = "_unknown"


def rebuild() -> dict[str, int]:
    """Recompute hourly + daily aggregates from all hot + cold archives."""
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
    _fill_missing_cols(df)
    hourly = _agg_block(df, "h")
    daily = _agg_block(df, "D")
    _write(hourly, HOURLY_PATH)
    _write(daily, DAILY_PATH)
    return {"rows": int(len(df)), "hourly_rows": int(len(hourly)), "daily_rows": int(len(daily))}


def update(affected_dates: list[dt.date]) -> dict[str, int]:
    """Incrementally update aggregates for the given dates only.

    Reads only the hot-archive files for affected_dates, drops their existing
    aggregate rows, and re-aggregates. Cold archives are untouched (they are
    only ever affected by dates old enough that they won't appear in affected_dates).
    """
    if not affected_dates:
        return {"rows": 0, "updated_dates": 0}

    AGGREGATES_DIR.mkdir(parents=True, exist_ok=True)
    affected_set = set(affected_dates)

    parts = [
        day_df
        for d in affected_dates
        if not (day_df := archive.read_hot(date_from=d, date_to=d)).empty
    ]
    new_df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if not new_df.empty:
        _fill_missing_cols(new_df)

    def _update_one(path: Path, freq: str) -> pd.DataFrame:
        if path.exists():
            existing = pd.read_parquet(path)
            mask = pd.to_datetime(existing["bucket"]).dt.date.isin(affected_set)
            existing = existing[~mask]
        else:
            existing = pd.DataFrame()
        if new_df.empty:
            return existing
        new_agg = _agg_block(new_df, freq)
        if existing.empty:
            return new_agg
        return (
            pd.concat([existing, new_agg], ignore_index=True)
            .sort_values("bucket")
            .reset_index(drop=True)
        )

    hourly = _update_one(HOURLY_PATH, "h")
    daily = _update_one(DAILY_PATH, "D")
    _write(hourly, HOURLY_PATH)
    _write(daily, DAILY_PATH)
    return {
        "rows": int(len(new_df)),
        "updated_dates": len(affected_dates),
        "hourly_rows": int(len(hourly)),
        "daily_rows": int(len(daily)),
    }


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
    os.replace(tmp, path)
