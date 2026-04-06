# Rankless MCP — Plan

## Why MCP

AI agents doing research, literature review, expert discovery, or institutional analysis need structured access to citation data. Rankless already serves this data at low latency over a compact binary backend — wrapping it in MCP makes it directly consumable by any MCP-compatible agent (Claude, GPT, Copilot, open-source agent frameworks) without building bespoke integrations.

The core bet: agents will increasingly be the primary consumers of academic data APIs, overtaking human-driven web UIs in query volume. Being the best MCP source for citation intelligence positions Rankless as infrastructure.

---

## 1. MCP Interface Design

### 1.1 Tools (agent-callable actions)

Tools are the primary interface — agents call them to answer questions.

| Tool | Parameters | Returns | Maps to |
|------|-----------|---------|---------|
| `search_entities` | `query: str`, `entity_type: enum` | Top 20 matches with names, IDs, coordinates | `/v1/names/:etype?q=` |
| `get_entity_profile` | `entity_type`, `semantic_id` | Full profile: name, stats, coordinates, metadata | `/v1/views/:etype/:id` |
| `get_citation_tree` | `entity_type`, `semantic_id`, `year?`, `depth?` | Hierarchical breakdown: subfield → country → institution | `/v1/trees/:root/:id` |
| `get_papers` | `entity_type`, `semantic_id`, `offset?`, `limit?` | Paginated paper list: titles, DOIs, years, citation counts | `/v1/works/:etype/:id/:from` |
| `get_author_peers` | `semantic_id` | 5 closest peers + subfield heatmap data | `/v1/author-peers/:asem` |
| `get_paper_profile` | `semantic_id` | Paper citation DAG, impact metrics | `/v1/paper-profile/:asem` |
| `find_citation_path` | `author_id`, `target_paper_id` | Citation chain connecting author to paper | path-to-paper page data |
| `find_collaboration_path` | `author_id_a`, `author_id_b` | Co-authorship chain between two authors | path-to-person page data |
| `lookup_by_orcid` | `orcid` | Author profile if found | `/v1/orcid/:id` |
| `lookup_by_openalex_id` | `entity_type`, `oa_id` | Semantic ID resolution | `/v1/sem-id-via-oa/:etype/:id` |
| `get_top_entities` | `entity_type?` | Featured/top entities per type | `/v1/tops` |
| `compare_entities` | `entity_type`, `ids: list` | Side-by-side shallow trees for multiple entities | `/v1/shallows/:root?ids[]` |

**New tools (require backend work):**

| Tool | Parameters | Returns | Why |
|------|-----------|---------|-----|
| `search_papers` | `query: str`, `year_range?`, `subfield?` | Papers matching keywords in title | Most common agent need — "find papers about X" |
| `get_field_landscape` | `subfield_id` | Top authors, institutions, sources, recent trends | Agents mapping a research area |
| `get_entity_stats` | `entity_type`, `semantic_id` | Numeric summary: total papers, citations, h-index proxy, year range, top subfields | Quick factual answers without full tree |
| `batch_lookup` | `identifiers: list[{type, id}]` | Batch resolution of DOIs, ORCIDs, OA IDs → profiles | Agents processing bibliographies |

### 1.2 Resources (readable context)

Resources provide background knowledge agents can pull when needed.

| Resource URI | Content | Purpose |
|-------------|---------|---------|
| `rankless://schema/entity-types` | Entity type definitions, ID formats, counts | Agent learns what it can query |
| `rankless://schema/discipline-hierarchy` | Full domain → field → subfield → topic tree | Agent understands classification system |
| `rankless://schema/tree-breakdowns` | Available tree breakdown paths per entity type | Agent knows how to parameterize tree queries |
| `rankless://data/top-entities/{etype}` | Pre-computed top entities | Quick discovery without search |
| `rankless://data/subfield-list` | All 252 subfields with IDs and parent fields | Agent can filter/scope by discipline |

### 1.3 Prompts (reusable workflows)

Prompts are pre-built templates for common multi-step agent tasks.

