"""Agentic deep exploration over a live rankless backend via the MCP tools.

    uv run -m pyscripts.explore.deep --backend live --foci all \
        [--subject "César Hidalgo"] [--question "..."] \
        [--investigate <run>[:<id>]] [--model opus] [--sample 8] [--out my-run]

One run drives a headless Claude session with the rankless MCP tools
(mcp_server/) pointed at a chosen backend. The agent produces findings; this
module then RE-ISSUES every cited number deterministically through the same
tool functions, so the published numbers come from reproduction, not from the
model.

Output lands in `.cril/writeups/explorations/<run>/`:
- report.md   -> the stories only (prose + entity links), linking out
- reproduce.md -> per-finding numbers table + the exact calls (+ curl)
- findings.json -> machine-readable findings incl. reproduced values + ids
- ledger-suggestions.jsonl -> data-issue fixes in LedgerPayload shape
plus a one-line-per-run record appended to explorations/runs.jsonl.

Scoping options:
- --foci        share / query / data-issue (or all); default query when
                --investigate/--question is set, else share.
- --subject     center the whole round on one entity/scope ("Hungary", a
                person, or a typed ref like `authors:balazs-lengyel`).
- --question    a specific investigation for the query focus.
- --investigate deepen a past finding: `<run>` or `<run>:<id>` (finding ids
                are `f1`, `f2`, ... in that run's findings.json).
- --suggest-endpoints  propose missing backend endpoints (on by default).
"""

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import mcp_server
from mcp_server import client as be_client
from pyscripts import object_store
from pyscripts.explore import cli, evidence, runner, runs, verify

FOCI = ("share", "query", "data-issue")
# Output root: personal PKM by default, overridable (env or --out-root) so the
# host worker can write runs into the served sessions store instead.
WRITEUPS_DIR = Path(
    os.environ.get("RANKLESS_WRITEUPS_DIR", ".cril/writeups/explorations")
)
MAX_TURNS = 120
TIMEOUT_S = 3600
DEFAULT_SAMPLE = 8

# Backend GET a metric's tool maps to, for human-reproducible curl lines. Value
# is (path_template, query_arg_names); None for tools whose call isn't a plain
# GET (get_citation_tree resolves the year via /specs). Kept small and explicit
# rather than reconstructed from the tool bodies.
_CURL_MAP = {
    "search_entities": ("/names/{entity_type}", ["query"]),
    "get_top_entities": ("/tops", []),
    "get_entity_profile": ("/views/{entity_type}/{semantic_id}", []),
    "get_entity_stats": (
        "/stats/{entity_type}/{semantic_id}",
        ["year_from", "year_to", "subfield"],
    ),
    "get_papers": ("/works/{entity_type}/{semantic_id}/{offset}", ["limit", "sort"]),
    "get_peers": ("/peers/{entity_type}/{semantic_id}", []),
    "lookup_orcid": ("/orcid/{orcid}", []),
}

_FOCUS_BLOCKS = {
    "share": """\
FOCUS "share" - genuinely interesting, TRUE, shareable findings: surprising
rankings, striking trends, unexpected cross-field impact, David-vs-Goliath
comparisons, human-interest angles. Classify each with `share_kind`:
entity-value (spotlight one entity's standing), comparison (two+ entities),
strengths-weaknesses (where an entity dominates vs lags), analysis (a deeper
multi-number read), or other.""",
    "query": """\
FOCUS "query" - the result of a specific investigation. {question} Report the
answer plainly in `description`, set `question` to the exact question answered,
and back it with metrics.""",
    "data-issue": """\
FOCUS "data-issue" - possible data problems: implausible counts, duplicates,
zeros, extreme outliers, wrong attributions, garbled/mojibake names, mismatched
field/journal mappings. Set `issue_kind`: "ledger-fix" if a single logged-in
user edit would correct it - then fill `ledger_suggestion` (kind one of
merge_authors / merge_papers / claim_paper / disown_paper / add_paper_request,
a human `note`, and any ids/names you can infer in `details`; omit ids you
cannot see) - or "investigation" if it needs more digging first.""",
}


