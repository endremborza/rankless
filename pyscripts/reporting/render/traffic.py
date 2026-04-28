import pandas as pd

from .base import RenderContext, plotly_div, render_template, write


def render(ctx: RenderContext) -> None:
    sessions = ctx.sessions_table
    events = ctx.events_24h
    daily = ctx.daily

    bot_area = _bot_area(daily)
    top_uas = _top_table(
        sessions, "ua_family" if "ua_family" in sessions.columns else "ua",
        agg_col="bot_class", title_id="top-uas",
    ) if not sessions.empty else "<p class='hint'>No sessions.</p>"
    top_refs = _top_referrers(events)
    top_paths = _top_paths(events, sessions)
    status_chart = _status_donut(daily)

    html = render_template(
        ctx,
        "traffic.html.j2",
        active_page="traffic",
        depth=0,
        bot_area_chart=bot_area,
        top_uas_table=top_uas,
        top_refs_table=top_refs,
        top_paths_table=top_paths,
        status_chart=status_chart,
    )
    write(ctx, "traffic.html", html)


def _bot_area(daily: pd.DataFrame) -> str:
    if daily.empty:
        return "<p class='hint'>No data.</p>"
    g = daily.groupby(["bucket", "bot_class"])["n"].sum().unstack(fill_value=0)
    color_map = {
        "bot_known": "#f38ba8",
        "bot_likely": "#eba0ac",
        "human_known": "#a6e3a1",
        "human_likely": "#94e2d5",
        "unknown": "#9399b2",
    }
    traces = [
        {
            "x": list(g.index.astype(str)),
            "y": list(g[col]),
            "name": col,
            "type": "scatter",
            "stackgroup": "one",
            "fillcolor": color_map.get(col),
            "line": {"width": 0.5, "color": color_map.get(col)},
        }
        for col in g.columns
    ]
    return plotly_div("bot-area", traces, layout={"yaxis": {"title": "requests"}})


def _top_table(
    df: pd.DataFrame,
    by: str,
    agg_col: str | None = None,
    title_id: str = "tbl",
    n: int = 30,
) -> str:
    if df.empty or by not in df.columns:
        return "<p class='hint'>No data.</p>"
    if agg_col and agg_col in df.columns:
        ct = df.groupby(by)[agg_col].agg(["count", _mode]).reset_index()
        ct.columns = [by, "sessions", "dominant_class"]
    else:
        ct = df.groupby(by).size().reset_index(name="sessions")
    ct = ct.sort_values("sessions", ascending=False).head(n)
    return ct.to_html(classes="dt", index=False, table_id=title_id, border=0)


def _mode(s):
    return s.mode().iloc[0] if len(s) else ""


def _top_referrers(events: pd.DataFrame) -> str:
    if events.empty or "referrer_domain" not in events.columns:
        return "<p class='hint'>No data.</p>"
    s = events[events["referrer_domain"].fillna("") != ""]
    if s.empty:
        return "<p class='hint'>No referrer hits.</p>"
    ct = (
        s.groupby("referrer_domain")
        .size()
        .reset_index(name="requests")
        .sort_values("requests", ascending=False)
        .head(30)
    )
    return ct.to_html(classes="dt", index=False, table_id="top-refs", border=0)


def _top_paths(events: pd.DataFrame, sessions: pd.DataFrame) -> str:
    if events.empty or sessions.empty:
        return "<p class='hint'>No data.</p>"
    human_ids = set(
        sessions.loc[sessions["bot_class"].isin(["human_known", "human_likely"]), "session_id"]
    )
    s = events[events["session_id"].isin(human_ids)]
    if s.empty:
        return "<p class='hint'>No human sessions yet.</p>"
    ct = (
        s.groupby("route_template")
        .size()
        .reset_index(name="requests")
        .sort_values("requests", ascending=False)
        .head(30)
    )
    return ct.to_html(classes="dt", index=False, table_id="top-paths", border=0)


def _status_donut(daily: pd.DataFrame) -> str:
    if daily.empty:
        return "<p class='hint'>No data.</p>"
    cutoff = daily["bucket"].max() - pd.Timedelta(days=7)
    s = daily[daily["bucket"] >= cutoff]
    g = s.groupby("status_family")["n"].sum().reset_index().sort_values("status_family")
    return plotly_div(
        "status-donut",
        [
            {
                "labels": list(g["status_family"]),
                "values": list(g["n"]),
                "type": "pie",
                "hole": 0.5,
            }
        ],
        layout={},
    )
