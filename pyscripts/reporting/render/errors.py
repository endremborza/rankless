import pandas as pd

from .. import archive
from .base import RenderContext, render_template, write


def render(ctx: RenderContext) -> None:
    import datetime as dt

    today = dt.date.today()
    events = archive.read_hot(date_from=today - dt.timedelta(days=7))
    if events.empty:
        events = ctx.events_24h

    if ctx.mode == "public" and not events.empty and "addr" in events.columns:
        from .base import _anonymize_events
        events = _anonymize_events(events)

    table_5xx = _err_table(events, lambda df: df["status"] >= 500, "err-5xx")
    table_4xx = _err_table(
        events,
        lambda df: (df["status"] >= 400) & (df["status"] < 500) & (df["status"] != 404),
        "err-4xx",
    )
    table_429 = _err_table(events, lambda df: df["status"] == 429, "err-429")

    html = render_template(
        ctx,
        "errors.html.j2",
        active_page="errors",
        depth=0,
        table_5xx=table_5xx,
        table_4xx=table_4xx,
        table_429=table_429,
    )
    write(ctx, "errors.html", html)


def _err_table(events: pd.DataFrame, mask_fn, table_id: str) -> str:
    if events.empty:
        return "<p class='hint'>No data.</p>"
    mask = mask_fn(events)
    s = events[mask]
    if s.empty:
        return "<p class='hint'>None.</p>"
    cols = ["route_template", "status"]
    g = s.groupby(cols).agg(
        n=("status", "count"),
        last_seen=("t", "max"),
    ).reset_index().sort_values("n", ascending=False).head(50)
    g["last_seen"] = g["last_seen"].dt.strftime("%Y-%m-%d %H:%M UTC")
    return g.to_html(classes="dt", index=False, table_id=table_id, border=0)