@dataclass
class DeepConfig:
    model: str
    runner: str
    backend_url: str
    backend_label: str
    foci: list[str]
    suggest_endpoints: bool
    store: bool
    question: str | None
    subject: str | None
    investigate: dict | None
    seeds: list[dict]
    sample: int
    out_dir: Path


def main() -> int:
    args = build_parser().parse_args()
    backend_url, backend_label = runner.resolve_backend(args.backend)
    investigate = _load_investigation(args.investigate) if args.investigate else None
    foci_arg = args.foci or ("query" if (investigate or args.question) else "share")
    foci = list(FOCI) if foci_arg == "all" else _split(foci_arg)
    if bad := [f for f in foci if f not in FOCI]:
        print(f"ERROR: unknown foci {bad}; choose from {list(FOCI)} or 'all'.")
        return 2

    # A subject- or investigation-scoped round centers on that target, so random
    # snapshot seeds would only dilute it.
    focused = bool(args.subject or investigate)
    seeds = [] if focused else evidence.sample_snapshots(_load_seeds(), args.sample)
    config = DeepConfig(
        model=cli.resolve_model(args.model),
        runner=args.runner,
        backend_url=backend_url,
        backend_label=backend_label,
        foci=foci,
        suggest_endpoints=args.suggest_endpoints,
        store=args.store,
        question=args.question,
        subject=args.subject,
        investigate=investigate,
        seeds=seeds,
        sample=args.sample,
        out_dir=Path(args.out_root)
        / (args.out or runs.run_name("deep", backend_label)),
    )

    print(
        f"[deep] mining {config.backend_label} ({config.backend_url}) with "
        f"{config.model}; foci={','.join(foci)}"
        + (f"; subject={config.subject!r}" if config.subject else "")
        + (f"; investigate={investigate['ref']!r}" if investigate else "")
        + f"; {len(seeds)} seed(s)."
    )
    t0 = time.monotonic()
    raw = _mine(config)
    t_mine = time.monotonic() - t0
    parsed = _parse(raw, config)
    if parsed is None:
        return 1
    findings, suggestions = parsed
    for i, finding in enumerate(findings, 1):
        finding["id"] = f"f{i}"
    t1 = time.monotonic()
    asyncio.run(_reproduce(findings, config))
    timing = {
        "mine": round(t_mine, 1),
        "reproduce": round(time.monotonic() - t1, 1),
        "total": round(time.monotonic() - t0, 1),
    }

    paths = _write(findings, suggestions, config, timing)
    if config.store:
        _store_findings(findings, config)
    n_ok = sum(f["_verified"] for f in findings)
    print(
        f"[deep] {len(findings)} finding(s), {n_ok} fully reproduced, "
        f"{len(suggestions)} endpoint suggestion(s); mine {timing['mine']}s · "
        f"reproduce {timing['reproduce']}s · total {timing['total']}s."
    )
    print(f"-> {paths['report']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Agentic deep exploration via MCP.")
    p.add_argument(
        "--backend",
        default="local",
        help=f"one of {list(runner.BACKENDS)} or a full /v1 base URL (default: local).",
    )
    p.add_argument(
        "--foci",
        default=None,
        help=(
            f"comma list of {list(FOCI)} or 'all' "
            "(default: query when --investigate/--question, else share)."
        ),
    )
    p.add_argument(
        "--subject",
        default=None,
        help="center the round on one entity/scope, e.g. 'Hungary' or 'authors:balazs-lengyel'.",
    )
    p.add_argument(
        "--question", default=None, help="a specific investigation for the query focus."
    )
    p.add_argument(
        "--investigate",
        default=None,
        help="deepen a past finding: '<run>' or '<run>:<id>' under the writeups dir.",
    )
    p.add_argument(
        "--suggest-endpoints",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="ask the session to propose missing backend endpoints (default: on).",
    )
    p.add_argument(
        "--store",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="collect fully verified findings into the MCP object store (default: on).",
    )
    p.add_argument(
        "--model",
        default=cli.DEFAULT_MODEL,
        help=f"'{'|'.join(cli.MODELS)}' shortcut (default: {cli.DEFAULT_MODEL}) or id.",
    )
    p.add_argument(
        "--runner",
        default=runner.DEFAULT_RUNNER,
        choices=list(runner.RUNNERS),
        help=f"mining engine (default: {runner.DEFAULT_RUNNER}).",
    )
    p.add_argument(
        "--sample", type=int, default=DEFAULT_SAMPLE, help="seed entity count."
    )
    p.add_argument("--out", default=None, help="run dir name under the output root.")
    p.add_argument(
        "--out-root",
        default=str(WRITEUPS_DIR),
        help=f"output root dir (default: {WRITEUPS_DIR}).",
    )
    return p


