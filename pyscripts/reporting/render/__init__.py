from .base import Mode, RenderContext, build_context
from . import classification, errors, landing, performance, runs, sessions, traffic


def render_all(mode: Mode = "local") -> RenderContext:
    ctx = build_context(mode)
    landing.render(ctx)
    traffic.render(ctx)
    performance.render(ctx)
    errors.render(ctx)
    sessions.render(ctx)
    classification.render(ctx)
    runs.render(ctx)
    return ctx
