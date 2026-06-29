"""LLM-based sanity check for entity page data.

Reads logs/sanity_check_data.json (produced by tests/sanity-data.spec.ts),
sends entity snapshots to Claude for semantic validation, reports issues.
"""

import json
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

DATA_PATH = Path("logs/sanity_check_data.json")

SYSTEM_PROMPT = """\
You are a data quality reviewer for a scholarly citation explorer called Rankless.
It displays entity pages for authors, institutions, journals (sources), countries,
subfields, and hit-papers. Each page shows specialization fields, top co-authors,
top journals, citing fields, citation stats, and a generated about paragraph.

You will receive structured snapshots of entity pages. For each, check:

1. FACTUAL COHERENCE: Do the specialization fields, top journals, co-authors,
   and cited-by fields make sense together? Flag if a leader row item is obviously
   unrelated to the entity's domain (e.g., an economics professor listing a marine
   biology journal as a top journal).

2. DATA ANOMALIES: Are the citation/paper counts plausible? Any zeros or extreme
   outliers that suggest data pipeline errors?

3. TEXT QUALITY: Any garbled names, encoding artifacts (mojibake), or obvious
   spelling errors in entity names, field names, or about text?

For entities marked with "expectedDomain", pay special attention to whether the
displayed data matches that domain.

Respond ONLY with a JSON array of issues found. Each issue must be an object with:
{"entity": "<name or url>", "severity": "critical|warning|info", \
"category": "coherence|anomaly|text", "description": "..."}

Return an empty array [] if everything looks correct.
Do NOT wrap the response in markdown code fences — return raw JSON only."""


def build_user_prompt(snapshots: list[dict]) -> str:
    lines = ["Entity page snapshots to review:\n"]
    for i, snap in enumerate(snapshots, 1):
        lines.append(f"--- Entity {i} ---")
        lines.append(f"URL: {snap['url']}")
        lines.append(f"Root Type: {snap['rootType']}")
        lines.append(f"Name: {snap['name']}")
        lines.append(f"Stats: {snap['stats']}")
        if snap.get("expectedDomain"):
            lines.append(f"Expected Domain: {snap['expectedDomain']}")
        if snap.get("fields"):
            lines.append(f"Fields: {', '.join(snap['fields'])}")
        if snap.get("leaders"):
            for leader in snap["leaders"]:
                items = ", ".join(leader["items"])
                lines.append(f"  {leader['label']}: {items}")
        if snap.get("aboutText"):
            lines.append(f"About: {snap['aboutText'][:500]}")
        lines.append("")
    return "\n".join(lines)


def run() -> int:
    load_dotenv()
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found. Run the Playwright test first.")
        return 1

    snapshots = json.loads(DATA_PATH.read_text())
    if not snapshots:
        print("No entity snapshots found in data file.")
        return 1

    print(f"Analyzing {len(snapshots)} entity snapshots...")

    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(snapshots)}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        issues = json.loads(raw)
    except json.JSONDecodeError:
        print(f"ERROR: Failed to parse LLM response as JSON:\n{raw[:500]}")
        return 1

    if not issues:
        print("All entities passed sanity check.")
        return 0

    critical_count = 0
    for issue in issues:
        severity = issue.get("severity", "info").upper()
        category = issue.get("category", "?")
        entity = issue.get("entity", "?")
        desc = issue.get("description", "")
        marker = {"CRITICAL": "!!", "WARNING": "?!", "INFO": "--"}.get(severity, "--")
        print(f"  [{marker}] {severity} ({category}) {entity}: {desc}")
        if severity == "CRITICAL":
            critical_count += 1

    print(f"\n{len(issues)} issue(s) found, {critical_count} critical.")
    return 1 if critical_count > 0 else 0


if __name__ == "__main__":
    sys.exit(run())
