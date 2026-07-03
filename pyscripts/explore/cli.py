"""Claude Code CLI runner + response parsing shared by all explore paths."""

import json
import subprocess

MODELS = {
    "sonnet": "claude-sonnet-4-6",
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
) -> str:
    """Run one prompt through the Claude Code CLI and return its text response.

    Headless `-p` with tools disabled by default means no permission prompt can
    block the run; the timeout is a hard backstop so a stalled CLI can never
    hang. Uses the local `claude` CLI auth, so no ANTHROPIC_API_KEY is needed.
    Pass `mcp_config` (inline JSON) plus an `allowed_tools` rule (e.g.
    "mcp__rankless") for an agentic run with MCP tools.
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
        "text",
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
        raise RuntimeError(proc.stderr.strip() or f"claude exited {proc.returncode}")
    return proc.stdout.strip()


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
