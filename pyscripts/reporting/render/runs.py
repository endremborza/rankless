import pandas as pd

from .base import RenderContext, df_to_html, hint, render_template, write


def render(ctx: RenderContext) -> None:
    runs = ctx.runs_index
    if not runs:
        table_html = hint("No run history yet.")
    else:
        df = pd.DataFrame(runs)
        if "ts" in df.columns:
            df = df.assign(run=df["ts"].map(lambda t: f'<a href="{t}.html">{t}</a>'))
            ordered = ["run"] + [c for c in df.columns if c not in ("ts", "run")]
            df = df[ordered]
        table_html = df_to_html(df, table_id="runs", escape=False)

    write(ctx, "runs/index.html", render_template(
        ctx, "runs_index.html.j2",
        active_page="runs", depth=1,
        runs_table=table_html,
    ))

    for r in runs:
        ts = r.get("ts", "")
        if not ts:
            continue
        write(ctx, f"runs/{ts}.html", render_template(
            ctx, "run_detail.html.j2",
            active_page="runs", depth=1,
            run=r,
        ))