| Prompt | Description | Steps |
|--------|-------------|-------|
| `literature_review` | Survey a research topic | Search papers → get top authors → get field landscape → synthesize |
| `expert_discovery` | Find researchers in a niche | Search subfields → get top entities → get author profiles → rank |
| `institutional_comparison` | Compare research programs | Get profiles for N institutions → compare trees → summarize strengths |
| `author_impact_report` | Comprehensive author analysis | Get profile → get peers → get papers → get citation tree → narrative |
| `citation_provenance` | Trace how an idea spread | Get paper profile → follow citation DAG → find key intermediaries |
| `field_mapping` | Map a discipline's structure | Get subfield → get top authors/institutions/sources → identify clusters |

---

## 2. New Features Required

### 2.1 Paper/Keyword Search (high priority)

**The single most impactful addition.** Right now agents can only find entities by name — they can't answer "find papers about graph neural networks for drug discovery."

**Implementation approach:**
- Index paper titles in `muwo_search` alongside existing entity name indices
- Papers are already loaded as `WorksNames` — add a `NameState` for papers
- Challenge: ~930k papers is 4-5x larger than the biggest current index (authors at ~211k)
- `muwo_search` trie should handle this — benchmark to confirm
- Expose as `/v1/names/papers?q=` or dedicated `/v1/search-papers?q=&year_from=&year_to=&subfield=`

**Stretch:** Lightweight inverted index over title tokens for boolean keyword queries (faster than trie substring for multi-word factual lookups). Could reuse the trie's word-boundary logic.

### 2.2 Entity Stats Endpoint (medium priority)

Quick numeric summary without building a full tree. Agents asking "how many papers has author X published?" shouldn't need to parse a tree response.

```
GET /v1/stats/:etype/:semantic_id
→ { papers: u32, citations: u32, top_subfields: [(name, count)], year_range: [u16, u16] }
```

Most of this data is already computed — it's just not exposed as a flat endpoint. Pull from coordinates (citations/papers are the raw values behind the z-scores), `WorkCountMarker`, and the subfield citation array.

### 2.3 Batch Endpoint (medium priority)

```
POST /v1/batch
[{tool: "get_entity_profile", params: {etype: "authors", id: "david-baker"}}, ...]
→ [{result: ...}, ...]
```

Agents processing a bibliography or comparing multiple entities make many sequential calls. A batch endpoint cuts round-trips. Straightforward to implement as a dispatcher over existing handlers.

### 2.4 DOI Lookup (low effort, high value)

```
GET /v1/doi/:doi
→ Paper profile or redirect to paper-profile
```

DOIs are already stored as `WorkDois`. Add a hash map at startup (DOI string → work dm_id). Agents constantly work with DOIs from user-pasted references.

### 2.5 Structured Tree Response Simplification (medium priority)

Current tree responses are optimized for the SVG frontend — deeply nested, with internal IDs. Add an `?format=flat` or `?format=summary` query param that returns a simplified structure:

```json
{
  "entity": "MIT",
  "breakdown": [
    {"subfield": "Artificial Intelligence", "papers": 1234, "citations": 56789, "top_paper": {...}},
    {"subfield": "Condensed Matter", "papers": 890, ...}
  ]
}
```

This makes tree data immediately usable by agents without parsing the visualization-oriented structure.

### 2.6 Rate Limiting & API Keys (for launch)

- Anonymous tier: 100 req/min (sufficient for demo, light agent use)
- Keyed tier: 1000 req/min
- Key issuance tied to "work-for-us" system (see section 4)

---

## 3. Business Model & Benefits

### 3.1 Why Give It Away

- **Marginal cost is near-zero.** Binary data is memory-mapped, queries are CPU-bound but fast (sub-ms for most endpoints). An agent doing a 20-query research session costs less than serving one page with SVGs
- **Network effect.** Every agent that uses Rankless MCP teaches its users that Rankless exists. Agent-generated citations link back to Rankless entity pages
- **Data exhaust is valuable.** Agent query patterns reveal what researchers and tools actually need — which entities are underserved, which workflows are common, what data gaps exist
- **Moat building.** First-mover as the MCP source for citation data. OpenAlex's own API is REST/JSON and slow by comparison. Semantic Scholar has no MCP. Being the default tool that agents reach for is a durable advantage

