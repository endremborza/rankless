import pandas as pd

from .base import RenderContext, df_to_html, hint, plotly_div, render_template, write


def _qtile(q: float):
    def _agg(s: pd.Series) -> float:
        return float(s.quantile(q)) if s.notna().any() else float("nan")
    return _agg


def render(ctx: RenderContext) -> None:
    write(ctx, "performance.html", render_template(
        ctx, "performance.html.j2",
        active_page="performance", depth=0,
        route_table=_route_table(ctx.events_24h),
        p99_chart=_p99_per_route_chart(ctx.hourly),
        cache_chart=_cache_hit_chart(ctx.hourly),
        slow_table=_slow_requests(ctx.events_24h),
    ))


def _route_table(events: pd.DataFrame) -> str:
    if events.empty:
        return hint("No data.")
    e = events.assign(
        is_5xx=events["status"] >= 500,
        is_4xx=(events["status"] >= 400) & (events["status"] < 500),
        is_hit=events["cs"] == "HIT",
    )
    g = (
        e.groupby("route_template")
        .agg(
            n=("status", "count"),
            urt_p50=("urt", _qtile(0.5)),
            urt_p95=("urt", _qtile(0.95)),
            urt_p99=("urt", _qtile(0.99)),
            err_5xx=("is_5xx", "mean"),
            err_4xx=("is_4xx", "mean"),
            cache_hit=("is_hit", "mean"),
        )
        .reset_index()
        .sort_values("n", ascending=False)
    )
    return (
        g.assign(**{f"{c}_ms": (g[c] * 1000).round(1) for c in ("urt_p50", "urt_p95", "urt_p99")})
        .drop(columns=["urt_p50", "urt_p95", "urt_p99"])
        .assign(**{c: (g[c] * 100).round(2) for c in ("err_5xx", "err_4xx", "cache_hit")})
        .pipe(df_to_html, table_id="route-perf")
    )


def _p99_per_route_chart(hourly: pd.DataFrame) -> str:
    if hourly.empty:
        return hint("No data.")
    cutoff = hourly["bucket"].max() - pd.Timedelta(days=1)
    s = hourly[hourly["bucket"] >= cutoff]
    if s.empty:
        return hint("No recent hourly data.")
    top = s.groupby("route_template")["n"].sum().nlargest(8).index
    g = (
        s[s["route_template"].isin(top)]
        .groupby(["bucket", "route_template"])
        .agg(urt_p99=("urt_p99", "max"))
        .reset_index()
    )
    traces = [
        {
            "x": list(gd["bucket"].astype(str)),
            "y": [v * 1000 if pd.notna(v) else None for v in gd["urt_p99"]],
            "name": str(route),
            "type": "scatter",
            "mode": "lines",
        }
        for route, gd in g.groupby("route_template")
    ]
    return plotly_div("p99-routes", traces, layout={"yaxis": {"title": "p99 ms"}})


def _cache_hit_chart(hourly: pd.DataFrame) -> str:
    if hourly.empty:
        return hint("No data.")
    cutoff = hourly["bucket"].max() - pd.Timedelta(days=7)
    s = hourly[hourly["bucket"] >= cutoff]
    g = (
        s.groupby("bucket")
        .apply(
            lambda d: pd.Series({
                "hit_pct": d.loc[d["cs"] == "HIT", "n"].sum() / max(d["n"].sum(), 1) * 100,
            }),
            include_groups=False,
        )
        .reset_index()
    )
    return plotly_div(
        "cache-hit",
        [{
            "x": list(g["bucket"].astype(str)),
            "y": list(g["hit_pct"]),
            "type": "scatter",
            "mode": "lines",
            "fill": "tozeroy",
            "line": {"color": "#89b4fa"},
            "name": "cache hit %",
        }],
        layout={"yaxis": {"title": "cache hit %", "range": [0, 100]}},
    )


def _slow_requests(events: pd.DataFrame) -> str:
    if events.empty:
        return hint("No data.")
    cols = [c for c in ("t", "route_template", "status", "urt", "cs", "size") if c in events.columns]
    s = (
        events.dropna(subset=["urt"])
        .sort_values("urt", ascending=False)
        .head(100)
        [cols]
    )
    if "urt" in s.columns:
        s = s.assign(urt_ms=(s["urt"] * 1000).round(1)).drop(columns=["urt"])
    return df_to_html(s, table_id="slow-reqs")
