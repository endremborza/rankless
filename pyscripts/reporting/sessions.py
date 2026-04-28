import datetime as dt
import hashlib

import pandas as pd

from .config import SESSION_ID_LEN, SESSION_IDLE_MIN
from .state import get_or_create_salt


def assign_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Adds `session_id` to df. Sessions = same (addr, ua) split by >SESSION_IDLE_MIN gap."""
    if df.empty:
        df = df.copy()
        df["session_id"] = pd.Series([], dtype="object")
        return df

    df = df.sort_values(["addr", "ua", "t"]).reset_index(drop=True)
    same_who = (df["addr"] == df["addr"].shift()) & (df["ua"] == df["ua"].shift())
    gap = df["t"].diff() > pd.Timedelta(minutes=SESSION_IDLE_MIN)
    new_session = (~same_who) | gap
    new_session.iloc[0] = True

    # session start = t at the boundary, propagated forward.
    starts_t = df["t"].where(new_session).ffill()
    starts_addr = df["addr"]
    starts_ua = df["ua"]

    salts_for_dates = {d: get_or_create_salt(d.isoformat()) for d in starts_t.dt.date.unique()}
    df["session_id"] = [
        _hash_session(salts_for_dates[d.date()], a, u, t)
        for d, a, u, t in zip(starts_t, starts_addr, starts_ua, starts_t)
    ]
    return df


def _hash_session(salt: str, addr: str, ua: str, start: dt.datetime) -> str:
    h = hashlib.sha256(f"{salt}|{addr}|{ua}|{start.isoformat()}".encode()).hexdigest()
    return h[:SESSION_ID_LEN]