def _load_investigation(ref: str) -> dict:
    run, _, fid = ref.partition(":")
    path = WRITEUPS_DIR / run / "findings.json"
    if not path.exists():
        raise SystemExit(f"--investigate: no findings.json at {path}")
    findings = json.loads(path.read_text()).get("findings", [])
    if fid:
        findings = [f for f in findings if f.get("id") == fid]
        if not findings:
            raise SystemExit(f"--investigate: finding {fid!r} not found in {run!r}")
    return {"ref": ref, "run": run, "findings": findings}


def _load_seeds() -> list[dict]:
    try:
        return evidence.load_snapshots()
    except (FileNotFoundError, ValueError):
        print("[deep] no local snapshots; seeding from get_top_entities instead.")
        return []


def _mine(config: DeepConfig) -> str:
    job = runner.MineJob(
        system=_system_prompt(config),
        user=_user_prompt(config),
        model=config.model,
        backend_url=config.backend_url,
        max_turns=MAX_TURNS,
        timeout_s=TIMEOUT_S,
    )
    return runner.get_runner(config.runner)(job)


def _system_prompt(config: DeepConfig) -> str:
    parts = [
        "You are an investigative analyst for Rankless, a scholarly citation "
        "explorer. You have live MCP tools over its backend (search_entities, "
        "get_top_entities, get_entity_profile, get_entity_stats, "
        "get_citation_tree, get_papers, get_peers, lookup_orcid).",
        "",
        "Resolve every name to a semantic_id with the tools before using it; "
        "disambiguate homonyms by paper/citation counts. Follow the data - compare "
        "peers, pull hit papers, check which fields an entity's work feeds into.",
        "",
        "Every number you report MUST come from a tool call you made this "
        "session. For each number, record the exact `tool`, `args`, and a dotted "
        "`path` into that call's JSON result. Those calls are re-issued and the "
        "reproduced value - not your text - is what gets published, so make args "
        "and path exact. `path` examples: `windowPapers`, "
        "`topSubfields[0].citations`, `breakdown[1].children[2].citationLinks`, "
        "`papers[1].year`, `relations.paper-fields[1].score`.",
        "",
        "Produce findings for these foci ONLY:",
    ]
    for focus in config.foci:
        block = _FOCUS_BLOCKS[focus]
        if focus == "query":
            q = (
                f'Investigate: "{config.question}".'
                if config.question
                else "Pick meaningful investigations a curious analyst would run."
            )
            block = block.format(question=q)
        parts += ["", block]
    if config.suggest_endpoints:
        parts += [
            "",
            "If you hit a wall where a backend endpoint that does not exist "
            "would have unlocked a better finding or made insight easier to "
            "reach, add it to `endpoint_suggestions`.",
        ]
    parts += ["", _schema_block(config)]
    return "\n".join(parts)


