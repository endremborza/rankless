import datetime as dt
import os
from pathlib import Path

import pandas as pd

from .config import ARCHIVE_COLD_DIR, ARCHIVE_DIR, COLD_AFTER_DAYS
from .paths import template

# Columns retained in cold archive. `path`, `ua`, `referrer` raw text are dropped;
# their derived buckets (`route_template`, `ua_family`, `bot_class`, `referrer_domain`)
# must be present before a day can be compacted to cold.
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


def annotate_routes(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        df["route_template"] = pd.Series([], dtype="object")
        return df
    df = df.copy()
    df["route_template"] = df["path"].map(template)
    return df


def write_events(df: pd.DataFrame) -> dict[str, int]:
    """Append events to per-day parquet files, deduped. Returns counts per date."""
    if df.empty:
        return {}
    if "route_template" not in df.columns:
        df = annotate_routes(df)
    df = df.assign(_d=df["t"].dt.tz_convert("UTC").dt.date)
    written: dict[str, int] = {}
    for d, day_df in df.groupby("_d", sort=False):
        day_df = day_df.drop(columns="_d")
        path = _hot_path(d)
        path.parent.mkdir(parents=True, exist_ok=True)
        prev_n = 0
        if path.exists():
            existing = pd.read_parquet(path)
            prev_n = len(existing)
            combined = pd.concat([existing, day_df], ignore_index=True)
        else:
            combined = day_df
        combined = (
            combined.drop_duplicates(
                subset=["t", "addr", "path", "status", "size", "ua"]
            )
            .sort_values("t")
            .reset_index(drop=True)
        )
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


def read_hot(date_from: dt.date | None = None, date_to: dt.date | None = None) -> pd.DataFrame:
    parts = []
    for d in list_hot_dates():
        if date_from and d < date_from:
            continue
        if date_to and d > date_to:
            continue
        parts.append(pd.read_parquet(_hot_path(d)))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def read_cold(date_from: dt.date | None = None, date_to: dt.date | None = None) -> pd.DataFrame:
    parts = []
    for y, m in list_cold_months():
        if date_from and (y, m) < (date_from.year, date_from.month):
            continue
        if date_to and (y, m) > (date_to.year, date_to.month):
            continue
        parts.append(pd.read_parquet(_cold_path(y, m)))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


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
        existing_cold = pd.read_parquet(cold_path) if cold_path.exists() else None
        day_frames = []
        missing_cols = []
        for d in dates:
            day = pd.read_parquet(_hot_path(d))
            if not all(c in day.columns for c in COLD_COLUMNS):
                missing_cols.append(d.isoformat())
                continue
            day_frames.append(day[COLD_COLUMNS])
        if missing_cols:
            # Skip the whole month so we don't lose data we can't recover.
            result[f"{y}-{m:02d}-skipped"] = len(missing_cols)
            continue
        if not day_frames:
            continue
        combined = (
            pd.concat([*([existing_cold] if existing_cold is not None else []), *day_frames])
            .sort_values("t")
            .reset_index(drop=True)
        )
        cold_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_parquet_write(combined, cold_path, compression="zstd", level=22, dictionary=True)
        for d in dates:
            _hot_path(d).unlink()
        result[f"{y}-{m:02d}"] = len(day_frames)
    return result


def _hot_path(d: dt.date) -> Path:
    return ARCHIVE_DIR / f"{d.year:04d}" / f"{d.month:02d}" / f"{d.isoformat()}.parquet"


def _cold_path(year: int, month: int) -> Path:
    return ARCHIVE_COLD_DIR / f"{year:04d}" / f"{month:02d}.parquet"


def _atomic_parquet_write(
    df: pd.DataFrame,
    path: Path,
    *,
    compression: str = "zstd",
    level: int = 3,
    dictionary: bool = False,
) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    extra = {"use_dictionary": True} if dictionary else {}
    df.to_parquet(
        tmp,
        engine="pyarrow",
        compression=compression,
        compression_level=level,
        index=False,
        **extra,
    )
    os.replace(tmp, path)
