# MCP server

`mcp_server/` wraps the Rust backend (`rankless_server`, `127.0.0.1:3038`) in the
[Model Context Protocol](https://modelcontextprotocol.io) so any MCP client — Claude
Code, Claude Desktop, or the in-repo story miner — can consume citation data without
bespoke integration. It is a separate Python process (official `mcp` SDK + `httpx`)
that proxies and shapes responses; rate/agent logic stays out of the Rust hot path.

## Running

```bash
make mcp-server            # = uv run -m mcp_server (stdio transport)
```

Environment:

- `RANKLESS_BE_URL` — backend base URL (default `http://127.0.0.1:3038/v1`)
- `RANKLESS_SITE_URL` — base for `rankless_url` backlinks (default `https://rankless.org`)

Client config (Claude Code / Desktop — prefer the venv python directly; `uv run`
resolution is slow enough that clients can give up on the connect):

```json
{
	"mcpServers": {
		"rankless": {
			"command": "/path/to/rankless/.venv/bin/python",
			"args": ["-m", "mcp_server"]
		}
	}
}
```

## Surface

Tools (each response carries `rankless_url` backlinks; ids must come from the
resolution tools, never guessed):

| Tool                                                                         | Backend                 | Notes                                                                |
| ---------------------------------------------------------------------------- | ----------------------- | -------------------------------------------------------------------- |
| `search_entities(query, entity_type)`                                        | `/v1/names/:etype?q=`   | tier-1 resolution; `entity_type` ∈ root types or `all`               |
| `get_top_entities()`                                                         | `/v1/tops`              | seed entities per type                                               |
| `get_entity_profile(etype, sem_id)`                                          | `/v1/views/:etype/:sem` | drops `authorNetwork`, truncates long lists                          |
| `get_entity_stats(etype, sem_id, year_from?, year_to?, subfield?)`           | `/v1/stats/...`         | recent-era window clamped to `[eraFrom, eraTo]`                      |
| `get_citation_tree(etype, sem_id, tree_index?, since_year?, top_n?, depth?)` | `/v1/trees/...`         | flattened top-N per level; level meaning from `/v1/specs` breakdowns |
| `get_papers(etype, sem_id, offset?, limit?, sort?)`                          | `/v1/works/...`         | `sort="citations"` for hit papers                                    |
| `get_peers(etype, sem_id)`                                                   | `/v1/peers/...`         |                                                                      |
| `lookup_orcid(orcid)`                                                        | `/v1/orcid/:id`         |                                                                      |

Resources: `rankless://schema/entity-types`, `rankless://guide/agent` (resolution-first
rule, provenance expectations). Prompt: `author_impact_report(author_name)`.

Tool implementations are plain async functions (`mcp_server/tools.py`, `TOOL_FNS`
registry) deliberately importable without the MCP transport — the deep-stories
evidence verifier re-issues them directly.

## Consumer: deep exploration

```bash
uv run -m pyscripts.explore.deep --backend live --foci all \
    [--question "..."] [--model opus] [--sample 8] [--out my-run]
# make alias: make deep-explore ARGS="--backend live --foci all"
```

`pyscripts/explore/deep.py` drives a headless Claude session with these tools
(`--mcp-config` + `--strict-mcp-config`, `--allowedTools mcp__rankless`) pointed at a chosen
backend, then **re-issues every cited number** through the same tool functions — the
reproduced value, not the model's text, is what gets published. Output lands in
`.cril/writeups/explorations/<run>/` (`report.md`, `findings.json`, and
`ledger-suggestions.jsonl` when any data-issue is ledger-fixable); run metadata (per-phase
runtime + counts) is embedded in `findings.json` `meta` and appended one-line-per-run to
`.cril/writeups/explorations/runs.jsonl`.

Parameters:

- `--backend` — `local` (`127.0.0.1:3038`), `live` (`alpha-api.rankless.org`), or a full
  `/v1` URL. Passed to the spawned MCP server (`RANKLESS_BE_URL` in the MCP config's `env`)
  **and** the in-process verifier (`mcp_server.set_backend`), so both hit the same data.
- `--foci` — any of `share` (interesting/shareable, sub-typed by `share_kind`), `query` (a
  specific investigation, drivable with `--question`), `data-issue` (a data problem: an
  investigation setup, or a single-ledger-entry fix), or `all`.
- `--suggest-endpoints` / `--no-suggest-endpoints` — surface backend endpoints that don't
  exist yet but would unlock better insight (on by default).

Each finding carries a plain-language description, the exact reproduction calls
(`tool(args) → path`, plus a curl for the direct-mapped tools), and the reproduced numbers
table. `mcp_server/tools.py`'s `TOOL_FNS` registry is reused verbatim as the verifier.

## Status / roadmap

Phase 1 (this doc) is built. Phase 2+ (paper search, DOI lookup, batch, citation paths,
SSE/remote deployment, rate limiting) is designed in `.cril/ideas.md` §8.
