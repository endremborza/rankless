"""Grounding tools: verify a drafted answer's numbers, report what was missing.

`verify_claims` re-issues every claim through the same tool functions and
returns the fact record the offline miners store — `{tool, args, path,
claimed}` plus `{reproduced, ok, error}` — so a live session and an offline run
are verified in one format. A claim cites a receipt id or restates the call;
`path` is dotted, relative to the response `data`.
"""

from typing import Any

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from mcp_server import receipts, verify


class Claim(BaseModel):
    label: str = Field(description="what the number is, in a few words")
    claimed: Any = Field(description="the value as read from data, unformatted")
    path: str = Field(
        description="dotted path into the response data, e.g. windowPapers, "
        "topSubfields[0].citations, papers[1].year"
    )
    receipt: str | None = Field(
        default=None, description="receipt id of the response the number came from"
    )
    tool: str | None = Field(
        default=None, description="tool name, when no receipt is cited"
    )
    args: dict[str, Any] | None = Field(
        default=None, description="the tool's arguments, when no receipt is cited"
    )


async def verify_claims(claims: list[Claim], ctx: Context) -> dict:
    """Re-issue every number you are about to state; fix any that fail first.

    Each claim names a value and where it came from: the receipt id of an
    earlier response plus a dotted `path` into its `data` (or an explicit
    `tool` + `args`). Returns the claims with `reproduced`, `ok` and `error`
    filled in; the reproduced value is the one to publish. Derived numbers
    (ratios, ranks, sums) cannot be re-issued: verify their inputs instead.
    """
    session = receipts.session_key(ctx)
    log = receipts.session_log(session)
    facts = [_fact(claim, log) for claim in claims]
    await verify.verify_facts([f for f in facts if "error" not in f])
    for fact in facts:
        fact.setdefault("reproduced", None)
        fact.setdefault("ok", False)
    failed = sum(1 for f in facts if not f["ok"])
    result = {"claims": facts, "verified": len(facts) - failed, "failed": failed}
    receipts.log_event(session, "verify", result)
    return result


async def suggest_endpoint(need: str, why: str, question: str, ctx: Context) -> dict:
    """Record a capability the tools lacked for this question.

    Call it whenever an answer stays incomplete because no tool could supply
    something: an aggregation, a filter, a time window, a relation. `need` is
    the missing endpoint or tool in one line, `why` what it would have
    unlocked, `question` the user's question verbatim. Suggestions are
    reviewed and order the roadmap.
    """
    session = receipts.session_key(ctx)
    receipts.log_event(
        session, "suggest", {"need": need, "why": why, "question": question}
    )
    return {"recorded": bool(receipts.LOG_DIR)}


def _fact(claim: Claim, log: receipts.SessionLog) -> dict:
    fact = claim.model_dump()
    if claim.claimed is None:
        fact["error"] = "a claim states the value it verifies"
    elif claim.receipt:
        source = log.resolve(claim.receipt)
        if source is None:
            fact["error"] = f"no receipt {claim.receipt!r} in this session"
        else:
            fact["tool"], fact["args"] = source["tool"], source["args"]
    elif not claim.tool:
        fact["error"] = "a claim names a receipt or a tool"
    return fact


GROUNDING_TOOLS = (verify_claims, suggest_endpoint)