def _schema_block(config: DeepConfig) -> str:
    return f"""\
Respond with ONLY a JSON object (no markdown fences):
{{"findings": [
  {{"focus": "{"|".join(config.foci)}",
    "title": "punchy title",
    "description": "2-5 plain sentences: the story / answer / issue, with the key "
                   "numbers woven in (this is the only prose a reader sees)",
    "share_kind": "entity-value|comparison|strengths-weaknesses|analysis|other|null",
    "issue_kind": "investigation|ledger-fix|null",
    "question": "the exact question answered, or null",
    "ledger_suggestion": null | {{"kind": "...", "note": "...", "details": {{}}}},
    "entities": ["<rankless_url>", ...],
    "metrics": [
      {{"key": "short_slug", "label": "human label of the number",
        "tool": "<tool name>", "args": {{...}}, "path": "<dotted path>",
        "claimed": <the value you saw>}}]}}],
 "endpoint_suggestions": [
   {{"name": "/v1/...", "rationale": "why", "unlocks": "what it enables"}}]}}
Use only the requested foci. Return [] for any section you have nothing for."""


def _user_prompt(config: DeepConfig) -> str:
    if config.investigate:
        return _investigate_prompt(config)
    if config.subject:
        return (
            f"Center this entire round on: {config.subject}\n\n"
            "Resolve it first (it may be an entity name, a country, a field, or an "
            "`etype:semantic_id` ref). Build every finding around it and its immediate "
            "neighborhood - its production and standout works, its peers, its co-authors "
            "or related entities, and the fields it feeds into or draws from. Prefer the "
            "specific and less-obvious over generic famous entities."
        )
    if not config.seeds:
        return "No seed entities provided - start from get_top_entities()."
    lines = ["Seed entities (starting points only - explore beyond them):", ""]
    lines += [f"- {s['name']} ({s['rootType']}) {s['url']}" for s in config.seeds]
    return "\n".join(lines)


def _investigate_prompt(config: DeepConfig) -> str:
    inv = config.investigate
    lines = [
        f'You are deepening prior finding(s) from exploration "{inv["run"]}". Go '
        "beyond restating them: verify they still hold, explain the mechanism, surface "
        "related entities and adjacent findings, note caveats, and test whether they "
        "generalize.",
    ]
    if config.subject:
        lines.append(f"\nStay centered on: {config.subject}")
    lines.append("\nPrior finding(s):")
    for f in inv["findings"]:
        nums = "; ".join(
            f"{m.get('label', m.get('key'))}={m.get('reproduced')}"
            for m in f.get("metrics", [])
            if not m.get("error")
        )
        lines += [
            f"\n--- {f.get('id')}: {f.get('title')} ---",
            f.get("description", ""),
        ]
        if nums:
            lines.append(f"Numbers: {nums}")
        if ents := f.get("entities"):
            lines.append("Entities: " + ", ".join(ents))
    return "\n".join(lines)


def _parse(raw: str, config: DeepConfig) -> tuple[list[dict], list[dict]] | None:
    try:
        obj = cli.parse_json(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        config.out_dir.mkdir(parents=True, exist_ok=True)
        (config.out_dir / "raw-response.txt").write_text(raw)
        print(
            f"ERROR: could not parse response ({exc}); raw saved to {config.out_dir}."
        )
        return None
    return obj.get("findings", []), obj.get("endpoint_suggestions", [])


async def _reproduce(findings: list[dict], config: DeepConfig) -> None:
    """Re-issue every metric against the backend; reproduced value is canonical."""
    mcp_server.set_backend(config.backend_url)
    try:
        for finding in findings:
            metrics = finding.get("metrics", [])
            await verify.verify_facts(metrics)
            finding["numbers"] = {
                m["key"]: m["reproduced"] for m in metrics if not m["error"]
            }
            finding["_verified"] = bool(metrics) and all(m["ok"] for m in metrics)
    finally:
        await be_client.aclose()


def _write(
    findings: list[dict],
    suggestions: list[dict],
    config: DeepConfig,
    timing: dict,
) -> dict[str, Path]:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "type": "deep",
        "backend": config.backend_label,
        "backendUrl": config.backend_url,
        "model": config.model,
        "foci": config.foci,
        "subject": config.subject,
        "question": config.question,
        "investigate": config.investigate["ref"] if config.investigate else None,
        "generated": runs.utc_now_iso(),
        "seedCount": len(config.seeds),
        "runtimeSeconds": timing,
        "counts": _counts(findings, suggestions),
    }
    report = config.out_dir / "report.md"
    report.write_text(_render_report(findings, suggestions, config, meta))
    (config.out_dir / "reproduce.md").write_text(_render_reproduce(findings, config))
    (config.out_dir / "findings.json").write_text(
        json.dumps(
            {"meta": meta, "findings": findings, "endpointSuggestions": suggestions},
            indent=2,
        )
    )
    ledger = [
        {
            **f["ledger_suggestion"],
            "_title": f.get("title"),
            "_why": f.get("description"),
        }
        for f in findings
        if f.get("focus") == "data-issue" and f.get("ledger_suggestion")
    ]
    if ledger:
        (config.out_dir / "ledger-suggestions.jsonl").write_text(
            "".join(json.dumps(s) + "\n" for s in ledger)
        )
    _append_runs_log(config, meta)
    return {"report": report}


