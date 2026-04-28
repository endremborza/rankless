import datetime as dt
from typing import Iterable

import numpy as np
import pandas as pd

from .config import LINE_RE, LOG_TIME_FMT


def _f(s: str | None) -> float:
    if s is None or s == "" or s == "-":
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def parse_lines(lines: Iterable[str]) -> tuple[pd.DataFrame, int]:
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
    df = pd.DataFrame(rows)
    df = df.assign(
        t=pd.to_datetime(df["time"], format=LOG_TIME_FMT, utc=True),
        status=df["status"].astype("uint16"),
        size=df["size"].astype("uint32"),
        rt=df["rt"].map(_f).astype("float32"),
        uct=df["uct"].map(_f).astype("float32"),
        uht=df["uht"].map(_f).astype("float32"),
        urt=df["urt"].map(_f).astype("float32"),
        referrer=df["referrer"].where(df["referrer"] != "-", ""),
        ua=df["ua"].where(df["ua"] != "-", ""),
        cs=df["cs"].fillna("").where(lambda s: s != "-", ""),
    ).drop(columns=["time"])
    return df[
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
        ]
    ], failures


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "t": pd.Series(dtype="datetime64[ns, UTC]"),
            "addr": pd.Series(dtype="object"),
            "method": pd.Series(dtype="object"),
            "path": pd.Series(dtype="object"),
            "status": pd.Series(dtype="uint16"),
            "size": pd.Series(dtype="uint32"),
            "referrer": pd.Series(dtype="object"),
            "ua": pd.Series(dtype="object"),
            "rt": pd.Series(dtype="float32"),
            "uct": pd.Series(dtype="float32"),
            "uht": pd.Series(dtype="float32"),
            "urt": pd.Series(dtype="float32"),
            "cs": pd.Series(dtype="object"),
        }
    )
