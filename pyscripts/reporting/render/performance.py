import pandas as pd

from .base import RenderContext, plotly_div, render_template, write


def render(ctx: RenderContext) -> None:
    events = ctx.events_24h
    hourly = ctx.hourly

    route_table = _route_table(events)
    p99_chart = _p99_per_route_chart(hourly)
    cache_chart = _cache_hit_chart(hourly)
    slow_table = _slow_requests(events)

    html = render_template(
        ctx,
        "performance.html.j2",
        active_page="performance",
        depth=0,
        route_table=route_table,
        p99_chart=p99_chart,
        cache_chart=cache_chart,
        slow_table=slow_table,
    )
    write(ctx, "performance.html", html)


def _route_table(events: pd.DataFrame) -> str:
    if events.empty:
        return "<p class='hint'>No data.</p>"
    e = events.copy()
    e["is_5xx"] = e["status"] >= 500
    e["is_4xx"] = (e["status"] >= 400) & (e["status"] < 500)
    e["is_hit"] = e["cs"] == "HIT"
    g = e.groupby("route_template").agg(
        n=("status", "count"),
        urt_p50=("urt", lambda s: float(s.quantile(0.5)) if s.notna().any() else float("nan")),
        urt_p95=("urt", lambda s: float(s.quantile(0.95)) if s.notna().any() else float("nan")),
        urt_p99=("urt", lambda s: float(s.quantile(0.99)) if s.notna().any() else float("nan")),
        err_5xx=("is_5xx", "mean"),
        err_4xx=("is_4xx", "mean"),
        cache_hit=("is_hit", "mean"),
    ).reset_index().sort_values("n", ascending=False)
    for c in ("urt_p50", "urt_p95", "urt_p99"):
        g[c] = (g[c] * 1000).round(1)
        g.rename(columns={c: c + "_ms"}, inplace=True)
    for c in ("err_5xx", "err_4xx", "cache_hit"):
        g[c] = (g[c] * 100).round(2)
    return g.to_html(classes="dt", index=False, table_id="route-perf", border=0)


def _p99_per_route_chart(hourly: pd.DataFrame) -> str:
    if hourly.empty:
        return "<p class='hint'>No data.</p>"
    cutoff = hourly["bucket"].max() - pd.Timedelta(days=1)
    s = hourly[hourly["bucket"] >= cutoff].copy()
    if s.empty:
        return "<p class='hint'>No recent hourly data.</p>"
    weighted = s.groupby("route_template")["n"].sum().nlargest(8).index
    s = s[s["route_template"].isin(weighted)]
    g = (
        s.groupby(["bucket", "route_template"])
        .agg(urt_p99=("urt_p99", "max"))
        .reset_index()
    )
    traces = []
    for route, gd in g.groupby("route_template"):
        traces.append(
            {
                "x": list(gd["bucket"].astype(str)),
                "y": [v * 1000 if pd.notna(v) else None for v in gd["urt_p99"]],
                "name": str(route),
                "type": "scatter",
                "mode": "lines",
            }
        )
    return plotly_div("p99-routes", traces, layout={"yaxis": {"title": "p99 ms"}})


def _cache_hit_chart(hourly: pd.DataFrame) -> str:
    if hourly.empty:
        return "<p class='hint'>No data.</p>"
    cutoff = hourly["bucket"].max() - pd.Timedelta(days=7)
    s = hourly[hourly["bucket"] >= cutoff].copy()
    g = s.groupby("bucket").apply(
        lambda d: pd.Series(
            {
                "hit_pct": (d.loc[d["cs"] == "HIT", "n"].sum() / max(d["n"].sum(), 1)) * 100
            }
        ),
        include_groups=False,
    ).reset_index()
    return plotly_div(
        "cache-hit",
        [
            {
                "x": list(g["bucket"].astype(str)),
                "y": list(g["hit_pct"]),
                "type": "scatter",
                "mode": "lines",
                "fill": "tozeroy",
                "line": {"color": "#89b4fa"},
                "name": "cache hit %",
            }
        ],
        layout={"yaxis": {"title": "cache hit %", "range": [0, 100]}},
    )


def _slow_requests(events: pd.DataFrame) -> str:
    if events.empty:
        return "<p class='hint'>No data.</p>"
    s = events.dropna(subset=["urt"]).sort_values("urt", ascending=False).head(100)
    cols = ["t", "route_template", "status", "urt", "cs", "size"]
    cols = [c for c in cols if c in s.columns]
    out = s[cols].copy()
    if "urt" in out.columns:
        out["urt_ms"] = (out["urt"] * 1000).round(1)
        out = out.drop(columns=["urt"])
    return out.to_html(classes="dt", index=False, table_id="slow-reqs", border=0)
