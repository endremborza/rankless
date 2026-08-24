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
    [--subject "César Hidalgo"] [--question "..."] [--investigate <run>[:<id>]] \
    [--model opus] [--sample 8] [--out my-run]
# make alias: make deep-explore ARGS="--backend live --foci all"
```

`pyscripts/explore/deep.py` drives a headless Claude session with these tools
(`--mcp-config` + `--strict-mcp-config`, `--allowedTools mcp__rankless`) pointed at a chosen
backend, then **re-issues every cited number** through the same tool functions — the
reproduced value, not the model's text, is what gets published. Each run writes to
`.cril/writeups/explorations/<run>/`:

| File                       | Contents                                                                                                                   |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `report.md`                | the stories only — prose (with numbers woven in) + entity links, each linking to its reproduction anchor. No code clutter. |
| `reproduce.md`             | per-finding (`#f1`, `#f2`, …) numbers table + the exact calls (`tool(args) → path`) and equivalent `curl`.                 |
| `findings.json`            | machine-readable findings incl. stable `id`, reproduced values, and `meta` (per-phase runtime + counts).                   |
| `ledger-suggestions.jsonl` | data-issue fixes in `LedgerPayload` shape (only when a finding is ledger-fixable).                                         |

A one-line-per-run record is also appended to `.cril/writeups/explorations/runs.jsonl`.

Parameters:

- `--backend` — `local` (`127.0.0.1:3038`), `live` (`alpha-api.rankless.org`), or a full
  `/v1` URL. Passed to the spawned MCP server (`RANKLESS_BE_URL` in the MCP config's `env`)
  **and** the in-process verifier (`mcp_server.set_backend`), so both hit the same data.
- `--foci` — any of `share` (interesting/shareable, sub-typed by `share_kind`), `query` (a
  specific investigation, drivable with `--question`), `data-issue` (a data problem: an
  investigation setup, or a single-ledger-entry fix), or `all`. Defaults to `query` when
  `--investigate`/`--question` is set, else `share`.
- `--subject` — center the whole round on one entity/scope: a name (`"Balázs Lengyel"`), a
  country (`"Hungary"`), or a typed ref (`authors:balazs-lengyel`). Scopes findings to that
  target and its neighborhood instead of famous seeds.
- `--investigate <run>[:<id>]` — deepen a past finding. Every finding has a stable `id`
  (`f1`, `f2`, …) in its run's `findings.json`; `--investigate <run>:f5` loads that
  finding's description + reproduced numbers as the seed and tells the agent to dig further.
  Omit `:<id>` to follow up the whole run.
- `--suggest-endpoints` / `--no-suggest-endpoints` — surface backend endpoints that don't
  exist yet but would unlock better insight (on by default).

`mcp_server/tools.py`'s `TOOL_FNS` registry is reused verbatim as the verifier
(`pyscripts/explore/verify.py`).

The mining engine is pluggable: `pyscripts/explore/runner.py` holds a `RUNNERS` registry
(selected with `--runner`, default `claude-cli`), so the Claude Code CLI can be swapped for
an SDK/API engine without touching the mining or reproduction logic.

## Generator workflows

`pyscripts/explore/generation.py` is the shared engine for workflows that mine
per-entity objects into the store: it picks targets from the backend's citation-ordered
slice (idempotent reruns skip already-stored keys, a per-country cap keeps packs
diverse), mines each target with one agentic session, and lands the accepted objects as
one immutable bundle. A workflow is a `GeneratorSpec` — prompts plus an accept policy —
so adding one is a small module plus a `WORKFLOWS` registry entry (`explore/runs.py`),
which also gives it the worker spawn path and the `/mcp` queue form. Each run registers
itself as an `mcp_sessions` row (self-registered from the CLI with `params.origin:
"cli"`; worker-claimed when queued from `/mcp`) named `<workflow>-<etype>-<UTC stamp>`
— the naming every agent run shares (`runs.run_name`, mirrored in
`src/lib/mcp-util.ts`).

- **`uv run -m pyscripts game-cards`** (`game_cards.py`) — 6-clue guessing ladders,
  hardest first; every cited number re-issued through `verify.verify_facts` and clue
  text linted against name/acronym/city leaks; accepted cards become `game-card`
  objects, which the `/game-clues` route reads server-side (no LLM at play time).
- **`uv run -m pyscripts country-cards`** (`country_cards.py`) — country-quiz cards for
  `/game-countries`: batch-prompted (no per-entity agentic session, the backend already
  knows name + country) judgment over a deep slice of mid-tier institutions, keeping
  the misleadingly named ones with three ISO-validated decoy countries and a
  post-answer reveal note; accepted picks become `country-card` objects.
- **`uv run -m pyscripts impact-stories`** (`impact_stories.py`) — short verified
  narratives of how an entity's research gets used (citation flows, landmark papers,
  peers); stories with any unreproducible fact are dropped; approved `impact-story`
  objects show publicly on `/mcp`.

