import pandas as pd

from .. import aggregate
from .base import RenderContext, copy_assets, kpi_window, plotly_div, render_template, write


def render(ctx: RenderContext) -> None:
    copy_assets(ctx)
    events = ctx.events_24h

    kpis = {
        "1h": _kpi_block("Last 1h", kpi_window(events, 1)),
        "24h": _kpi_block("Last 24h", kpi_window(events, 24)),
        "7d": _kpi_block("Last 7d", _kpi_from_daily(ctx.daily, 7)),
        "30d": _kpi_block("Last 30d", _kpi_from_daily(ctx.daily, 30)),
    }

    traffic_chart = _traffic_chart(ctx.daily)
    bot_chart = _bot_session_chart(ctx.sessions_table)

    html = render_template(
        ctx,
        "landing.html.j2",
        active_page="landing",
        depth=0,
        kpis=kpis,
        traffic_chart=traffic_chart,
        bot_chart=bot_chart,
    )
    write(ctx, "index.html", html)


def _kpi_block(label, k):
    parts = []
    parts.append(_card("Requests", f"{k['n_req']:,}"))
    parts.append(_card("Sessions", f"{k['n_sessions']:,}"))
    parts.append(_card("Human %", _pct(k["human_pct"])))
    parts.append(_card("Error rate", _pct(k["err_rate"])))
    parts.append(_card("p99 urt", _ms(k["p99"])))
    parts.append(_card("Cache hit", _pct(k["cache_hit_rate"])))
    return {"label": label, "value": "", "html": "\n".join(parts)}


def _card(label, value):
    return f'<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div></div>'


def _pct(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{v*100:.2f}%"


def _ms(v):
    if v is None or pd.isna(v):
        return "—"
    return f"{v*1000:.0f} ms"


def _kpi_from_daily(daily: pd.DataFrame, days: int) -> dict:
    if daily.empty:
        return {
            "n_req": 0,
            "n_sessions": 0,
            "human_pct": float("nan"),
            "err_rate": float("nan"),
            "p99": float("nan"),
            "cache_hit_rate": float("nan"),
        }
    cutoff = daily["bucket"].max() - pd.Timedelta(days=days)
    s = daily[daily["bucket"] >= cutoff]
    n = int(s["n"].sum())
    n_5xx = int(s.loc[s["status_family"] == "5xx", "n"].sum())
    cache_hit = int(s.loc[s["cs"] == "HIT", "n"].sum())
    human = int(s.loc[s["bot_class"].isin(["human_known", "human_likely"]), "n"].sum())
    p99 = float(s["urt_p99"].dropna().mean()) if s["urt_p99"].notna().any() else float("nan")
    return {
        "n_req": n,
        "n_sessions": 0,
        "human_pct": human / n if n else float("nan"),
        "err_rate": n_5xx / n if n else float("nan"),
        "p99": p99,
        "cache_hit_rate": cache_hit / n if n else float("nan"),
    }


def _traffic_chart(daily: pd.DataFrame) -> str:
    if daily.empty:
        return "<p class='hint'>No data yet.</p>"
    g = daily.groupby("bucket")["n"].sum().reset_index()
    return plotly_div(
        "traffic-30d",
        [
            {
                "x": list(g["bucket"].astype(str)),
                "y": list(g["n"]),
                "type": "bar",
                "marker": {"color": "#89b4fa"},
                "name": "Requests",
            }
        ],
        layout={"yaxis": {"title": "requests"}},
    )


def _bot_session_chart(sessions: pd.DataFrame) -> str:
    if sessions.empty:
        return "<p class='hint'>No sessions yet.</p>"
    s = sessions.copy()
    s["day"] = pd.to_datetime(s["start"]).dt.floor("D")
    pivot = s.groupby(["day", "bot_class"]).size().unstack(fill_value=0)
    color_map = {
        "bot_known": "#f38ba8",
        "bot_likely": "#eba0ac",
        "human_known": "#a6e3a1",
        "human_likely": "#94e2d5",
        "unknown": "#9399b2",
    }
    traces = []
    for col in pivot.columns:
        traces.append(
            {
                "x": list(pivot.index.astype(str)),
                "y": list(pivot[col]),
                "name": col,
                "type": "bar",
                "marker": {"color": color_map.get(col, "#cdd6f4")},
            }
        )
    return plotly_div(
        "bot-stack",
        traces,
        layout={"barmode": "stack", "yaxis": {"title": "sessions"}},
    )