### 3.2 What We Harvest (Ethically)

From agent interactions (no PII, no query content stored beyond aggregates):

- **Query pattern analytics:** Which entity types are most queried? Which tools are most used? What's the typical session length?
- **Coverage gaps:** Queries that return zero results → entities or papers we should add
- **Workflow fingerprints:** Common tool-call sequences → informs which prompts to build, which UI features to prioritize
- **Subfield demand heat map:** Which research areas are most queried → informs where to invest in data enrichment
- **Error patterns:** Which queries fail or return unexpected results → quality signal

### 3.3 Attribution & Backlinks

Every MCP response includes a `rankless_url` field pointing to the web UI page for that entity. Agents citing data should link back. This drives organic traffic from agent-generated reports, papers, and analyses.

---

## 4. "Work-for-Us" Agent Exchange

The core idea: agents can earn elevated API access by performing lightweight tasks that are expensive for us to do manually but trivial for an LLM in-context.

### 4.1 Task Types

| Task | Agent Input | Agent Output | Our Benefit |
|------|------------|-------------|-------------|
| **Name disambiguation** | Two author records with similar names + their papers | "Same person" / "different people" + confidence | Improves entity deduplication |
| **Affiliation resolution** | Author + list of possible institutions | Best match + reasoning | Fills gaps in institution linkage |
| **Topic classification** | Paper title + abstract snippet | Most fitting subfield(s) from our taxonomy | Improves topic coverage |
| **Translation verification** | Entity name in original script + our romanization | Correct/incorrect + correction | Fixes transliteration errors |
| **Relevance judgment** | Two papers + "is A a meaningful citation of B?" | Yes/no + reasoning | Citation quality signal |

### 4.2 Mechanism

```
1. Agent calls `request_elevated_access`
2. Server returns a task (e.g., disambiguate these 3 author pairs)
3. Agent submits answers via `submit_task_results`
4. Server validates (cross-check against known answers or consensus)
5. On pass: returns API key with elevated rate limit (e.g., 7-day validity, 1000 req/min)
6. On fail: can retry with different tasks
```

**Key design principles:**
- Tasks must be completable in-context (no external lookups required) — we provide all needed data
- Each task takes <30 seconds of agent compute — must not feel like a burden
- Validation uses gold-standard tasks (known answers) mixed with real tasks (consensus from multiple agents)
- Rate limit elevation is generous enough to feel worth it, cheap enough for us to serve
- Tasks are idempotent — same task can be given to multiple agents for consensus

### 4.3 Quality Control

- **Gold tasks:** 20% of tasks have known answers. Agents that fail gold tasks don't get keys
- **Consensus:** Real tasks require 3+ agreeing agents before we act on the result
- **Reputation:** Agents (identified by API key lineage) build trust scores over time. High-trust agents get harder, higher-value tasks and longer key validity
- **Audit log:** All task responses stored with agent ID for later review

### 4.4 What This Enables

At scale, this creates a distributed data-improvement engine where the cost is borne by agent compute (which is already being spent) and the benefit accrues to data quality. A few hundred agents doing a few tasks each per day could process thousands of disambiguation decisions monthly — work that would otherwise require a dedicated team.

---

## 5. Implementation Phases

### Phase 1 — MVP (1-2 weeks)

**Goal:** Working MCP server that an agent can use for basic research tasks. Demoable.

**Scope:**
- Standalone MCP server process (Python or TypeScript) that proxies to the existing Rust backend on localhost:3038
- Implement 6 core tools:
  - `search_entities` (wraps `/v1/names`)
  - `get_entity_profile` (wraps `/v1/views`)
  - `get_citation_tree` (wraps `/v1/trees`, with response simplification in the MCP layer)
  - `get_papers` (wraps `/v1/works`)
  - `get_author_peers` (wraps `/v1/author-peers`)
  - `lookup_by_orcid` (wraps `/v1/orcid`)
- 2 resources:
  - `rankless://schema/entity-types`
  - `rankless://schema/discipline-hierarchy`
- 1 prompt:
  - `author_impact_report`
