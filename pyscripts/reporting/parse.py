import datetime as dt
from typing import Iterable

import polars as pl

from .config import LINE_RE, LOG_TIME_FMT


def _f(s: str | None) -> float:
    if s is None or s == "" or s == "-":
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def parse_lines(lines: Iterable[str]) -> tuple[pl.DataFrame, int]:
    """Return (df, n_failures). Drops empty lines silently."""
    rows = []
    failures = 0
    for line in lines:
        line = line.rstrip("\n")
        if not line:
            continue
        m = LINE_RE.match(line)
        if not m:
            failures += 1
            continue
        rows.append(m.groupdict())
    if not rows:
        return _empty_df(), failures

    raw = pl.DataFrame(rows)
    df = raw.with_columns([
        pl.col("time").str.strptime(pl.Datetime("us", "UTC"), LOG_TIME_FMT).alias("t"),
        pl.col("status").cast(pl.UInt16),
        pl.col("size").cast(pl.UInt32),
        pl.col("rt").map_elements(_f, return_dtype=pl.Float32),
        pl.col("uct").map_elements(_f, return_dtype=pl.Float32),
        pl.col("uht").map_elements(_f, return_dtype=pl.Float32),
        pl.col("urt").map_elements(_f, return_dtype=pl.Float32),
        pl.when(pl.col("referrer") == "-").then(pl.lit("")).otherwise(pl.col("referrer")).alias("referrer"),
        pl.when(pl.col("ua") == "-").then(pl.lit("")).otherwise(pl.col("ua")).alias("ua"),
        pl.col("cs").fill_null("").map_elements(lambda s: "" if s == "-" else s, return_dtype=pl.String),
    ]).drop("time").select([
        "t", "addr", "method", "path", "status", "size",
        "referrer", "ua", "rt", "uct", "uht", "urt", "cs",
    ])
    return df, failures


def _empty_df() -> pl.DataFrame:
    return pl.DataFrame({
        "t": pl.Series([], dtype=pl.Datetime("us", "UTC")),
        "addr": pl.Series([], dtype=pl.String),
        "method": pl.Series([], dtype=pl.String),
        "path": pl.Series([], dtype=pl.String),
        "status": pl.Series([], dtype=pl.UInt16),
        "size": pl.Series([], dtype=pl.UInt32),
        "referrer": pl.Series([], dtype=pl.String),
        "ua": pl.Series([], dtype=pl.String),
        "rt": pl.Series([], dtype=pl.Float32),
        "uct": pl.Series([], dtype=pl.Float32),
        "uht": pl.Series([], dtype=pl.Float32),
        "urt": pl.Series([], dtype=pl.Float32),
        "cs": pl.Series([], dtype=pl.String),
    })
