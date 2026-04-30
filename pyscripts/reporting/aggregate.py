import datetime as dt
import os
from pathlib import Path

import polars as pl

from . import archive
from .config import AGGREGATES_DIR


HOURLY_PATH = AGGREGATES_DIR / "hourly.parquet"
DAILY_PATH = AGGREGATES_DIR / "daily.parquet"
SESSIONS_PATH = AGGREGATES_DIR / "sessions.parquet"

GROUP_KEYS = ["bucket", "route_template", "status_family", "bot_class", "cs"]


def _agg_block(df: pl.DataFrame, every: str) -> pl.DataFrame:
    prepared = df.with_columns(
        [
            pl.col("t").dt.truncate(every).alias("bucket"),
            ((pl.col("status").cast(pl.Int32) // 100).cast(pl.String) + "xx").alias(
                "status_family"
            ),
            pl.col("cs")
            .fill_null("")
            .map_elements(lambda s: "-" if s == "" else s, return_dtype=pl.String),
            pl.col("bot_class").fill_null("unknown"),
        ]
    )
    return (
        prepared.group_by(GROUP_KEYS)
        .agg(
            [
                pl.len().alias("n"),
                pl.col("size").sum().alias("bytes"),
                pl.col("urt").mean().alias("urt_mean"),
                pl.col("urt").quantile(0.5).alias("urt_p50"),
                pl.col("urt").quantile(0.95).alias("urt_p95"),
                pl.col("urt").quantile(0.99).alias("urt_p99"),
                pl.col("urt").quantile(0.999).alias("urt_p999"),
            ]
        )
        .sort("bucket")
    )


def _fill_missing_cols(df: pl.DataFrame) -> pl.DataFrame:
    adds = []
    if "bot_class" not in df.columns:
        adds.append(pl.lit("unknown").alias("bot_class"))
    if "cs" not in df.columns:
        adds.append(pl.lit("-").alias("cs"))
    if "route_template" not in df.columns:
        adds.append(pl.lit("_unknown").alias("route_template"))
    return df.with_columns(adds) if adds else df


def rebuild() -> dict[str, int]:
    parts = []
    hot = archive.read_hot()
    if not hot.is_empty():
        parts.append(hot)
    cold = archive.read_cold()
    if not cold.is_empty():
        parts.append(cold)
    AGGREGATES_DIR.mkdir(parents=True, exist_ok=True)
    if not parts:
        for p in (HOURLY_PATH, DAILY_PATH):
            if p.exists():
                p.unlink()
        return {"rows": 0}
    df = _fill_missing_cols(pl.concat(parts))
    hourly = _agg_block(df, "1h")
    daily = _agg_block(df, "1d")
    _write(hourly, HOURLY_PATH)
    _write(daily, DAILY_PATH)
    return {"rows": len(df), "hourly_rows": len(hourly), "daily_rows": len(daily)}


def update(affected_dates: list[dt.date]) -> dict[str, int]:
    if not affected_dates:
        return {"rows": 0, "updated_dates": 0}

    AGGREGATES_DIR.mkdir(parents=True, exist_ok=True)
    affected_set = set(affected_dates)

    parts = [
        day_df
        for d in affected_dates
        if not (day_df := archive.read_hot(date_from=d, date_to=d)).is_empty()
    ]
    new_df = _fill_missing_cols(pl.concat(parts)) if parts else pl.DataFrame()

    def _update_one(path: Path, every: str) -> pl.DataFrame:
        if path.exists():
            existing = pl.read_parquet(path)
            existing = existing.filter(
                ~pl.col("bucket").dt.date().is_in(list(affected_set))
            )
        else:
            existing = pl.DataFrame()
        if new_df.is_empty():
            return existing
        new_agg = _agg_block(new_df, every)
        if existing.is_empty():
            return new_agg
        return pl.concat([existing, archive.cast_to_match(new_agg, existing)]).sort(
            "bucket"
        )

    hourly = _update_one(HOURLY_PATH, "1h")
    daily = _update_one(DAILY_PATH, "1d")
    _write(hourly, HOURLY_PATH)
    _write(daily, DAILY_PATH)
    return {
        "rows": len(new_df),
        "updated_dates": len(affected_dates),
        "hourly_rows": len(hourly),
        "daily_rows": len(daily),
    }


def load_hourly() -> pl.DataFrame:
    return pl.read_parquet(HOURLY_PATH) if HOURLY_PATH.exists() else pl.DataFrame()


def load_daily() -> pl.DataFrame:
    return pl.read_parquet(DAILY_PATH) if DAILY_PATH.exists() else pl.DataFrame()


def write_sessions(sessions: pl.DataFrame) -> None:
    AGGREGATES_DIR.mkdir(parents=True, exist_ok=True)
    _write(sessions, SESSIONS_PATH)


def load_sessions() -> pl.DataFrame:
    return pl.read_parquet(SESSIONS_PATH) if SESSIONS_PATH.exists() else pl.DataFrame()


def _write(df: pl.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.write_parquet(tmp, compression="zstd", compression_level=9)
    os.replace(tmp, path)
