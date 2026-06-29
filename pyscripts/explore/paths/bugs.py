"""Bugs path: data-quality / correctness review of entity pages.

Each finding is classified `code` (a pipeline/frontend bug) or `data` (fixable
by correcting records the way a logged-in user would). Data findings also become
draft LedgerPayload events (same format ORCID users submit, src/lib/types/ledger.ts:
merge_authors/merge_papers/claim_paper/disown_paper/add_paper_request) — ids the
model cannot see are omitted and resolved downstream (.cril/ideas.md §3).
"""

from pyscripts.explore import PathResult, cli, evidence

NAME = "bugs"
SAMPLE = None  # review everything collected — bugs wants broad coverage
SEVERITY_ORDER = ["critical", "warning", "info"]

SYSTEM_PROMPT = """\
You are a data-quality reviewer for Rankless, a scholarly citation explorer with
entity pages for authors, institutions, journals (sources), countries, subfields,
and hit-papers. Each page shows specialization fields, top co-authors/scholars,
top journals, citing fields, citation stats, and a generated about paragraph.

Review the entity snapshots for:
1. FACTUAL COHERENCE - leader-row items unrelated to the entity's domain;
   mismatched fields/journals/citing-fields.
2. DATA ANOMALIES - implausible counts, duplicates, zeros, extreme outliers,
   wrong attributions.
3. TEXT QUALITY - garbled names, encoding artifacts/mojibake, missing spaces,
   wrong diacritics, spelling.
For entities with "Expected Domain", check the displayed data matches it.

Classify each finding's fix_type:
- "data": fixable by correcting the underlying records the way a logged-in user
  would. Set ledger_suggestion to the best-fitting action:
  * merge_authors - the same person appears as two author records (e.g. a name
    listed twice with different counts).
  * merge_papers - the same paper appears twice.
  * claim_paper / disown_paper - a paper wrongly attributed to / missing from an
    author.
  * add_paper_request - a paper is missing.
  Put a human note in `note` and any names/identifiers you can infer from the
  snapshot in `details`. Omit ids you cannot see; they are resolved downstream.
- "code": a pipeline/frontend bug (wrong topic mapping, name formatting/encoding,
  mislabeled research area). Set ledger_suggestion to null.

Respond ONLY with a JSON array; each element:
{"entity": "<page url>", "severity": "critical|warning|info",
 "category": "coherence|anomaly|text", "fix_type": "code|data",
 "description": "...",
 "ledger_suggestion": null | {"kind": "merge_authors|merge_papers|claim_paper|\
disown_paper|add_paper_request", "note": "...", "details": {...}}}
Return [] if nothing is wrong. Do not wrap the response in markdown code fences."""


def run(snapshots: list[dict], model: str) -> PathResult:
    print(f"[{NAME}] reviewing {len(snapshots)} entities with {model}...")
    raw = cli.query_claude_cli(
        SYSTEM_PROMPT, evidence.build_evidence_prompt(snapshots), model
    )
    issues = cli.parse_json_array(raw)
    suggestions = [
        {
            **i["ledger_suggestion"],
            "_entity": i.get("entity"),
            "_why": i.get("description"),
        }
        for i in issues
        if i.get("fix_type") == "data" and i.get("ledger_suggestion")
    ]

    critical = sum(1 for i in issues if i.get("severity", "").lower() == "critical")
    print(
        f"[{NAME}] {len(issues)} issue(s), {critical} critical, "
        f"{len(suggestions)} ledger suggestion(s)."
    )
    return PathResult(
        section=_section(issues, snapshots, len(suggestions)),
        exit_code=1 if critical else 0,
        suggestions=suggestions,
    )


def _section(issues: list[dict], snapshots: list[dict], n_sug: int) -> str:
    by_url = {s["url"]: s for s in snapshots}
    grouped: dict[str, list[dict]] = {sev: [] for sev in SEVERITY_ORDER}
    for issue in issues:
        grouped.setdefault(issue.get("severity", "info").lower(), []).append(issue)
    counts = {sev: len(items) for sev, items in grouped.items()}
    n_data = sum(1 for i in issues if i.get("fix_type") == "data")
    n_code = sum(1 for i in issues if i.get("fix_type") == "code")

    out = [
        "## Bugs — data-quality review",
        "",
        f"Reviewed **{len(snapshots)}** entity pages — **{len(issues)}** issue(s): "
        f"{counts.get('critical', 0)} critical, {counts.get('warning', 0)} warning, "
        f"{counts.get('info', 0)} info ({n_code} code, {n_data} data; "
        f"{n_sug} ledger suggestion(s)).",
        "",
        "Findings are tagged **[code]** (pipeline/frontend bug — hand to a coding "
        "agent) or **[data]** (record correction; drafts in the suggestions file).",
        "",
    ]
    if not issues:
        return "\n".join([*out, "No issues found.", ""])

    flagged: list[str] = []
    for sev in SEVERITY_ORDER:
        if not grouped[sev]:
            continue
        out += [f"### {sev.capitalize()} ({counts[sev]})", ""]
        for issue in grouped[sev]:
            entity = issue.get("entity", "?")
            sug = issue.get("ledger_suggestion")
            kind = f" → `{sug['kind']}`" if sug else ""
            out += [
                f"- **[{issue.get('fix_type', '?')}]** **{entity}** — "
                f"_{issue.get('category', '?')}_{kind}  ",
                f"  {issue.get('description', '')}",
            ]
            if entity in by_url and entity not in flagged:
                flagged.append(entity)
        out.append("")

    if flagged:
        out += ["### Flagged entity snapshots", ""]
        for url in flagged:
            out += ["```", *evidence.render_snapshot(by_url[url]), "```", ""]
    return "\n".join(out)
