"""Agentic deep exploration over a live rankless backend via the MCP tools.

    uv run -m pyscripts.explore.deep --backend live --foci all \
        [--question "..."] [--model opus] [--sample 8] [--out my-run]

One run drives a headless Claude session with the rankless MCP tools
(mcp_server/) pointed at a chosen backend. The agent produces findings; this
module then RE-ISSUES every cited number deterministically through the same
tool functions, so the published numbers come from reproduction, not from the
model. Output (a report + machine-readable findings) lands in
`.cril/writeups/explorations/<run>/`.

Findings are separated by `--foci`:
- share      -> interesting, shareable findings (share_kind: entity-value /
                comparison / strengths-weaknesses / analysis / other).
- query      -> the result of a specific investigation (drive one with
                --question, or let the agent pick meaningful ones).
- data-issue -> a possible data problem: an investigation setup, or one
                correctable with a single ledger entry (LedgerPayload shape).

A session can also surface `endpoint_suggestions`: backend endpoints that don't
exist yet but would unlock better stories / easier insight (--suggest-endpoints,
on by default).
"""

import argparse
import asyncio
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import httpx

import mcp_server
from mcp_server import client as be_client
from mcp_server.tools import TOOL_FNS
from pyscripts.explore import cli, evidence

BACKENDS = {
    "local": "http://127.0.0.1:3038/v1",
    "live": "https://alpha-api.rankless.org/v1",
}
FOCI = ("share", "query", "data-issue")
WRITEUPS_DIR = Path(".cril/writeups/explorations")
ALLOWED_TOOLS = "mcp__rankless"
MAX_TURNS = 120
TIMEOUT_S = 3600
DEFAULT_SAMPLE = 8

_PATH_TOKEN_RE = re.compile(r"\.?([^.\[\]]+)|\[(\d+)\]")

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
    backend_url: str
    backend_label: str
    foci: list[str]
    suggest_endpoints: bool
    question: str | None
    seeds: list[dict]
    sample: int
    out_dir: Path


def main() -> int:
    args = _parse_args()
    backend_url, backend_label = _resolve_backend(args.backend)
    foci = list(FOCI) if args.foci == "all" else _split(args.foci)
    if bad := [f for f in foci if f not in FOCI]:
        print(f"ERROR: unknown foci {bad}; choose from {list(FOCI)} or 'all'.")
        return 2

    seeds = evidence.sample_snapshots(_load_seeds(), args.sample)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out_name = args.out or f"{backend_label}-{stamp}"
    config = DeepConfig(
        model=cli.resolve_model(args.model),
        backend_url=backend_url,
        backend_label=backend_label,
        foci=foci,
        suggest_endpoints=args.suggest_endpoints,
        question=args.question,
        seeds=seeds,
        sample=args.sample,
        out_dir=WRITEUPS_DIR / out_name,
    )

    print(
        f"[deep] mining {config.backend_label} ({config.backend_url}) with "
        f"{config.model}; foci={','.join(foci)}; {len(seeds)} seed(s)."
    )
    t0 = time.monotonic()
    raw = _mine(config)
    t_mine = time.monotonic() - t0
    parsed = _parse(raw, config)
    if parsed is None:
        return 1
    findings, suggestions = parsed
    t1 = time.monotonic()
    asyncio.run(_reproduce(findings, config))
    timing = {
        "mine": round(t_mine, 1),
        "reproduce": round(time.monotonic() - t1, 1),
        "total": round(time.monotonic() - t0, 1),
    }

    paths = _write(findings, suggestions, config, stamp, timing)
    n_ok = sum(f["_verified"] for f in findings)
    print(
        f"[deep] {len(findings)} finding(s), {n_ok} fully reproduced, "
        f"{len(suggestions)} endpoint suggestion(s); mine {timing['mine']}s · "
        f"reproduce {timing['reproduce']}s · total {timing['total']}s."
    )
    print(f"-> {paths['report']}")
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Agentic deep exploration via MCP.")
    p.add_argument(
        "--backend",
        default="local",
        help=f"one of {list(BACKENDS)} or a full /v1 base URL (default: local).",
    )
    p.add_argument(
        "--foci",
        default="share",
        help=f"comma list of {list(FOCI)} or 'all' (default: share).",
    )
    p.add_argument(
        "--question", default=None, help="a specific investigation for the query focus."
    )
    p.add_argument(
        "--suggest-endpoints",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="ask the session to propose missing backend endpoints (default: on).",
    )
    p.add_argument(
        "--model",
        default=cli.DEFAULT_MODEL,
        help=f"'{'|'.join(cli.MODELS)}' shortcut (default: {cli.DEFAULT_MODEL}) or id.",
    )
    p.add_argument(
        "--sample", type=int, default=DEFAULT_SAMPLE, help="seed entity count."
    )
    p.add_argument(
        "--out", default=None, help="run dir name under .cril/writeups/explorations."
    )
    return p.parse_args()


