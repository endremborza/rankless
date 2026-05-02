import datetime as dt

import polars as pl
from shackleton import TableRepo

from . import archive
from .config import AGGREGATES_DIR


GROUP_KEYS = ["bucket", "route_template", "status_family", "bot_class", "cs"]


def _hourly_repo() -> TableRepo:
    return TableRepo(AGGREGATES_DIR / "hourly", compression="zstd")


def _daily_repo() -> TableRepo:
    return TableRepo(AGGREGATES_DIR / "daily", compression="zstd")


def _sessions_repo() -> TableRepo:
    return TableRepo(AGGREGATES_DIR / "sessions", compression="zstd")


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
    if not parts:
        _hourly_repo().purge()
        _daily_repo().purge()
        return {"rows": 0}
    df = _fill_missing_cols(pl.concat(parts, how="diagonal"))
    hourly = _agg_block(df, "1h")
    daily = _agg_block(df, "1d")
    _hourly_repo().replace_all(hourly)
    _daily_repo().replace_all(daily)
    return {"rows": len(df), "hourly_rows": len(hourly), "daily_rows": len(daily)}


def update(affected_dates: list[dt.date]) -> dict[str, int]:
    if not affected_dates:
        return {"rows": 0, "updated_dates": 0}

    affected_set = set(affected_dates)

    parts = [
        day_df
        for d in affected_dates
        if not (day_df := archive.read_hot(date_from=d, date_to=d)).is_empty()
    ]
    new_df = (
        _fill_missing_cols(pl.concat(parts, how="diagonal"))
        if parts
        else pl.DataFrame()
    )

    def _update_one(repo: TableRepo, every: str) -> pl.DataFrame:
        existing = repo.get_full_df()
        if not existing.is_empty():
            existing = existing.filter(
                ~pl.col("bucket").dt.date().is_in(list(affected_set))
            )
        if new_df.is_empty():
            return existing
        new_agg = _agg_block(new_df, every)
        if existing.is_empty():
            return new_agg
        return pl.concat([existing, new_agg], how="diagonal").sort("bucket")

    hourly = _update_one(_hourly_repo(), "1h")
    daily = _update_one(_daily_repo(), "1d")
    _hourly_repo().replace_all(hourly)
    _daily_repo().replace_all(daily)
    return {
        "rows": len(new_df),
        "updated_dates": len(affected_dates),
        "hourly_rows": len(hourly),
        "daily_rows": len(daily),
    }


def load_hourly() -> pl.DataFrame:
    return _hourly_repo().get_full_df()


def load_daily() -> pl.DataFrame:
    return _daily_repo().get_full_df()


def write_sessions(sessions: pl.DataFrame) -> None:
    _sessions_repo().replace_all(sessions)


def load_sessions() -> pl.DataFrame:
    return _sessions_repo().get_full_df()


def hourly_exists() -> bool:
    return _hourly_repo().n_files > 0
