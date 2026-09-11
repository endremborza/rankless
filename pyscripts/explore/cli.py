"""Claude Code CLI runner + response parsing shared by all explore paths."""

import json
import subprocess

MODELS = {
    "sonnet": "claude-sonnet-4-6",
    "sonnet-5": "claude-sonnet-5",
    "opus": "claude-opus-4-8",
}
DEFAULT_MODEL = "sonnet"
CLI_TIMEOUT_S = 600


def resolve_model(name: str) -> str:
    return MODELS.get(name, name)


def query_claude_cli(
    system: str,
    user: str,
    model: str,
    *,
    allowed_tools: str = "",
    mcp_config: str | None = None,
    max_turns: int | None = None,
    timeout_s: int = CLI_TIMEOUT_S,
    stats: dict | None = None,
) -> str:
    """Run one prompt through the Claude Code CLI and return its text response.

    Headless `-p` with tools disabled by default means no permission prompt can
    block the run; the timeout is a hard backstop so a stalled CLI can never
    hang. Uses the local `claude` CLI auth, so no ANTHROPIC_API_KEY is needed.
    Pass `mcp_config` (inline JSON) plus an `allowed_tools` rule (e.g.
    "mcp__rankless") for an agentic run with MCP tools. Pass `stats` to receive
    the call's usage (`seconds`, `output_tokens`, `thinking_tokens`, `usd`)
    from the CLI's JSON envelope.
    """
    cmd = [
        "claude",
        "-p",
        "--model",
        model,
        "--system-prompt",
        system,
        "--allowedTools",
        allowed_tools,
        "--output-format",
        "text" if stats is None else "json",
    ]
    if mcp_config:
        cmd += ["--mcp-config", mcp_config, "--strict-mcp-config"]
    if max_turns:
        cmd += ["--max-turns", str(max_turns)]
    try:
        proc = subprocess.run(
            cmd,
            input=user,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"claude CLI timed out after {timeout_s}s") from exc
    if proc.returncode != 0:
        # limit/quota refusals land on stdout with an empty stderr
        detail = proc.stderr.strip() or proc.stdout.strip()
        msg = f"claude exited {proc.returncode}"
        raise RuntimeError(f"{msg}: {detail[-400:]}" if detail else msg)
    if stats is None:
        return proc.stdout.strip()
    return unwrap_result(proc.stdout, stats)


def unwrap_result(raw: str, stats: dict) -> str:
    """The text of a `--output-format json` envelope, with its usage recorded
    into `stats`."""
    envelope = json.loads(raw)
    if envelope.get("is_error"):
        raise RuntimeError(
            f"claude reported an error: {str(envelope.get('result', ''))[-400:]}"
        )
    usage = envelope.get("usage") or {}
    stats.update(
        seconds=envelope.get("duration_ms", 0) / 1000,
        output_tokens=usage.get("output_tokens", 0),
        thinking_tokens=(usage.get("output_tokens_details") or {}).get(
            "thinking_tokens", 0
        ),
        usd=envelope.get("total_cost_usd", 0.0),
    )
    return str(envelope.get("result", "")).strip()


def parse_json(raw: str):
    """Parse a JSON response, tolerating a code fence or agent narration.

    Agentic sessions often prepend "thinking out loud" prose before the JSON
    payload, so on a direct failure we scan for the first embedded object/array
    that decodes cleanly to the end of the string.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return _extract_json(raw)


def _extract_json(raw: str):
    """Best embedded JSON: prefer one that runs to end-of-string, else longest."""
    decoder = json.JSONDecoder()
    best, best_len = None, -1
    for i, ch in enumerate(raw):
        if ch not in "{[":
            continue
        try:
            obj, end = decoder.raw_decode(raw, i)
        except json.JSONDecodeError:
            continue
        if raw[end:].strip() == "":
            return obj
        if end - i > best_len:
            best, best_len = obj, end - i
    if best is None:
        raise json.JSONDecodeError("no JSON value found", raw, 0)
    return best


def parse_json_array(raw: str) -> list[dict]:
    """Parse a JSON-array response, tolerating a wrapping markdown code fence."""
    return parse_json(raw)