def _counts(findings: list[dict], suggestions: list[dict]) -> dict:
    metrics = [m for f in findings for m in f.get("metrics", [])]
    return {
        "findings": len(findings),
        "byFocus": dict(Counter(f.get("focus") for f in findings)),
        "reproducedFindings": sum(f.get("_verified", False) for f in findings),
        "metrics": len(metrics),
        "metricsReproduced": sum(1 for m in metrics if not m["error"] and m["ok"]),
        "metricsMismatch": sum(1 for m in metrics if not m["error"] and not m["ok"]),
        "metricsError": sum(1 for m in metrics if m["error"]),
        "endpointSuggestions": len(suggestions),
    }


def _store_findings(findings: list[dict], config: DeepConfig) -> None:
    run = config.out_dir.name
    objects = [
        {
            "kind": "finding",
            "obj_key": f"{run}|{f['id']}",
            "title": f.get("title"),
            "payload": f,
        }
        for f in findings
        if f["_verified"]
    ]
    if not objects:
        print("[deep] no fully verified findings; nothing stored")
        return
    con = object_store.connect()
    try:
        n = object_store.write_bundle(con, run, objects)
    finally:
        con.close()
    print(f"[deep] {n} verified finding(s) -> object store bundle {run!r}")


def _append_runs_log(config: DeepConfig, meta: dict) -> None:
    """One compact line per run in a shared log (in the output root)."""
    root = config.out_dir.parent
    root.mkdir(parents=True, exist_ok=True)
    record = {"out": config.out_dir.name, **meta}
    with (root / "runs.jsonl").open("a") as fh:
        fh.write(json.dumps(record) + "\n")


def _render_report(
    findings: list[dict], suggestions: list[dict], config: DeepConfig, meta: dict
) -> str:
    """The stories only: prose + entity links + a link out to the numbers."""
    n_ok = sum(f["_verified"] for f in findings)
    rt, c = meta["runtimeSeconds"], meta["counts"]
    out = [
        f"# Deep exploration — {config.backend_label}",
        "",
        f"_Backend `{config.backend_url}` · model `{config.model}` · foci "
        f"`{', '.join(config.foci)}` · {meta['generated']}._  ",
        f"_{len(findings)} finding(s), {n_ok} fully reproduced; "
        f"{c['metricsReproduced']}/{c['metrics']} numbers reproduced"
        + (f", {c['metricsMismatch']} mismatch" if c["metricsMismatch"] else "")
        + (f", {c['metricsError']} error" if c["metricsError"] else "")
        + f". Mined in {rt['mine']}s. Numbers and reproduction calls: "
        "[reproduce.md](reproduce.md) · [findings.json](findings.json)._",
        "",
    ]
    for label, value in (
        ("Subject", config.subject),
        ("Investigation", config.question),
        ("Deepening", meta["investigate"]),
    ):
        if value:
            out += [f"**{label}:** {value}", ""]
    for focus in config.foci:
        group = [f for f in findings if f.get("focus") == focus]
        if not group:
            continue
        out += [f"## {focus} ({len(group)})", ""]
        out += [line for f in group for line in _render_story(f)]
    out += _render_suggestions(suggestions)
    return "\n".join(out).rstrip() + "\n"


