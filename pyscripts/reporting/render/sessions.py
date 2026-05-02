import datetime as dt
import json

import polars as pl

from ..classify import HUMAN_CLASSES
from .base import RenderContext, df_to_html, hint, render_template, write

INDEX_DAYS = 7
DETAIL_TOP_N = 100
INDEX_COLS = [
    "session", "addr", "ua_family", "bot_class",
    "start", "end", "n_req", "route_diversity",
]
EVENT_COLS = ["t", "method", "path", "route_template", "status", "urt", "cs", "size"]


def render(ctx: RenderContext) -> None:
    sessions = ctx.sessions_table
    if sessions.is_empty():
        write(ctx, "sessions/index.html", _empty(ctx))
        return

    max_start = sessions["start"].max()
    cutoff = max_start - pl.duration(days=INDEX_DAYS)
    recent = sessions.filter(
        (pl.col("start") >= cutoff) & (pl.col("n_req") > 1)
    )

    show_details = ctx.mode != "public"
    detailed_ids: set[str] = set()
    if show_details:
        detailed_ids = set(
            recent.filter(pl.col("bot_class").is_in(list(HUMAN_CLASSES)))
            .sort("n_req", descending=True)
            .head(DETAIL_TOP_N)["session_id"]
            .to_list()
        )

    link_map = {sid: f'<a href="{sid}.html">{sid}</a>' if sid in detailed_ids else sid
                for sid in recent["session_id"].to_list()}
    display = (
        recent.with_columns(
            pl.col("session_id").replace_strict(link_map, return_dtype=pl.String).alias("session")
        )
        .sort("start", descending=True)
        .select([c for c in INDEX_COLS if c in recent.columns or c == "session"])
    )
    table_html = df_to_html(display, table_id="sessions", escape=False)

    write(ctx, "sessions/index.html", render_template(
        ctx, "sessions_index.html.j2",
        active_page="sessions", depth=1,
        sessions_table=table_html,
        n_detailed=len(detailed_ids),
    ))

    if not detailed_ids:
        return

    cutoff_dt = ctx.now - dt.timedelta(days=INDEX_DAYS)
    events = (
        ctx.events_hot.filter(
            (pl.col("t") >= cutoff_dt) & pl.col("session_id").is_in(detailed_ids)
        )
        if not ctx.events_hot.is_empty() else ctx.events_hot
    )
    events_by_sid = {
        part["session_id"][0]: part
        for part in events.partition_by("session_id", maintain_order=False)
    } if not events.is_empty() else {}

    for row in recent.filter(pl.col("session_id").is_in(detailed_ids)).iter_rows(named=True):
        sid = row["session_id"]
        sess_events = events_by_sid.get(sid, pl.DataFrame())
        write(ctx, f"sessions/{sid}.html", _detail_html(ctx, row, sess_events))


def _detail_html(ctx: RenderContext, sess: dict, sess_events: pl.DataFrame) -> str:
    if sess_events.is_empty():
        ev_html = hint("No events archived for this session.")
    else:
        cols = [c for c in EVENT_COLS if c in sess_events.columns]
        ev_html = df_to_html(sess_events.sort("t").select(cols), table_id="ev")
    try:
        signals = json.loads(sess.get("signals_json", "[]"))
    except (TypeError, ValueError):
        signals = []
    return render_template(
        ctx, "session_detail.html.j2",
        active_page="sessions", depth=1,
        session=sess,
        signals=signals,
        events_table=ev_html,
    )


def _empty(ctx: RenderContext) -> str:
    return render_template(
        ctx, "sessions_index.html.j2",
        active_page="sessions", depth=1,
        sessions_table=hint("No sessions yet."),
        n_detailed=0,
    )