- Response simplification: flatten tree responses into agent-friendly JSON in the MCP layer (no backend changes)
- Basic stdio transport (for local Claude Desktop / claude-code integration)

**No backend changes required.** The MCP server is a thin translation layer.

**Demo scenario:** "Tell me about David Baker's research impact" → agent uses search → profile → tree → peers → synthesizes a report with Rankless links.

### Phase 2 — Paper Search & Stats (2-3 weeks after MVP)

- Add paper title search to `muwo_search` / new endpoint
- Add `/v1/stats/:etype/:id` endpoint to Rust backend
- Add DOI lookup endpoint
- Add `search_papers`, `get_entity_stats`, `lookup_by_doi` tools to MCP
- SSE transport for remote access (agents not on same machine)
- Basic rate limiting (IP-based, no keys yet)

### Phase 3 — Batch, Paths & Remote Access (2-3 weeks)

- Batch endpoint in Rust backend
- Citation/collaboration path tools
- `compare_entities` tool (wraps shallows)
- `get_field_landscape` tool
- Deploy MCP server alongside web server (same host, separate port or path)
- HTTP+SSE transport with CORS for remote agents

### Phase 4 — Work-for-Us & Keys (3-4 weeks)

- Task generation pipeline (select disambiguation candidates from data)
- Gold task set curation (manual labeling of ~200 ground truth pairs)
- `request_elevated_access` / `submit_task_results` tools
- API key issuance, storage, and rate limit enforcement
- Task result aggregation and consensus logic
- Integration of validated results back into pipeline

### Phase 5 — Analytics & Optimization (ongoing)

- Query pattern dashboard
- Coverage gap reports
- Response caching tuned for agent access patterns (likely different from web)
- Additional prompts based on observed workflows
- Prompt/resource refinements based on agent feedback patterns

---

## 6. Technical Architecture

```
┌─────────────────┐     stdio/SSE/HTTP      ┌─────────────────────┐
│   AI Agent      │ ◄──────────────────────► │   MCP Server        │
│ (Claude, GPT,   │      MCP Protocol        │   (Python/TS)       │
│  custom)        │                          │                     │
└─────────────────┘                          │  - Tool handlers    │
                                             │  - Response shaping │
                                             │  - Rate limiting    │
                                             │  - Task management  │
                                             └────────┬────────────┘
                                                      │ HTTP (localhost)
                                                      ▼
                                             ┌─────────────────────┐
                                             │  Rust Backend       │
                                             │  (rankless_server)  │
                                             │  port 3038          │
                                             │                     │
                                             │  - Binary data      │
                                             │  - muwo_search      │
                                             │  - Tree engine      │
                                             │  - Cache            │
                                             └─────────────────────┘
```

**MCP server is a separate process**, not embedded in the Rust server. Reasons:
- MCP SDKs are mature in Python and TypeScript, not Rust
- Response shaping (flattening trees, adding URLs) is simpler in a scripting language
- Can iterate on MCP layer without rebuilding/restarting the Rust backend
- Rate limiting and task logic don't belong in the data-serving hot path

**Language choice:** Python (with `mcp` SDK). Reasons:
- Existing Python tooling in `pyscripts/` — same ecosystem
- `mcp` Python SDK is the reference implementation
- `httpx` for async proxying to Rust backend
- Easier to prototype the work-for-us task logic

**File location:** `mcp_server/` at project root.

---

## 7. MVP Checklist

- [ ] `mcp_server/` directory with `pyproject.toml` (uv-managed)
- [ ] `mcp_server/server.py` — MCP server entry point
- [ ] `mcp_server/tools.py` — tool handler implementations
- [ ] `mcp_server/resources.py` — resource definitions
- [ ] `mcp_server/prompts.py` — prompt templates
- [ ] `mcp_server/client.py` — async HTTP client to Rust backend
- [ ] `mcp_server/response_shaping.py` — tree flattening, URL generation
- [ ] Test with Claude Desktop or claude-code MCP config
- [ ] Demo script: end-to-end "research David Baker" session
- [ ] Update `docs/overview.md` and `docs/tree-description.md`