## Object store

The unified home for the miners' reusable outputs — game clue cards, verified
findings, whatever comes next — split into immutable payloads and a reviewable index:

- **Bundles** — each generation run writes one `data/mcp-objects/<run>.jsonl.zst`
  (zstd, one self-describing object per line: `kind`, `obj_key`, display fields,
  `payload`). Bundles are never rewritten; batching a run into one archive compresses
  to roughly a sixth of the raw JSON.
- **Index** — `mcp_objects` (in `data/rankless.sqlite`) holds one payload-free row
  per object _version_: logical key `(kind, obj_key)`, the `(bundle, line)` address,
  `gen_at`, and a review `status` (`new` → `approved`/`rejected`). Regeneration adds
  a superseding version row; consumers read the **latest non-rejected** version per
  key, so rejecting a bad regeneration falls back to the previous good one.

`gen_at` is a sortable UTC ISO datetime stamped by `write_bundle` (`ingest --gen-at`
overrides it for historical backfills).

Writers: `pyscripts/object_store.py` (shared write/read/CLI:
`uv run -m pyscripts objects {list,ingest,export,set-status,fsck}` — `fsck` verifies
every index row's `(bundle, line)` address resolves, `export` compresses to a `.zst`
path), the generator workflows above (one bundle per run, named after its session),
and `deep.py`, which bundles every fully verified finding by default (`--no-store` to
skip). The frontend reads the same index + bundles via `src/lib/server/objects.ts`
(decompressed bundles are cached per process — immutability makes that safe; rows
whose bundle hasn't reached this box read as payload-less and are dropped from
consumer reads): `/game-clues` consumes current cards of its pack's etype
(`GAME_PACK_ETYPE` in `src/lib/server/game-clues.ts`) and `/game-countries` its
`country-card` pack; `/mcp` shows approved findings and
impact stories publicly and gives admins the full review list (approve/reject —
rejecting requires a reason, stored as `status_note` and shown in the list so
rejections stay reviewable against later data improvements; decisions and notes
propagate across boxes with the merge) — game cards never render publicly,
they'd spoil the game.

Between boxes, bundles ride the artifact-dir copy (next to `data/mcp-sessions/`)
and index rows ride the user-DB handoff below: merges dedup on
`(kind, obj_key, bundle)`, and for version rows both boxes hold, review
decisions propagate — a decision beats `new`, and between two decisions the
later `updated_at` wins.

## Public site

One page serves everyone — **`/mcp`** (`src/routes/(stat)/mcp/`, "Developers" in the footer):

- **Reference** — connect-your-agent snippets and the tool/foci/option list, rendered from the
  baked manifest `src/lib/assets/data/mcp-manifest.json`, generated by
  `pyscripts/build_mcp_manifest.py` (`make mcp-manifest`) from the **live sources** — tool
  docstrings, `deep._FOCUS_BLOCKS`, the argparse `--help` (via `deep.build_parser()`),
  `resources.py`, `prompts.py`, and `MCP_PUBLIC_URL` — so nothing is restated. Re-bake after
  changing a tool/prompt: `make mcp-manifest` (`MCP_PUBLIC_URL=… ` to set the hosted endpoint).
- **Sessions** — the list of exploration sessions. The public sees public, completed runs;
  admins (ORCID-gated via `isAdmin`) additionally see every session plus the controls: a form
  that **enqueues** a new run, per-session visibility toggle, and delete.
- **`/mcp/runs/[name]`** — one session: its command, metadata, and outputs, rendered from
  `findings.json` via `SessionFindings.svelte` (raw `report.md`/`reproduce.md`/`findings.json`
  under `…/raw/<file>`; private sessions 404 for non-admins).

## Sessions store & worker

