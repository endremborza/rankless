import collections
import json

import polars as pl

from .. import classify
from .base import RenderContext, plotly_div, render_template, write


def render(ctx: RenderContext) -> None:
    rule_stats = _rule_stats(ctx.sessions_table)
    write(
        ctx,
        "classification.html",
        render_template(
            ctx,
            "classification.html.j2",
            active_page="classification",
            depth=0,
            bot_classes=[
                (cls, classify.BOT_CLASS_COLORS[cls])
                for cls in classify.BOT_CLASS_ORDER
            ],
            ua_families=[
                {
                    "name": fam.name,
                    "pattern": fam.pattern.pattern,
                    "side": "bot" if fam.is_bot else "browser",
                }
                for fam in classify.UA_FAMILIES
            ],
            hard_bot_rules=[r for r in classify.HARD_RULES if r.side == "bot"],
            hard_human_rules=[r for r in classify.HARD_RULES if r.side == "human"],
            soft_rules=classify.SOFT_RULES,
            soft_human_threshold=classify.SOFT_HUMAN_THRESHOLD,
            soft_bot_threshold=classify.SOFT_BOT_THRESHOLD,
            route_groups=[
                ("Bot-only routes", sorted(classify.ROUTE_HARD_BOT)),
                ("Hard-human POST routes", sorted(classify.ROUTE_HARD_HUMAN_POST)),
                ("Hard-human GET routes", sorted(classify.ROUTE_HARD_HUMAN_GET)),
                ("HTML page routes", sorted(classify.ROUTE_HTML_PAGES)),
                ("Browser-asset routes", sorted(classify.ROUTE_BROWSER_ASSETS)),
                (
                    "SvelteKit data prefetch routes",
                    sorted(classify.ROUTE_SVELTEKIT_DATA),
                ),
            ],
            search_route=classify.ROUTE_SEARCH,
            hard_rule_rates=rule_stats["hard"],
            soft_rule_rates=rule_stats["soft"],
            score_dist_chart=rule_stats["score_dist_chart"],
            n_sessions=rule_stats["n_sessions"],
        ),
    )


def _rule_stats(sessions: pl.DataFrame) -> dict:
    if sessions.is_empty() or "signals_json" not in sessions.columns:
        return {"hard": {}, "soft": {}, "score_dist_chart": "", "n_sessions": 0}

    n = len(sessions)
    hard_counts: dict[str, int] = {}
    soft_counts: dict[str, int] = {}
    scores: list[int] = []

    for sig_json in sessions["signals_json"].fill_null("[]").to_list():
        try:
            sigs = json.loads(sig_json)
        except (json.JSONDecodeError, TypeError):
            sigs = []
        for sig in sigs:
            if sig.startswith("hard:"):
                name = sig[5:]
                hard_counts[name] = hard_counts.get(name, 0) + 1
            elif sig.startswith("soft:score="):
                try:
                    scores.append(int(sig[11:]))
                except ValueError:
                    pass
            elif sig.startswith("soft:"):
                parts = sig[5:].split(" ", 1)
                if len(parts) == 2:
                    name = parts[1]
                    soft_counts[name] = soft_counts.get(name, 0) + 1

    return {
        "hard": {k: v / n for k, v in hard_counts.items()},
        "soft": {k: v / n for k, v in soft_counts.items()},
        "score_dist_chart": _score_dist_chart(scores) if scores else "",
        "n_sessions": n,
    }


def _score_dist_chart(scores: list[int]) -> str:
    counts = collections.Counter(scores)
    xs = sorted(counts)
    bot_thresh = classify.SOFT_BOT_THRESHOLD
    human_thresh = classify.SOFT_HUMAN_THRESHOLD
    return plotly_div(
        "score-dist",
        [
            {
                "x": xs,
                "y": [counts[s] for s in xs],
                "type": "bar",
                "marker": {"color": "#89b4fa"},
                "name": "sessions",
            }
        ],
        layout={
            "xaxis": {"title": "soft score", "dtick": 1},
            "yaxis": {"title": "sessions"},
            "shapes": [
                {
                    "type": "line",
                    "x0": human_thresh - 0.5,
                    "x1": human_thresh - 0.5,
                    "y0": 0,
                    "y1": 1,
                    "yref": "paper",
                    "line": {"color": "#a6e3a1", "dash": "dot", "width": 1.5},
                },
                {
                    "type": "line",
                    "x0": bot_thresh + 0.5,
                    "x1": bot_thresh + 0.5,
                    "y0": 0,
                    "y1": 1,
                    "yref": "paper",
                    "line": {"color": "#f38ba8", "dash": "dot", "width": 1.5},
                },
            ],
        },
        height=260,
    )
