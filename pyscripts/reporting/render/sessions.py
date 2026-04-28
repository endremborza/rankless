import json

import pandas as pd

from .. import archive
from .base import RenderContext, render_template, write


def render(ctx: RenderContext) -> None:
    sessions = ctx.sessions_table
    if sessions.empty:
        write(ctx, "sessions/index.html", _empty(ctx))
        return

    cutoff = pd.to_datetime(sessions["start"]).max() - pd.Timedelta(days=7)
    recent = sessions[pd.to_datetime(sessions["start"]) >= cutoff].copy()

    recent["session"] = recent["session_id"].map(lambda s: f'<a href="{s}.html">{s}</a>')
    cols = ["session", "addr", "ua_family", "bot_class", "start", "end", "n_req", "route_diversity"]
    cols = [c for c in cols if c in recent.columns]
    table_html = recent[cols].sort_values("start", ascending=False).to_html(
        classes="dt", index=False, table_id="sessions", border=0, escape=False
    )

    html = render_template(
        ctx,
        "sessions_index.html.j2",
        active_page="sessions",
        depth=1,
        sessions_table=table_html,
    )
    write(ctx, "sessions/index.html", html)

    # Per-session details (cap to most recent N for site size).
    import datetime as dt
    today = dt.date.today()
    events = archive.read_hot(date_from=today - dt.timedelta(days=7))
    if ctx.mode == "public" and not events.empty:
        from .base import _anonymize_events
        events = _anonymize_events(events)

    top_sessions = recent.sort_values("n_req", ascending=False).head(500)
    for _, sess in top_sessions.iterrows():
        sess_events = events[events["session_id"] == sess["session_id"]] if not events.empty else pd.DataFrame()
        signals = []
        try:
            signals = json.loads(sess.get("signals_json", "[]"))
        except (TypeError, ValueError):
            signals = []
        ev_cols = [c for c in ("t", "method", "route_template", "status", "urt", "cs", "size") if c in sess_events.columns]
        if not sess_events.empty:
            ev_html = sess_events[ev_cols].sort_values("t").to_html(
                classes="dt", index=False, table_id="ev", border=0,
            )
        else:
            ev_html = "<p class='hint'>No events archived for this session.</p>"
        html = render_template(
            ctx,
            "session_detail.html.j2",
            active_page="sessions",
            depth=1,
            session=sess.to_dict(),
            signals=signals,
            events_table=ev_html,
        )
        write(ctx, f"sessions/{sess['session_id']}.html", html)


def _empty(ctx: RenderContext) -> str:
    return render_template(
        ctx,
        "sessions_index.html.j2",
        active_page="sessions",
        depth=1,
        sessions_table="<p class='hint'>No sessions yet.</p>",
    )
