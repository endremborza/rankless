import pandas as pd

from .base import RenderContext, render_template, write


def render(ctx: RenderContext) -> None:
    runs = ctx.runs_index
    if not runs:
        table_html = "<p class='hint'>No run history yet.</p>"
    else:
        df = pd.DataFrame(runs)
        if "ts" in df.columns:
            df["run"] = df["ts"].map(lambda t: f'<a href="{t}.html">{t}</a>')
            ordered = ["run"] + [c for c in df.columns if c not in ("ts", "run")]
            df = df[ordered]
        table_html = df.to_html(classes="dt", index=False, table_id="runs", border=0, escape=False)

    html = render_template(
        ctx,
        "runs_index.html.j2",
        active_page="runs",
        depth=1,
        runs_table=table_html,
    )
    write(ctx, "runs/index.html", html)

    for r in runs:
        ts = r.get("ts", "")
        if not ts:
            continue
        html = render_template(
            ctx,
            "run_detail.html.j2",
            active_page="runs",
            depth=1,
            run=r,
        )
        write(ctx, f"runs/{ts}.html", html)