def _render_story(finding: dict) -> list[str]:
    metrics = finding.get("metrics", [])
    n_bad = sum(1 for m in metrics if not m["ok"])
    badge = (
        "— no numbers" if not metrics else (f"✗ {n_bad} unverified" if n_bad else "✓")
    )
    tags = [t for t in (finding.get("share_kind"), finding.get("issue_kind")) if t]
    heading = f"### {finding.get('title', 'Untitled')}  `{badge}`"
    if tags:
        heading += f"  _{' · '.join(tags)}_"
    out = [heading, ""]
    if q := finding.get("question"):
        out += [f"**Q:** {q}", ""]
    out += [finding.get("description", ""), ""]
    if sug := finding.get("ledger_suggestion"):
        out += [f"**Ledger fix:** `{sug.get('kind')}` — {sug.get('note', '')}", ""]
    footer = (
        [f"_Entities: {', '.join(f'<{e}>' for e in finding['entities'])}_"]
        if (finding.get("entities"))
        else []
    )
    if metrics:
        footer.append(f"[numbers & reproduction →](reproduce.md#{finding.get('id')})")
    if footer:
        out += [" · ".join(footer), ""]
    return out


def _render_suggestions(suggestions: list[dict]) -> list[str]:
    if not suggestions:
        return []
    out = ["## Suggested new endpoints", ""]
    for s in suggestions:
        out += [
            f"### `{s.get('name', '?')}`",
            f"- **Rationale:** {s.get('rationale', '')}",
            f"- **Unlocks:** {s.get('unlocks', '')}",
            "",
        ]
    return out


def _render_reproduce(findings: list[dict], config: DeepConfig) -> str:
    """The numbers and the exact calls that produce them, anchored per finding."""
    out = [
        f"# Reproduction — {config.out_dir.name}",
        "",
        f"_Numbers re-issued from `{config.backend_url}`. Each is an MCP tool call plus "
        "a dotted path into its JSON result; the `curl` is the equivalent raw backend "
        "call. Stories: [report.md](report.md)._",
        "",
    ]
    for finding in findings:
        metrics = finding.get("metrics", [])
        if not metrics:
            continue
        fid = finding.get("id")
        out += [
            f'<a id="{fid}"></a>',
            f"## {fid} — {finding.get('title', 'Untitled')}",
            "",
            "| Metric | Value |",
            "| --- | --- |",
        ]
        out += [f"| {m.get('label', m.get('key', ''))} | {_cell(m)} |" for m in metrics]
        out += ["", "**Calls:**"]
        for m in metrics:
            out.append(
                f"- `{m.get('tool')}({json.dumps(m.get('args', {}))})` → `{m.get('path')}`"
            )
            if curl := _curl(m, config.backend_url):
                out.append(f"  - `{curl}`")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _cell(metric: dict) -> str:
    if metric["error"]:
        return f"⚠️ {metric['error']}"
    val = metric["reproduced"]
    claimed = metric.get("claimed")
    if claimed is not None and not verify.values_match(val, claimed):
        return f"**{val}** (model claimed {claimed})"
    return f"{val}"


def _curl(metric: dict, base_url: str) -> str | None:
    entry = _CURL_MAP.get(metric.get("tool", ""))
    if entry is None:
        return None
    template, query_names = entry
    args = metric.get("args", {})
    args = {**args, "offset": args.get("offset", 0)}
    try:
        path = template.format(**args)
    except KeyError:
        return None
    qs = "&".join(
        f"{_query_key(n)}={args[n]}" for n in query_names if args.get(n) is not None
    )
    return f"curl '{base_url}{path}{'?' + qs if qs else ''}'"


def _query_key(name: str) -> str:
    return {"query": "q", "limit": "n"}.get(name, name)


def _split(raw: str) -> list[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


if __name__ == "__main__":
    sys.exit(main())
