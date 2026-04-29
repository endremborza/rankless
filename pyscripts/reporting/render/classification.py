from .. import classify
from .base import RenderContext, render_template, write


def render(ctx: RenderContext) -> None:
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
            ],
            search_route=classify.ROUTE_SEARCH,
        ),
    )
