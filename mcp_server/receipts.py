"""Receipts: every tool response names the call that produced it.

The response envelope is `{"receipt": {"id", "tool", "args"}, "data": ...}`.
A session's receipts are the record of what the model was handed, so a claim
can cite a receipt id instead of restating the call, and an answer can be
audited afterwards against calls that actually happened. Sessions are keyed by
the transport's `Mcp-Session-Id` (a local stdio proxy is one session); the
in-memory log is bounded, and every event is mirrored as one JSON line per day
under `MCP_LOG_DIR` when it is set (a call that raises is logged with its `error`).
"""

import inspect
import json
import os
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from mcp.server.fastmcp import Context

LOG_DIR = os.environ.get("MCP_LOG_DIR")
SESSION_CAP = 512
RECEIPT_CAP = 2000
STDIO_SESSION = "stdio"

ENVELOPE_NOTE = (
    "Response: {receipt: {id, tool, args}, data: ...}. Keep the receipt id with "
    "every number taken from data and pass it to verify_claims before answering."
)


class SessionLog:
    def __init__(self, key: str) -> None:
        self.key = key
        self.n = 0
        self.receipts: OrderedDict[str, dict] = OrderedDict()

    def record(self, tool: str, args: dict) -> dict:
        self.n += 1
        receipt = {"id": f"r{self.n}", "tool": tool, "args": args}
        self.receipts[receipt["id"]] = receipt
        while len(self.receipts) > RECEIPT_CAP:
            self.receipts.popitem(last=False)
        return receipt

    def resolve(self, receipt_id: str) -> dict | None:
        return self.receipts.get(receipt_id)


_logs: OrderedDict[str, SessionLog] = OrderedDict()


def session_log(key: str) -> SessionLog:
    log = _logs.get(key)
    if log is None:
        log = _logs[key] = SessionLog(key)
        while len(_logs) > SESSION_CAP:
            _logs.popitem(last=False)
    else:
        _logs.move_to_end(key)
    return log


def session_key(ctx: Context | None) -> str:
    request = ctx.request_context.request if ctx is not None else None
    if request is None:
        return STDIO_SESSION
    return request.headers.get("mcp-session-id") or STDIO_SESSION


def log_event(session: str, kind: str, payload: dict) -> None:
    if not LOG_DIR:
        return
    now = datetime.now(UTC)
    path = Path(LOG_DIR) / f"{now:%Y-%m-%d}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "session": session,
        "kind": kind,
        **payload,
    }
    with path.open("a") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def with_receipt(fn: Callable[..., Any]) -> Callable[..., Any]:
    """The MCP-registered form of a plain tool function: the same argument
    schema plus an injected Context, the result wrapped in the receipt envelope
    and the call logged to the session."""
    sig = inspect.signature(fn)

    async def wrapped(*args: Any, ctx: Context, **kwargs: Any) -> dict:
        call_args = dict(sig.bind(*args, **kwargs).arguments)
        session = session_key(ctx)
        receipt = session_log(session).record(fn.__name__, call_args)
        try:
            data = await fn(*args, **kwargs)
        except Exception as exc:
            log_event(
                session, "call", {**receipt, "error": f"{type(exc).__name__}: {exc}"}
            )
            raise
        log_event(session, "call", receipt)
        return {"receipt": receipt, "data": data}

    ctx_param = inspect.Parameter(
        "ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context
    )
    wrapped.__name__ = fn.__name__
    wrapped.__doc__ = f"{inspect.getdoc(fn)}\n\n{ENVELOPE_NOTE}"
    wrapped.__signature__ = sig.replace(  # pyright: ignore[reportFunctionMemberAccess]
        parameters=[*sig.parameters.values(), ctx_param], return_annotation=dict
    )
    wrapped.__annotations__ = {**fn.__annotations__, "ctx": Context, "return": dict}
    return wrapped
