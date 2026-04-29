import datetime as dt
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .. import aggregate, archive
from ..config import (
    ARCHIVE_DIR,
    IP_HASH_LEN,
    RUN_LOGS_DIR,
    SITE_LOCAL_DIR,
    SITE_PUBLIC_DIR,
)
from ..state import get_or_create_salt, load

Mode = Literal["local", "public"]

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
ASSET_DIR = Path(__file__).parent.parent / "assets"


@dataclass
class RenderContext:
    mode: Mode
    out_dir: Path
    env: Environment
    events_24h: pd.DataFrame
    sessions_table: pd.DataFrame
    hourly: pd.DataFrame
    daily: pd.DataFrame
    state_snapshot: dict
    now: dt.datetime
    runs_index: list[dict]


def build_context(mode: Mode) -> RenderContext:
    out_dir = SITE_LOCAL_DIR if mode == "local" else SITE_PUBLIC_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sessions").mkdir(exist_ok=True)
    (out_dir / "runs").mkdir(exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["fmt_int"] = lambda v: f"{int(v):,}" if pd.notna(v) else "—"
    env.filters["fmt_pct"] = lambda v: (
        f"{v*100:.2f}%" if (v is not None and pd.notna(v)) else "—"
    )
    env.filters["fmt_ms"] = lambda v: f"{v*1000:.0f} ms" if pd.notna(v) else "—"
    env.filters["fmt_dt"] = lambda v: pd.to_datetime(v).strftime("%Y-%m-%d %H:%M UTC")

    today = dt.date.today()
    cutoff_24h = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=1)
    hot_recent = archive.read_hot(date_from=today - dt.timedelta(days=2))
    if hot_recent.empty:
        events_24h = hot_recent
    else:
        events_24h = hot_recent[hot_recent["t"] >= cutoff_24h].copy()
    if mode == "public" and not events_24h.empty:
        events_24h = anonymize_events(events_24h)

    sessions_table = aggregate.load_sessions()
    if mode == "public" and not sessions_table.empty:
        sessions_table = _anonymize_sessions(sessions_table)

    state = load()
    runs_idx = _read_runs_index()

    return RenderContext(
        mode=mode,
        out_dir=out_dir,
        env=env,
        events_24h=events_24h,
        sessions_table=sessions_table,
        hourly=aggregate.load_hourly(),
        daily=aggregate.load_daily(),
        state_snapshot=state.__dict__,
        now=dt.datetime.now(dt.timezone.utc),
        runs_index=runs_idx,
    )


def write(ctx: RenderContext, rel_path: str, html: str) -> None:
    p = ctx.out_dir / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html)


def hint(text: str) -> str:
    return f"<p class='hint'>{text}</p>"


def df_to_html(df: pd.DataFrame, *, table_id: str, escape: bool = True) -> str:
    return df.to_html(
        classes="dt", index=False, table_id=table_id, border=0, escape=escape,
    )


def render_template(ctx: RenderContext, template: str, **vars) -> str:
    tpl = ctx.env.get_template(template)
    base_vars = {
        "mode": ctx.mode,
        "now_iso": ctx.now.isoformat(timespec="seconds"),
        "state": ctx.state_snapshot,
        "active_page": "",
    }
    base_vars.update(vars)
    return tpl.render(**base_vars)


def plotly_div(fig_id: str, data: list, layout: dict | None = None, height: int = 320) -> str:
    layout = layout or {}
    layout.setdefault("margin", {"l": 40, "r": 20, "t": 30, "b": 40})
    layout.setdefault("paper_bgcolor", "rgba(0,0,0,0)")
    layout.setdefault("plot_bgcolor", "rgba(0,0,0,0)")
    layout.setdefault("font", {"color": "#cdd6f4", "size": 12})
    spec = {"data": data, "layout": layout, "config": {"displaylogo": False, "responsive": True}}
    return (
        f'<div id="{fig_id}" style="height:{height}px"></div>'
        f'<script>Plotly.newPlot("{fig_id}", '
        f"{json.dumps(spec, default=_json_default)});</script>"
    )


def time_series_traces(df: pd.DataFrame, x: str, y: str, group: str) -> list[dict]:
    out = []
    for name, g in df.groupby(group):
        out.append(
            {
                "x": list(g[x].astype(str)),
                "y": list(g[y]),
                "name": str(name),
                "type": "scatter",
                "mode": "lines",
            }
        )
    return out


def hash_ip(addr: str, day_iso: str | None = None) -> str:
    salt = get_or_create_salt(day_iso or dt.date.today().isoformat())
    return hashlib.sha256(f"{salt}|{addr}".encode()).hexdigest()[:IP_HASH_LEN]


def copy_assets(ctx: RenderContext) -> None:
    if not ASSET_DIR.exists():
        return
    target = ctx.out_dir / "assets"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(ASSET_DIR, target)


def anonymize_events(df: pd.DataFrame) -> pd.DataFrame:
    if "addr" in df.columns:
        day = df["t"].dt.date.astype(str)
        df = df.assign(
            addr=[hash_ip(a, d) for a, d in zip(df["addr"], day)]
        )
    return df.drop(columns=[c for c in ("ua", "referrer", "path") if c in df.columns])


def _anonymize_sessions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "addr" in df.columns:
        day = pd.to_datetime(df["start"]).dt.date.astype(str)
        df["addr"] = [hash_ip(a, d) for a, d in zip(df["addr"], day)]
    df = df.drop(columns=[c for c in ("ua",) if c in df.columns])
    return df


def _read_runs_index() -> list[dict]:
    out = []
    if not RUN_LOGS_DIR.exists():
        return out
    for f in sorted(RUN_LOGS_DIR.glob("run-*.log")):
        for line in f.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    out.sort(key=lambda r: r.get("ts", ""), reverse=True)
    return out[:200]


def _json_default(o):
    if isinstance(o, (pd.Timestamp, dt.datetime, dt.date)):
        return o.isoformat()
    if hasattr(o, "tolist"):
        return o.tolist()
    if isinstance(o, set):
        return list(o)
    return str(o)
