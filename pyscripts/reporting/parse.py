from typing import Iterable

import polars as pl

from .config import ALPHA_HOST_PREFIX, LINE_RE, LOG_TIME_FMT


def _f(s: str | None) -> float | None:
    if s is None or s == "" or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


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
    df = (
        raw.with_columns(
            [
                # non-strict: a torn/interleaved line can carry junk in the time
                # bracket (e.g. a client IP spliced in). Parse it to null and drop
                # the row below rather than raising — a raise would abort the whole
                # batch and echo the offending raw values (IPs) into the run log.
                pl.col("time")
                .str.strptime(pl.Datetime("us", "UTC"), LOG_TIME_FMT, strict=False)
                .alias("t"),
                pl.col("status").cast(pl.UInt16),
                pl.col("size").cast(pl.UInt32, strict=False),
                pl.col("rt").map_elements(_f, return_dtype=pl.Float32),
                pl.col("uct").map_elements(_f, return_dtype=pl.Float32),
                pl.col("uht").map_elements(_f, return_dtype=pl.Float32),
                pl.col("urt").map_elements(_f, return_dtype=pl.Float32),
                pl.when(pl.col("referrer") == "-")
                .then(pl.lit(""))
                .otherwise(pl.col("referrer"))
                .alias("referrer"),
                pl.when(pl.col("ua") == "-")
                .then(pl.lit(""))
                .otherwise(pl.col("ua"))
                .alias("ua"),
                pl.col("cs").map_elements(
                    lambda s: "" if s in ("-", None) else s, return_dtype=pl.String
                ),
            ]
        )
        .drop("time")
        .select(
            [
                "t",
                "addr",
                "method",
                "path",
                "status",
                "size",
                "referrer",
                "ua",
                "rt",
                "uct",
                "uht",
                "urt",
                "cs",
                "host",
            ]
        )
    )

    n_bad_time = int(df["t"].null_count())
    if n_bad_time:
        df = df.filter(pl.col("t").is_not_null())
        failures += n_bad_time
    return df, failures


def drop_alpha_hosts(df: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    """Drop rows served to the alpha vhost and remove the transient `host` column.

    Live instances are promoted alphas, so the access.log mixes the box's prior
    alpha-domain traffic with live; `$host` separates them. `host` is used only at
    ingest and never persisted, keeping the archive schema stable."""
    if "host" not in df.columns:
        return df, 0
    is_alpha = pl.col("host").str.to_lowercase().str.starts_with(ALPHA_HOST_PREFIX)
    n_alpha = int(df.select(is_alpha.sum()).item())
    return df.filter(~is_alpha).drop("host"), n_alpha


def _empty_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
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
            "host": pl.Series([], dtype=pl.String),
        }
    )
