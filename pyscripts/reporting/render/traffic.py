import pandas as pd

from ..classify import BOT_CLASS_COLORS, HUMAN_CLASSES
from .base import RenderContext, df_to_html, hint, plotly_div, render_template, write

TOP_N = 30


def render(ctx: RenderContext) -> None:
    sessions, events, daily = ctx.sessions_table, ctx.events_24h, ctx.daily

    write(ctx, "traffic.html", render_template(
        ctx, "traffic.html.j2",
        active_page="traffic", depth=0,
        bot_area_chart=_bot_area(daily),
        top_uas_table=_top_uas(sessions),
        top_refs_table=_top_referrers(events),
        top_paths_table=_top_paths(events, sessions),
        status_chart=_status_donut(daily),
    ))


def _bot_area(daily: pd.DataFrame) -> str:
    if daily.empty:
        return hint("No data.")
    g = daily.groupby(["bucket", "bot_class"])["n"].sum().unstack(fill_value=0)
    traces = [
        {
            "x": list(g.index.astype(str)),
            "y": list(g[col]),
            "name": col,
            "type": "scatter",
            "stackgroup": "one",
            "fillcolor": BOT_CLASS_COLORS.get(col),
            "line": {"width": 0.5, "color": BOT_CLASS_COLORS.get(col)},
        }
        for col in g.columns
    ]
    return plotly_div("bot-area", traces, layout={"yaxis": {"title": "requests"}})


def _top_uas(sessions: pd.DataFrame) -> str:
    if sessions.empty:
        return hint("No sessions.")
    by = "ua_family" if "ua_family" in sessions.columns else "ua"
    if by not in sessions.columns:
        return hint("No data.")
    if "bot_class" in sessions.columns:
        ct = (
            sessions.groupby(by)["bot_class"]
            .agg(["count", lambda s: s.mode().iloc[0] if len(s) else ""])
            .set_axis(["sessions", "dominant_class"], axis=1)
            .reset_index()
        )
    else:
        ct = sessions.groupby(by).size().reset_index(name="sessions")
    return (
        ct.sort_values("sessions", ascending=False)
        .head(TOP_N)
        .pipe(df_to_html, table_id="top-uas")
    )


def _top_referrers(events: pd.DataFrame) -> str:
    if events.empty or "referrer_domain" not in events.columns:
        return hint("No data.")
    s = events[events["referrer_domain"].fillna("") != ""]
    if s.empty:
        return hint("No referrer hits.")
    return (
        s.groupby("referrer_domain").size()
        .reset_index(name="requests")
        .sort_values("requests", ascending=False)
        .head(TOP_N)
        .pipe(df_to_html, table_id="top-refs")
    )


def _top_paths(events: pd.DataFrame, sessions: pd.DataFrame) -> str:
    if events.empty or sessions.empty:
        return hint("No data.")
    human_ids = set(sessions.loc[sessions["bot_class"].isin(HUMAN_CLASSES), "session_id"])
    s = events[events["session_id"].isin(human_ids)]
    if s.empty:
        return hint("No human sessions yet.")
    return (
        s.groupby("route_template").size()
        .reset_index(name="requests")
        .sort_values("requests", ascending=False)
        .head(TOP_N)
        .pipe(df_to_html, table_id="top-paths")
    )


def _status_donut(daily: pd.DataFrame) -> str:
    if daily.empty:
        return hint("No data.")
    cutoff = daily["bucket"].max() - pd.Timedelta(days=7)
    g = (
        daily[daily["bucket"] >= cutoff]
        .groupby("status_family")["n"].sum()
        .reset_index()
        .sort_values("status_family")
    )
    return plotly_div(
        "status-donut",
        [{"labels": list(g["status_family"]), "values": list(g["n"]), "type": "pie", "hole": 0.5}],
    )