def _resolve_backend(arg: str) -> tuple[str, str]:
    if arg in BACKENDS:
        return BACKENDS[arg], arg
    if arg.startswith("http"):
        return arg.rstrip("/"), "custom"
    raise SystemExit(f"--backend must be one of {list(BACKENDS)} or an http(s) URL.")


def _load_seeds() -> list[dict]:
    try:
        return evidence.load_snapshots()
    except (FileNotFoundError, ValueError):
        print("[deep] no local snapshots; seeding from get_top_entities instead.")
        return []


def _mine(config: DeepConfig) -> str:
    return cli.query_claude_cli(
        _system_prompt(config),
        _user_prompt(config),
        config.model,
        allowed_tools=ALLOWED_TOOLS,
        mcp_config=_mcp_config(config),
        max_turns=MAX_TURNS,
        timeout_s=TIMEOUT_S,
    )


def _mcp_config(config: DeepConfig) -> str:
    return json.dumps(
        {
            "mcpServers": {
                "rankless": {
                    "command": sys.executable,
                    "args": ["-m", "mcp_server"],
                    "env": {"RANKLESS_BE_URL": config.backend_url},
                }
            }
        }
    )


def _system_prompt(config: DeepConfig) -> str:
    parts = [
        "You are an investigative analyst for Rankless, a scholarly citation "
        "explorer. You have live MCP tools over its backend (search_entities, "
        "get_top_entities, get_entity_profile, get_entity_stats, "
        "get_citation_tree, get_papers, get_peers, lookup_orcid).",
        "",
        "Resolve every name to a semantic_id with the tools before using it; "
        "disambiguate homonyms by paper/citation counts. Follow the data beyond "
        "the seed entities - compare peers, pull hit papers, check which fields "
        "an entity's work feeds into.",
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
    "description": "2-5 plain sentences: the story / answer / issue",
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
    if not config.seeds:
        return "No seed entities provided - start from get_top_entities()."
    lines = ["Seed entities (starting points only - explore beyond them):", ""]
    lines += [f"- {s['name']} ({s['rootType']}) {s['url']}" for s in config.seeds]
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
            for metric in metrics:
                # The agent records the tool it actually called, e.g.
                # "mcp__rankless__get_peers"; TOOL_FNS is keyed by the bare name.
                metric["tool"] = _tool_name(metric.get("tool", ""))
                metric["reproduced"], metric["error"] = await _reissue(metric)
                metric["ok"] = _metric_ok(metric)
            finding["numbers"] = {
                m["key"]: m["reproduced"] for m in metrics if not m["error"]
            }
            finding["_verified"] = bool(metrics) and all(m["ok"] for m in metrics)
    finally:
        await be_client.aclose()


def _tool_name(tool: str) -> str:
    """Bare tool name, stripping any `mcp__<server>__` prefix the agent used."""
    return tool.split("__")[-1] if tool.startswith("mcp__") else tool


async def _reissue(metric: dict) -> tuple[object, str | None]:
    fn = TOOL_FNS.get(metric.get("tool", ""))
    if fn is None:
        return None, f"unknown tool {metric.get('tool')!r}"
    try:
        result = await fn(**metric.get("args", {}))
        return _walk(result, metric.get("path", "")), None
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _metric_ok(metric: dict) -> bool:
    if metric["error"]:
        return False
    claimed = metric.get("claimed")
    if claimed is None:
        return True
    return _values_match(metric["reproduced"], claimed)


def _walk(obj, path: str):
    for name, idx in _PATH_TOKEN_RE.findall(path):
        obj = obj[int(idx)] if idx else obj[name]
    return obj


def _values_match(actual, expected) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return float(actual) == float(expected)
    return actual == expected


def _write(
    findings: list[dict],
    suggestions: list[dict],
    config: DeepConfig,
    stamp: str,
    timing: dict,
) -> dict[str, Path]:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "backend": config.backend_label,
        "backendUrl": config.backend_url,
        "model": config.model,
        "foci": config.foci,
        "question": config.question,
        "generated": stamp,
        "seedCount": len(config.seeds),
        "runtimeSeconds": timing,
        "counts": _counts(findings, suggestions),
    }
    report = config.out_dir / "report.md"
    report.write_text(_render(findings, suggestions, config, meta))
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


