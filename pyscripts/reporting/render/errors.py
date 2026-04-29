import pandas as pd

from .base import RenderContext, df_to_html, hint, render_template, write

ERROR_TABLES = [
    ("err-5xx", lambda d: d["status"] >= 500),
    ("err-4xx", lambda d: (d["status"] >= 400) & (d["status"] < 500) & (d["status"] != 404)),
    ("err-429", lambda d: d["status"] == 429),
]
ERROR_DAYS = 7


def render(ctx: RenderContext) -> None:
    cutoff = pd.Timestamp(ctx.now) - pd.Timedelta(days=ERROR_DAYS)
    events = ctx.events_hot[ctx.events_hot["t"] >= cutoff] if not ctx.events_hot.empty else ctx.events_hot

    tables = {tid: _err_table(events, mask, tid) for tid, mask in ERROR_TABLES}

    write(ctx, "errors.html", render_template(
        ctx, "errors.html.j2",
        active_page="errors", depth=0,
        table_5xx=tables["err-5xx"],
        table_4xx=tables["err-4xx"],
        table_429=tables["err-429"],
    ))


def _err_table(events: pd.DataFrame, mask_fn, table_id: str) -> str:
    if events.empty:
        return hint("No data.")
    s = events[mask_fn(events)]
    if s.empty:
        return hint("None.")
    return (
        s.groupby(["route_template", "status"])
        .agg(n=("status", "count"), last_seen=("t", "max"))
        .reset_index()
        .sort_values("n", ascending=False)
        .head(50)
        .assign(last_seen=lambda d: d["last_seen"].dt.strftime("%Y-%m-%d %H:%M UTC"))
        .pipe(df_to_html, table_id=table_id)
    )
