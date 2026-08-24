"""Deterministic re-issue of model-cited MCP tool calls.

A metric is `{tool, args, path, claimed}`; `reissue` replays the call through
`TOOL_FNS` and walks the dotted path, so the reproduced value — not the model's
text — is what gets published.
"""

import re

import httpx

from mcp_server.tools import TOOL_FNS

PATH_TOKEN_RE = re.compile(r"\.?([^.\[\]]+)|\[(\d+)\]")


def tool_name(tool: str) -> str:
    """Bare tool name, stripping any `mcp__<server>__` prefix the agent used."""
    return tool.split("__")[-1] if tool.startswith("mcp__") else tool


async def verify_facts(facts: list[dict]) -> list[dict]:
    """Re-issue every fact in place (tool normalized, `reproduced`/`error`/`ok`
    set); returns the facts that failed to reproduce."""
    for fact in facts:
        fact["tool"] = tool_name(fact.get("tool", ""))
        fact["reproduced"], fact["error"] = await reissue(fact)
        fact["ok"] = metric_ok(fact)
    return [f for f in facts if not f["ok"]]


async def reissue(metric: dict) -> tuple[object, str | None]:
    fn = TOOL_FNS.get(metric.get("tool", ""))
    if fn is None:
        return None, f"unknown tool {metric.get('tool')!r}"
    try:
        result = await fn(**metric.get("args", {}))
        return walk(result, metric.get("path", "")), None
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def metric_ok(metric: dict) -> bool:
    if metric["error"]:
        return False
    claimed = metric.get("claimed")
    if claimed is None:
        return True
    return values_match(metric["reproduced"], claimed)


def walk(obj, path: str):
    for name, idx in PATH_TOKEN_RE.findall(path):
        obj = obj[int(idx)] if idx else obj[name]
    return obj


def values_match(actual, expected) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return float(actual) == float(expected)
    return actual == expected
