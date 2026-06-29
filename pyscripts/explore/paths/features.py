"""Features path: feature proposals grounded in the data and .cril/ideas.md."""

from pyscripts.explore import PathResult, cli, evidence

NAME = "features"
SAMPLE = 20  # a diverse random slice is enough to spot gaps
EFFORT_ORDER = ["S", "M", "L"]

SYSTEM_PROMPT = """\
You are a product strategist for Rankless, a large-scale scholarly citation
explorer. You are given (a) snapshots of live entity pages and (b) the project's
forward vision (.cril/ideas.md) - turning Rankless into an agent-driven academic
question-answerer (validated data + composable dashboards + MCP).

Propose concrete, high-leverage features. Prefer ideas that either advance the
vision (new endpoints, dashboard panels, MCP tools, agent recipes) or address a
real gap/opportunity visible in the entity snapshots. Every proposal must be
grounded in the snapshots or the vision - no generic filler.

Respond ONLY with a JSON array; each element:
{"title": "...", "category": "endpoint|panel|agent|mcp|data|ux|other",
 "rationale": "what it unlocks / why it matters",
 "evidence": "the snapshot detail or ideas.md section motivating it",
 "relates_to": "<ideas.md section number, or 'new'>", "effort": "S|M|L"}
Do not wrap the response in markdown code fences."""


def run(snapshots: list[dict], model: str) -> PathResult:
    print(f"[{NAME}] ideating over {len(snapshots)} entities with {model}...")
    prompt = evidence.build_evidence_prompt(snapshots)
    vision = evidence.load_vision()
    if vision:
        prompt += "\n\n## Project vision (.cril/ideas.md)\n\n" + vision
    ideas = cli.parse_json_array(cli.query_claude_cli(SYSTEM_PROMPT, prompt, model))

    print(f"[{NAME}] {len(ideas)} proposal(s).")
    return PathResult(section=_section(ideas, snapshots))


def _section(ideas: list[dict], snapshots: list[dict]) -> str:
    out = [
        "## Features — proposals",
        "",
        f"**{len(ideas)} proposal(s)** from {len(snapshots)} entity snapshots + "
        "`.cril/ideas.md`, grouped by effort (S/M/L). Each cites the snapshot "
        "detail or ideas.md section that motivates it.",
        "",
    ]
    buckets = {e: [i for i in ideas if i.get("effort") == e] for e in EFFORT_ORDER}
    buckets["unspecified"] = [i for i in ideas if i.get("effort") not in EFFORT_ORDER]
    for label, group in buckets.items():
        if not group:
            continue
        out += [f"### Effort: {label} ({len(group)})", ""]
        for idea in group:
            out += [
                f"#### {idea.get('title', 'Untitled')}  `{idea.get('category', '?')}`",
                "",
                f"- **Rationale:** {idea.get('rationale', '')}",
                f"- **Evidence:** {idea.get('evidence', '')}",
                f"- **Relates to:** {idea.get('relates_to', 'new')}",
                "",
            ]
    return "\n".join(out)
