import datetime as dt
import os
from pathlib import Path

import polars as pl

from .config import ARCHIVE_COLD_DIR, ARCHIVE_DIR, COLD_AFTER_DAYS
from .paths import template

COLD_COLUMNS = [
    "t",
    "addr",
    "method",
    "route_template",
    "status",
    "size",
    "rt",
    "urt",
    "uht",
    "uct",
    "cs",
    "session_id",
    "ua_family",
    "bot_class",
    "referrer_domain",
]


def annotate_routes(df: pl.DataFrame) -> pl.DataFrame:
    if df.is_empty():
        return df.with_columns(pl.lit(None).cast(pl.String).alias("route_template"))
    return df.with_columns(
        pl.col("path")
        .map_elements(template, return_dtype=pl.String)
        .alias("route_template")
    )


def cast_to_match(df: pl.DataFrame, target: pl.DataFrame) -> pl.DataFrame:
    target_schema = target.schema

    casts = []
    for col, target_dtype in target_schema.items():
        if col in df.columns:
            if df.schema[col] != target_dtype:
                casts.append(pl.col(col).cast(target_dtype))
        else:
            # optional: add missing columns as nulls
            casts.append(pl.lit(None).cast(target_dtype).alias(col))

    return df.with_columns(casts).select(target.columns)


def write_events(df: pl.DataFrame) -> dict[str, int]:
    """Append events to per-day parquet files, deduped. Returns counts per date."""
    if df.is_empty():
        return {}
    if "route_template" not in df.columns:
        df = annotate_routes(df)
    df = df.with_columns(pl.col("t").dt.convert_time_zone("UTC").dt.date().alias("_d"))
    written: dict[str, int] = {}
    for day_df in df.partition_by("_d", maintain_order=False):
        d = day_df["_d"][0]
        day_df = day_df.drop("_d")
        path = _hot_path(d)
        path.parent.mkdir(parents=True, exist_ok=True)
        prev_n = 0
        if path.exists():
            existing = pl.read_parquet(path)
            prev_n = len(existing)
            combined = pl.concat([existing, cast_to_match(day_df, existing)])
        else:
            combined = day_df
        combined = combined.unique(
            subset=["t", "addr", "path", "status", "size", "ua"]
        ).sort("t")
        _atomic_parquet_write(combined, path, compression="zstd", level=3)
        written[d.isoformat()] = len(combined) - prev_n
    return written


def list_hot_dates() -> list[dt.date]:
    out = []
    for year_dir in sorted(ARCHIVE_DIR.glob("[0-9]" * 4)):
        for month_dir in sorted(year_dir.glob("[0-9]" * 2)):
            for f in sorted(month_dir.glob("*.parquet")):
                try:
                    out.append(dt.date.fromisoformat(f.stem))
                except ValueError:
                    continue
    return out


def list_cold_months() -> list[tuple[int, int]]:
    out = []
    for year_dir in sorted(ARCHIVE_COLD_DIR.glob("[0-9]" * 4)):
        for f in sorted(year_dir.glob("*.parquet")):
            try:
                out.append((int(year_dir.name), int(f.stem)))
            except ValueError:
                continue
    return out


def read_hot(
    date_from: dt.date | None = None, date_to: dt.date | None = None
) -> pl.DataFrame:
    parts = []
    for d in list_hot_dates():
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        parts.append(pl.read_parquet(_hot_path(d)))
    return pl.concat(parts) if parts else pl.DataFrame()


def read_cold(
    date_from: dt.date | None = None, date_to: dt.date | None = None
) -> pl.DataFrame:
    parts = []
    for y, m in list_cold_months():
        if date_from and (y, m) < (date_from.year, date_from.month):
            continue
        if date_to and (y, m) > (date_to.year, date_to.month):
            continue
        parts.append(pl.read_parquet(_cold_path(y, m)))
    return pl.concat(parts) if parts else pl.DataFrame()


def compress_cold(today: dt.date) -> dict[str, int]:
    """Move per-day files older than COLD_AFTER_DAYS into per-month cold parquet."""
    cutoff = today - dt.timedelta(days=COLD_AFTER_DAYS)
    by_month: dict[tuple[int, int], list[dt.date]] = {}
    for d in list_hot_dates():
        if d >= cutoff:
            continue
        by_month.setdefault((d.year, d.month), []).append(d)
    result = {}
    for (y, m), dates in by_month.items():
        cold_path = _cold_path(y, m)
        existing_cold = pl.read_parquet(cold_path) if cold_path.exists() else None
        day_frames = []
        missing_cols = []
        for d in dates:
            day = pl.read_parquet(_hot_path(d))
            if not all(c in day.columns for c in COLD_COLUMNS):
                missing_cols.append(d.isoformat())
                continue
            day_frames.append(day.select(COLD_COLUMNS))
        if missing_cols:
            result[f"{y}-{m:02d}-skipped"] = len(missing_cols)
            continue
        if not day_frames:
            continue
        parts = ([existing_cold] if existing_cold is not None else []) + day_frames
        combined = pl.concat(parts).sort("t")
        cold_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_parquet_write(combined, cold_path, compression="zstd", level=22)
        for d in dates:
            _hot_path(d).unlink()
        result[f"{y}-{m:02d}"] = len(day_frames)
    return result


def rewrite_hot(d: dt.date, df: pl.DataFrame) -> None:
    _atomic_parquet_write(df, _hot_path(d), compression="zstd", level=3)


def _hot_path(d: dt.date) -> Path:
    return ARCHIVE_DIR / f"{d.year:04d}" / f"{d.month:02d}" / f"{d.isoformat()}.parquet"


def _cold_path(year: int, month: int) -> Path:
    return ARCHIVE_COLD_DIR / f"{year:04d}" / f"{month:02d}.parquet"


def _atomic_parquet_write(
    df: pl.DataFrame,
    path: Path,
    *,
    compression: str = "zstd",
    level: int = 3,
) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.write_parquet(tmp, compression=compression, compression_level=level)
    os.replace(tmp, path)
