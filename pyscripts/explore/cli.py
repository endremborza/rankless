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


def query_claude_cli(system: str, user: str, model: str) -> str:
    """Run one prompt through the Claude Code CLI and return its text response.

    Headless `-p` with tools disabled means no permission prompt can block the
    run; the timeout is a hard backstop so a stalled CLI can never hang. Uses the
    local `claude` CLI auth, so no ANTHROPIC_API_KEY is needed.
    """
    try:
        proc = subprocess.run(
            [
                "claude",
                "-p",
                "--model",
                model,
                "--system-prompt",
                system,
                "--allowedTools",
                "--output-format",
                "text",
            ],
            input=user,
            capture_output=True,
            text=True,
            check=False,
            timeout=CLI_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"claude CLI timed out after {CLI_TIMEOUT_S}s") from exc
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"claude exited {proc.returncode}")
    return proc.stdout.strip()


def parse_json_array(raw: str) -> list[dict]:
    """Parse a JSON-array response, tolerating a wrapping markdown code fence."""
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return json.loads(raw)
