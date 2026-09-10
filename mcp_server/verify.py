"""Deterministic re-issue of model-cited tool calls.

A fact is `{tool, args, path, claimed}`; `reissue` replays the call through
`TOOL_FNS` and walks the dotted path, so the reproduced value — not the model's
text — is what gets published. The same record, with `reproduced`/`ok`/`error`
filled in, is what the `verify_claims` tool returns to a live session and what
the offline miners store, so every verified number has one shape.
"""

import json
import re

import httpx

from mcp_server.tools import TOOL_FNS

PATH_TOKEN_RE = re.compile(r"\.?([^.\[\]]+)|\[(\d+)\]")
DATA_PREFIX_RE = re.compile(r"^data(?:\.|(?=\[)|$)")


def tool_name(tool: str) -> str:
    """Bare tool name, stripping any `mcp__<server>__` prefix the agent used."""
    return tool.split("__")[-1] if tool.startswith("mcp__") else tool


async def verify_facts(
    facts: list[dict], calls: dict[str, object] | None = None
) -> list[dict]:
    """Re-issue every fact in place (tool normalized, `reproduced`/`error`/`ok`
    set), one backend call per distinct tool + args; returns the facts that
    failed to reproduce. Pass `calls` to share the memo across batches."""
    if calls is None:
        calls = {}
    for fact in facts:
        fact["tool"] = tool_name(fact.get("tool", ""))
        fact["reproduced"], fact["error"] = await reissue(fact, calls)
        fact["ok"] = metric_ok(fact)
    return [f for f in facts if not f["ok"]]


async def reissue(metric: dict, calls: dict[str, object]) -> tuple[object, str | None]:
    """The value at the metric's path in the re-issued call; `calls` memoizes
    raw responses by tool + args across one batch."""
    tool = metric.get("tool") or ""
    fn = TOOL_FNS.get(tool)
    if fn is None:
        return None, f"unknown tool {tool!r}"
    args = metric.get("args") or {}
    key = f"{tool} {json.dumps(args, sort_keys=True)}"
    try:
        if key not in calls:
            calls[key] = await fn(**args)
        return walk(calls[key], data_path(metric.get("path") or "")), None
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def metric_ok(metric: dict) -> bool:
    if metric["error"]:
        return False
    claimed = metric.get("claimed")
    if claimed is None:
        return True
    return values_match(metric["reproduced"], claimed)


def data_path(path: str) -> str:
    """A path written against the `{receipt, data}` envelope, made relative to
    the bare tool result."""
    return DATA_PREFIX_RE.sub("", path)


def walk(obj, path: str):
    for name, idx in PATH_TOKEN_RE.findall(path):
        obj = obj[int(idx)] if idx else obj[name]
    return obj


def values_match(actual, expected) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return float(actual) == float(expected)
    return actual == expected
