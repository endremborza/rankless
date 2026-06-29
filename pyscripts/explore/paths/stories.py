"""Stories path: shareable, data-grounded narratives from the entity snapshots."""

from pyscripts.explore import PathResult, cli, evidence

NAME = "stories"
SAMPLE = 20  # random slice each run keeps the stories fresh
SHARE_ORDER = ["high", "medium", "low"]

SYSTEM_PROMPT = """\
You are a science-communication writer for Rankless, a scholarly citation
explorer. From the given entity-page snapshots, surface genuinely interesting,
TRUE, shareable stories - surprising facts, notable rankings, striking anomalies,
or human-interest angles - that a curious audience would enjoy.

Hard rules:
- Every claim must be grounded in the provided snapshot data. Do not invent
  numbers, names, or facts that are not present.
- Prefer the surprising and specific over the generic.
- A story rooted in a data quirk (e.g. an oddly attributed famous paper) is fine
  - frame it honestly.

Respond ONLY with a JSON array; each element:
{"headline": "punchy title", "story": "2-4 sentences, shareable",
 "entities": ["<page url>", ...], "shareability": "high|medium|low"}
Do not wrap the response in markdown code fences."""


def run(snapshots: list[dict], model: str) -> PathResult:
    print(f"[{NAME}] mining {len(snapshots)} entities with {model}...")
    stories = cli.parse_json_array(
        cli.query_claude_cli(
            SYSTEM_PROMPT, evidence.build_evidence_prompt(snapshots), model
        )
    )

    print(f"[{NAME}] {len(stories)} story(ies).")
    return PathResult(section=_section(stories, snapshots))


def _section(stories: list[dict], snapshots: list[dict]) -> str:
    out = [
        "## Stories — shareable findings",
        "",
        f"**{len(stories)} story(ies)** from {len(snapshots)} entity snapshots, "
        "grouped by shareability. Claims are grounded in the snapshot data.",
        "",
    ]
    for share in SHARE_ORDER:
        group = [s for s in stories if s.get("shareability") == share]
        if not group:
            continue
        out += [f"### Shareability: {share} ({len(group)})", ""]
        for story in group:
            entities = ", ".join(f"`{e}`" for e in story.get("entities", []))
            out += [
                f"#### {story.get('headline', 'Untitled')}",
                "",
                story.get("story", ""),
                "",
                f"_Entities: {entities or '—'}_",
                "",
            ]
    return "\n".join(out)
