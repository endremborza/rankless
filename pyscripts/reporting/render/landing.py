import polars as pl

from ..classify import BOT_CLASS_COLORS, BOT_CLASS_ORDER
from .base import RenderContext, copy_assets, hint, plotly_div, render_template, write

WINDOWS = [
    ("Last 1h", "1h", 1),
    ("Last 24h", "24h", 24),
    ("Last 7d", "7d", 7 * 24),
    ("Last 30d", "30d", 30 * 24),
]


def render(ctx: RenderContext) -> None:
    copy_assets(ctx)

    kpis = {
        key: _kpi_block(label, ctx.events_hot, hours) for label, key, hours in WINDOWS
    }

    write(
        ctx,
        "index.html",
        render_template(
            ctx,
            "landing.html.j2",
            active_page="landing",
            depth=0,
            kpis=kpis,
            traffic_chart=_traffic_chart(ctx.daily),
            bot_chart=_bot_session_chart(ctx.sessions_table),
        ),
    )


def _kpi_block(label: str, events: pl.DataFrame, hours: int) -> dict:
    if events.is_empty():
        return {"label": label, "html": _empty_kpi_html()}
    cutoff = events["t"].max() - pl.duration(hours=hours)
    s = events.filter(pl.col("t") >= cutoff)
    if s.is_empty():
        return {"label": label, "html": _empty_kpi_html()}

    n = len(s)
    sess = s.unique(subset=["session_id"]) if "session_id" in s.columns else s.head(0)
    n_sessions = len(sess)
    n_5xx = int((s["status"] >= 500).sum())
    cache_hit = int((s["cs"] == "HIT").sum()) if "cs" in s.columns else 0
    urt_valid = s["urt"].drop_nulls()
    p99 = float(urt_valid.quantile(0.99)) if len(urt_valid) > 0 else float("nan")

    cards = [
        _card("Requests", f"{n:,}"),
        _card("Sessions", f"{n_sessions:,}"),
        _card("5xx rate", _pct(n_5xx / n)),
        _card("p99 urt", _ms(p99)),
        _card("Cache hit", _pct(cache_hit / n)),
    ]
    if n_sessions and "bot_class" in sess.columns:
        cards.append(_breakdown_card(sess["bot_class"]))
    return {"label": label, "html": "\n".join(cards)}


def _card(label: str, value: str) -> str:
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f"</div>"
    )


def _breakdown_card(classes: pl.Series) -> str:
    counts_map = dict(zip(*classes.value_counts().to_pandas().values.T))
    counts = {cls: int(counts_map.get(cls, 0)) for cls in BOT_CLASS_ORDER}
    total = sum(counts.values())
    if total == 0:
        return _card("Class breakdown", "—")
    segs = []
    legend = []
    for cls, n in counts.items():
        if n == 0:
            continue
        pct = n / total * 100
        color = BOT_CLASS_COLORS.get(cls, "#cdd6f4")
        segs.append(
            f'<span class="seg" style="background:{color};width:{pct:.2f}%" '
            f'title="{cls}: {n} ({pct:.1f}%)"></span>'
        )
        legend.append(
            f'<span class="legend-item"><span class="dot" style="background:{color}"></span>'
            f"{cls} {n}</span>"
        )
    return (
        '<div class="kpi-card kpi-breakdown">'
        '<div class="kpi-label">Sessions by class</div>'
        f'<div class="bot-bar">{"".join(segs)}</div>'
        f'<div class="bot-legend">{" ".join(legend)}</div>'
        "</div>"
    )


def _empty_kpi_html() -> str:
    return _card("Requests", "0")


def _pct(v: float) -> str:
    import math

    if v is None or math.isnan(v):
        return "—"
    return f"{v * 100:.2f}%"


def _ms(v: float) -> str:
    import math

    if v is None or math.isnan(v):
        return "—"
    return f"{v * 1000:.0f} ms"


def _traffic_chart(daily: pl.DataFrame) -> str:
    if daily.is_empty():
        return hint("No data yet.")
    g = daily.group_by("bucket").agg(pl.col("n").sum()).sort("bucket")
    return plotly_div(
        "traffic-30d",
        [
            {
                "x": g["bucket"].cast(pl.String).to_list(),
                "y": g["n"].to_list(),
                "type": "bar",
                "marker": {"color": "#89b4fa"},
                "name": "Requests",
            }
        ],
        layout={"yaxis": {"title": "requests"}},
    )


def _bot_session_chart(sessions: pl.DataFrame) -> str:
    if sessions.is_empty():
        return hint("No sessions yet.")
    s = sessions.with_columns(pl.col("start").dt.truncate("1d").alias("day"))
    pivot = s.group_by(["day", "bot_class"]).agg(pl.len().alias("n")).sort("day")
    classes = pivot["bot_class"].unique().to_list()
    traces = []
    for cls in classes:
        sub = pivot.filter(pl.col("bot_class") == cls)
        traces.append(
            {
                "x": sub["day"].cast(pl.String).to_list(),
                "y": sub["n"].to_list(),
                "name": cls,
                "type": "bar",
                "marker": {"color": BOT_CLASS_COLORS.get(cls, "#cdd6f4")},
            }
        )
    return plotly_div(
        "bot-stack",
        traces,
        layout={"barmode": "stack", "yaxis": {"title": "sessions"}},
    )