A session is a SQLite index row (`mcp_sessions` in `data/rankless.sqlite`) plus a directory
`$MCP_SESSIONS_ROOT/<name>/` (default `data/mcp-sessions/`) holding the deep.py artifacts.
The frontend reads/writes rows via `bun:sqlite` (`src/lib/server/mcp-sessions.ts`); the host
worker uses Python's `sqlite3` on the same WAL file. Sessions are only created through this
flow (admin form → worker) — there is no side-channel seeding.

`pyscripts/mcp_worker.py` (`make mcp-worker`, systemd in prod) polls for `queued` rows, claims
one atomically, and spawns the row's workflow via the `explore/runs.py` `WORKFLOWS` registry
(`params.type`; deep when absent; default `claude-sonnet-5`, model per-session, engine from
`MCP_WORKER_RUNNER`). Deep runs write `findings.json` whose meta the worker ingests → `done`;
self-closing workflows (the generators) set their own done/failed + meta and the worker only
checks the exit code. On startup it re-queues rows a killed worker left `running` — but never
self-registered CLI runs (`params.origin: "cli"`), which it does not own.
deep.py's output root is overridable via `--out-root` or `RANKLESS_WRITEUPS_DIR` (so personal
PKM runs still land in `.cril/`).

### Moving sessions between boxes

`make {merge,sync}_db_{to,from}_{live,alpha}` moves the user-data tables (`mcp_sessions`, `mcp_objects`, `game_results`, `game_daily`, `country_game_results`,
`ledger_events`, `ledger_runs`, `owner_pins`, `users`, `email_consents`, and auth `sessions` —
unexpired rows only, so deploys don't log everyone out) plus the `data/mcp-sessions/` +
`data/mcp-objects/` artifact dirs between the local checkout and a running instance
(`pyscripts/deploy.py` → `pyscripts/userdb.py`, the one home for moving and preserving the
user-data unit — table transfer, decision reconciliation, snapshots, backups). `merge` unions rows (source never clobbers target; auto-id
`ledger_events` dedup on their logical unique index, index-less tables on a NULL-safe
exact-row guard) and copies dirs additively; `sync` mirrors — the target's copy of each table
becomes an exact copy of the source's and dir deletes propagate. `_to_live` writes the live
box, so `sync_db_to_live` **replaces** its ledger/sessions with your local copy — use
`merge_db_to_live` to publish without clobbering.

The deploy flow runs the handoff itself: `new_{small,large}_alpha` pull the latest DB from the
running live box and push it onto the fresh instance; `promote_alpha_to_live` does a pre-flip
catch-up merge (live → local → alpha) and, after the EIP flip, a final merge from the old live
box (still reachable on its new ephemeral IP until `kill_dangling`).

The DB itself is never rsync'd raw: the source is first hot-copied with SQLite's online backup
API (`userdb.snapshot`, run on whichever box holds the source) so a WAL-mode writer can't leave
un-checkpointed commits behind or hand over a torn image; the standalone snapshot is what moves.
If the source has no DB yet (e.g. MCP not deployed on that box), the transfer is a no-op.

## Deployment

Systemd `--user` units are rendered from the `deploy/` templates (`{{ var }}` placeholders —
real repo root, data root, backend URL; no `%h/rankless` guesses) by one shared system,
`pyscripts/services.py`:

```bash
make setup-services ARGS="--profile dev"                        # this machine
make setup-services ARGS="--profile dev --mcp-backend local"    # re-point the MCP server
```

Profiles pick the service set: `dev` = backend + mcp-server + mcp-worker, `small-alpha` =
frontend (blue+green) + mcp-server + mcp-worker, `live` = all four. The MCP server's backend
is a parameter (`--mcp-backend local|alpha|live|<url>`) with per-profile defaults (dev → alpha
API, small-alpha → live API, live → local backend). Cloud instances get the same templates via
`pyscripts/deploy.py` (`Transper.setup_mcp_services`, called from `full_setup_from_nothing`),
which also injects the `deploy/nginx-mcp-location.conf` proxy into the backend server block,
exposing `https://alpha-api.rankless.org/mcp`. Set `MCP_PUBLIC_URL` to that when baking the
manifest.

Notes:

- The worker's `claude-cli` runner **requires an authenticated `claude` CLI** in the service
  user's home; runs are sandboxed to `--allowedTools mcp__rankless` (read-only citation tools,
  no bash/fs). `ADMIN_ORCIDS` gates who can create sessions.
- Rate-limiting/keys for the public endpoint are still open (nginx/IP is the near-term lever;
  see `.cril/ideas.md` §8 Phase 2+).