def _append_runs_log(config: DeepConfig, meta: dict) -> None:
    """One compact line per run in a shared log, for cross-run history."""
    WRITEUPS_DIR.mkdir(parents=True, exist_ok=True)
    record = {"out": config.out_dir.name, **meta}
    with (WRITEUPS_DIR / "runs.jsonl").open("a") as fh:
        fh.write(json.dumps(record) + "\n")


def _render(
    findings: list[dict], suggestions: list[dict], config: DeepConfig, meta: dict
) -> str:
    n_ok = sum(f["_verified"] for f in findings)
    rt, c = meta["runtimeSeconds"], meta["counts"]
    out = [
        f"# Deep exploration — {config.backend_label}",
        "",
        f"_Backend `{config.backend_url}` · model `{config.model}` · foci "
        f"`{', '.join(config.foci)}` · {meta['seedCount']} seeds · {meta['generated']}._  ",
        f"_{len(findings)} finding(s), {n_ok} fully reproduced; "
        f"{c['metricsReproduced']}/{c['metrics']} numbers reproduced"
        + (f", {c['metricsMismatch']} mismatch" if c["metricsMismatch"] else "")
        + (f", {c['metricsError']} error" if c["metricsError"] else "")
        + f". Mined in {rt['mine']}s, reproduced in {rt['reproduce']}s. Numbers below "
        "are re-issued from the backend, not model-generated._",
        "",
    ]
    if config.question:
        out += [f"**Investigation:** {config.question}", ""]
    for focus in config.foci:
        group = [f for f in findings if f.get("focus") == focus]
        if not group:
            continue
        out += [f"## {focus} ({len(group)})", ""]
        out += [line for f in group for line in _render_finding(f, config)]
    if suggestions:
        out += ["## Suggested new endpoints", ""]
        for s in suggestions:
            out += [
                f"### `{s.get('name', '?')}`",
                f"- **Rationale:** {s.get('rationale', '')}",
                f"- **Unlocks:** {s.get('unlocks', '')}",
                "",
            ]
    return "\n".join(out).rstrip() + "\n"


def _render_finding(finding: dict, config: DeepConfig) -> list[str]:
    metrics = finding.get("metrics", [])
    n_bad = sum(1 for m in metrics if not m["ok"])
    if not metrics:
        badge = "— no numbers"
    elif n_bad:
        badge = f"✗ {n_bad} unverified"
    else:
        badge = "✓ reproduced"
    tags = [t for t in (finding.get("share_kind"), finding.get("issue_kind")) if t]
    heading = f"### {finding.get('title', 'Untitled')}  `{badge}`"
    if tags:
        heading += f"  _{' · '.join(tags)}_"
    out = [heading, ""]
    if q := finding.get("question"):
        out += [f"**Q:** {q}", ""]
    out += [finding.get("description", ""), ""]

    if metrics:
        out += ["**Numbers** (reproduced from the backend):", ""]
        out += ["| Metric | Value |", "| --- | --- |"]
        for m in metrics:
            out.append(f"| {m.get('label', m.get('key', ''))} | {_cell(m)} |")
        out += ["", "**Reproduce:**"]
        for m in metrics:
            out.append(
                f"- `{m.get('tool')}({json.dumps(m.get('args', {}))})` → `{m.get('path')}`"
            )
            if curl := _curl(m, config.backend_url):
                out.append(f"  - `{curl}`")
        out.append("")
    if sug := finding.get("ledger_suggestion"):
        out += [f"**Ledger fix:** `{sug.get('kind')}` — {sug.get('note', '')}", ""]
    entities = ", ".join(f"<{e}>" for e in finding.get("entities", []))
    out += [f"_Entities: {entities or '—'}_", ""]
    return out


def _cell(metric: dict) -> str:
    if metric["error"]:
        return f"⚠️ {metric['error']}"
    val = metric["reproduced"]
    claimed = metric.get("claimed")
    if claimed is not None and not _values_match(val, claimed):
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
