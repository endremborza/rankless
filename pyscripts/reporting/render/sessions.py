import datetime as dt
import json

import pandas as pd

from .. import archive
from ..classify import HUMAN_CLASSES
from .base import RenderContext, anonymize_events, df_to_html, hint, render_template, write

INDEX_DAYS = 7
DETAIL_TOP_N = 100
INDEX_COLS = [
    "session", "addr", "ua_family", "bot_class",
    "start", "end", "n_req", "route_diversity",
]
EVENT_COLS = ["t", "method", "path", "route_template", "status", "urt", "cs", "size"]


def render(ctx: RenderContext) -> None:
    sessions = ctx.sessions_table
    if sessions.empty:
        write(ctx, "sessions/index.html", _empty(ctx))
        return

    cutoff = pd.to_datetime(sessions["start"]).max() - pd.Timedelta(days=INDEX_DAYS)
    recent = sessions.loc[
        lambda d: (pd.to_datetime(d["start"]) >= cutoff) & (d["n_req"] > 1)
    ]

    detailed_ids = set(
        recent[recent["bot_class"].isin(HUMAN_CLASSES)]
        .sort_values("n_req", ascending=False)
        .head(DETAIL_TOP_N)["session_id"]
    )

    table_html = (
        recent.assign(session=recent["session_id"].map(_link(detailed_ids)))
        .sort_values("start", ascending=False)
        .pipe(lambda d: d[[c for c in INDEX_COLS if c in d.columns]])
        .pipe(df_to_html, table_id="sessions", escape=False)
    )

    write(ctx, "sessions/index.html", render_template(
        ctx, "sessions_index.html.j2",
        active_page="sessions", depth=1,
        sessions_table=table_html,
        n_detailed=len(detailed_ids),
    ))

    if not detailed_ids:
        return

    today = dt.date.today()
    events = archive.read_hot(date_from=today - dt.timedelta(days=INDEX_DAYS))
    if ctx.mode == "public" and not events.empty:
        events = anonymize_events(events)
    events_by_sid = (
        events.groupby("session_id") if not events.empty else None
    )

    detailed_rows = recent[recent["session_id"].isin(detailed_ids)]
    for _, sess in detailed_rows.iterrows():
        sid = sess["session_id"]
        sess_events = events_by_sid.get_group(sid) if events_by_sid is not None and sid in events_by_sid.groups else pd.DataFrame()
        write(ctx, f"sessions/{sid}.html", _detail_html(ctx, sess, sess_events))


def _detail_html(ctx: RenderContext, sess: pd.Series, sess_events: pd.DataFrame) -> str:
    if sess_events.empty:
        ev_html = hint("No events archived for this session.")
    else:
        ev_html = (
            sess_events.sort_values("t")
            .pipe(lambda d: d[[c for c in EVENT_COLS if c in d.columns]])
            .pipe(df_to_html, table_id="ev")
        )
    try:
        signals = json.loads(sess.get("signals_json", "[]"))
    except (TypeError, ValueError):
        signals = []
    return render_template(
        ctx, "session_detail.html.j2",
        active_page="sessions", depth=1,
        session=sess.to_dict(),
        signals=signals,
        events_table=ev_html,
    )


def _link(detailed_ids: set[str]):
    def fmt(sid: str) -> str:
        return f'<a href="{sid}.html">{sid}</a>' if sid in detailed_ids else sid
    return fmt


def _empty(ctx: RenderContext) -> str:
    return render_template(
        ctx, "sessions_index.html.j2",
        active_page="sessions", depth=1,
        sessions_table=hint("No sessions yet."),
        n_detailed=0,
    )
