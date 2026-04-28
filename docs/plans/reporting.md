# Reporting v2

Replace `pyscripts/report.py` with a richer, locally-built static site that runs hourly, archives parsed nginx events forever (cold-compressed past 90 days), and is published to GitHub Pages.

Two pillars: **traffic** (especially bot-vs-human estimation) and **performance** (per-endpoint latency, cache hit rate, error catalog).

When a phase is complete, **delete it from this file** (the user tracks progress via git, not crossed-out bullets).

---

## Architecture summary

- **Run host**: user laptop or home server (any host with SSH access to live). Cron hourly. Missed runs auto-recover via byte-offset bookkeeping.
- **Stack**: Python (pandas + pyarrow + jinja2 + paramiko-or-ssh-cli) → static HTML + Plotly.js (CDN) + DataTables.js (CDN). No Node. No build step.
- **Storage** under `reports-v2/` (gitignored):
  - `archive/YYYY/MM/DD.parquet` — one row per request, hot tier (≤90d)
  - `archive-cold/YYYY/MM.parquet` — month-merged cold tier (>90d), heavy zstd, drops free-text columns
  - `aggregates/{hourly,daily}.parquet` — pre-computed rollups (all time)
  - `state.json` — bookkeeping (last byte offset, inode, salt rotation)
  - `salts.json` — daily salts for IP hashing (kept locally, never published)
  - `site/` — generated site with **raw IPs** (local browsing only, never pushed)
  - `site-public/` — anonymized site, pushed to gh-pages
- **Anonymization**: IP → `sha256(daily_salt || ip)[:10]` (stable within a day, unlinkable across days). UA strings → bucketed family + bot class only. Referrers → registered domain only.
- **Path templating**: paths with IDs/queries are normalized to a small set of route shapes before any aggregation.
- **Sessions**: `(ip, ua)` grouped by 30-min idle window.
- **Bot/human classifier**: rule-based scorer with explicit hard signals + soft signal aggregation. Output bucket per session.
- **Deploy**: gh-pages worktree push (no orphan-branch dance). Public repo, anonymized site only.

---

## Phase 0 — nginx log_format adds `$upstream_cache_status` (USER, do first)

Edit `pyscripts/deploy.py` lines 488–491. The change appends ` cs=$upstream_cache_status` to the line — **does not** alter spacing of the existing fields, so the current `report.py` parser (line 117) keeps working until you delete it.

```python
log_format = '''log_format upstream_time '$remote_addr - $remote_user [$time_local] '
                         '"$request" $status $body_bytes_sent '
                         '"$http_referer" "$http_user_agent"'
                         'rt=$request_time uct="$upstream_connect_time" uht="$upstream_header_time" urt="$upstream_response_time" cs=$upstream_cache_status';'''
```

Then: ssh to live and run `tpr.setup_nginx()` + `tpr.restart_nginx()` (or `nginx -s reload`). Verify a tail shows `cs=HIT|MISS|BYPASS|-` at line end.

**Acceptance**: `tail -1 /var/log/nginx/access.log` ends with `cs=<status>`.

---

## Phase 1 — Skeleton + log puller + parser

Create package `pyscripts/reporting/` with:

```
pyscripts/reporting/
  __init__.py
  __main__.py        # `python -m pyscripts.reporting [--mode=local|publish]`
  config.py          # paths, env, constants
  state.py           # State dataclass; load/save state.json
  pull.py            # SSH-based incremental log fetch
  parse.py           # nginx line → row
  paths.py           # URL → templated route + query bucket
```

### `config.py`

- `REPORTS_ROOT = Path(os.environ.get("REPORTS_V2_ROOT", "reports-v2"))`
- `LIVE_SSH_ID = os.environ.get("REPORTS_LIVE_SSH_ID", "rankless-live")` (matches `~/.ssh/config` host alias)
- `NGINX_LOG = "/var/log/nginx/access.log"`
- `SESSION_IDLE_MIN = 30`
- `COLD_AFTER_DAYS = 90`
- `IP_HASH_LEN = 10`
- `LINE_RE` — extended regex including optional ` cs=([A-Z\-]+)` at end (optional so we can also parse pre-Phase-0 lines). Field columns:
  `addr, time, method, path, status, size, referrer, ua, rt, uct, uht, urt, cs`

### `state.py`

```python
@dataclass
class State:
    last_inode: int = 0
    last_size: int = 0
    last_event_ts: str = ""   # ISO8601 of latest parsed event
    last_run: str = ""        # ISO8601 of last successful run
    salt_date: str = ""       # YYYY-MM-DD; rotated daily
```

`load() -> State`, `save(s: State)`. Atomic write (tmpfile + rename). `salts.json` keeps a `{date: salt_hex}` map; rotate by adding a new entry when `salt_date != today`.

### `pull.py`

```python
def fetch_new_lines(state: State) -> Iterator[str]:
    """Yields raw log lines from live, idempotent across runs."""
```

Algorithm:
1. SSH `stat -c '%i %s' /var/log/nginx/access.log` → `(inode, size)`.
2. If `inode == state.last_inode` and `size >= state.last_size`: SSH `tail -c +<offset>` where `offset = state.last_size + 1`. Yield lines. Update state to new size.
3. If `inode != state.last_inode` (rotation): SSH `tail -c +<offset>` on `/var/log/nginx/access.log.1` (rest of old file), then `cat /var/log/nginx/access.log` (full new file). Update state to new inode + new size.
4. If `size < state.last_size` and inode same (truncate without rotation, rare): treat as fresh; warn.

Use `subprocess.check_output(["ssh", LIVE_SSH_ID, cmd])` — keep parity with existing `SSHrer`. Don't import `Transper` (no AWS / boto3 dependency in this package).

### `parse.py`

```python
def parse_lines(lines: Iterable[str]) -> pl.DataFrame | pd.DataFrame
```

Use pandas (already in repo) for parity. Output DataFrame columns:
- `t` (datetime64[ns, UTC]) — parsed from `%d/%b/%Y:%H:%M:%S %z`
- `addr` (str)
- `method` (str)
- `path` (str) — full path including query string
- `status` (uint16)
- `size` (uint32)
- `referrer` (str, empty if `-`)
- `ua` (str, empty if `-`)
- `rt`, `uct`, `uht`, `urt` (float32, NaN on `-`)
- `cs` (categorical: HIT/MISS/BYPASS/EXPIRED/REVALIDATED/STALE/UPDATING/-/null)

Drop unparseable lines silently, count them, surface count at run end.

### `paths.py`

```python
def template(path: str) -> tuple[str, dict[str, str]]:
    """Return (route_template, captured_params)."""
```

Hand-rolled regex table, in order, for these route shapes (extracted from `rankless_server/src/main.rs:844-872` and `src/routes/`):

API (`/v1/...`):
- `/v1/names/{etype}` (preserve `?q=` presence as `has_query` bool but drop value)
- `/v1/slice/{etype}/{from}/{to}`
- `/v1/views/{etype}/{semantic_id}`
- `/v1/sem-id-via-oa/{etype}/{oa_id}`
- `/v1/orcid/{orcid_id}`
- `/v1/resolve/work`
- `/v1/resolve/author`
- `/v1/paper-profile/{asem}`
- `/v1/author-peers/{asem}`
- `/v1/trees/{root_type}/{semantic_id}`
- `/v1/shallows/{root_type}`
- `/v1/works/{etype}/{semantic_id}/{from}`
- `/v1/counts`, `/v1/tops`, `/v1/specs/...`

Frontend (SSR or static):
- `/` (root)
- `/about`, `/login`, `/logout`, `/survey`
- `/{rootType}/table`
- `/{rootType}/{...semanticId}`
- `/oa-id/{...}`, `/path-to-person/{...}`, `/pic/{...}`, `/pathlogo/{...}`, `/tiles/{...}`
- `/sitemap*.xml`, `/robots.txt`
- `/dev-login`, `/callback`
- `/api/ledger`, `/api/ledger/{event_id}`, `/api/ledger-status`, `/api/papers/claim`, `/api/papers/disown`, `/api/papers/merge`, `/api/authors/merge-request`, `/api/survey`

Anything unmatched → `_unknown`. Always log the top 20 unmatched paths to stderr per run so the table can be expanded.

### Tests

`pyscripts/reporting/tests/test_parse.py` and `test_paths.py`: hand-write ~20 fixture log lines (with and without cs= field, with and without UA, with and without `-` fields) and assert parsed rows + templated routes.

**Acceptance**:
- `python -m pyscripts.reporting --dry-run` pulls a tail, parses, prints summary, does **not** write anything.
- All fixture tests pass.

---

## Phase 2 — Archive (hot + cold)

Create `pyscripts/reporting/archive.py`.

```python
def write_events(df: pd.DataFrame) -> None:
    """Append parsed events to per-day parquet files in archive/. Idempotent: dedupes by (t, addr, path, status)."""

def compress_cold(today: dt.date) -> None:
    """Move day-files older than COLD_AFTER_DAYS into archive-cold/YYYY/MM.parquet, dropping ua/referrer free-text."""
```

Hot-tier write:
1. Group `df` by date (UTC).
2. For each date, read existing `archive/YYYY/MM/DD.parquet` (if exists), concat, dedupe on `(t, addr, path, status, size)`, sort by `t`, rewrite atomically via tempfile + rename.
3. Use pyarrow with `compression="zstd"`, `compression_level=3` (hot tier — fast).

Cold-tier compaction (run at end of every cron, cheap if nothing to do):
1. List hot-tier files with date < `today - COLD_AFTER_DAYS`.
2. Group by `(YYYY, MM)`. For each month-group:
   - Read all day-files
   - Project to a slimmed schema: keep `t, addr, route_template (computed), status, size, rt, urt, cs, ua_family, bot_class, referrer_domain` — **drop** `path`, `ua`, `referrer` (raw text)
   - Write `archive-cold/YYYY/MM.parquet` with `compression="zstd"`, `compression_level=22`, `use_dictionary=True`, row-group size = 256k
   - Delete the source day-files only after successful write
3. The renderer reads from both `archive/` and `archive-cold/` — only the longer time-range pages need cold tier.

**Acceptance**:
- Run twice on same fetched batch → archive size stable, no duplicates.
- Mock 100 days of data; cold compaction reduces total bytes by ≥5×; row count preserved per (route, day) group.

---

## Phase 3 — Sessions + bot/human classifier

Create `pyscripts/reporting/sessions.py` and `classify.py`.

### `sessions.py`

```python
def assign_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Adds a `session_id` column. Sessions = same (addr, ua) split by >30min gap."""
```

- Sort by `(addr, ua, t)`.
- New session whenever `t - t.shift() > 30min` or `(addr, ua)` changes.
- `session_id = sha256(salt_for_session_start_date + addr + ua + start_ts)[:12]`.

### `classify.py`

Per-session classification with explicit signals. Output table:
`session_id, addr, ua, start, end, n_req, route_diversity, bot_class, signals_json`.

**Hard bot** (any of):
- UA matches `r"bot|crawl|slurp|spider|mediapartners|facebookexternalhit|whatsapp|telegram|python-(requests|urllib)|curl|wget|Go-http-client|java/|okhttp|Apache-HttpClient|libwww|AhrefsBot|SemrushBot|MJ12bot|GPTBot|ClaudeBot|Bytespider|PerplexityBot"` (case-insensitive)
- UA empty or `-`
- Visited `/robots.txt` or `/sitemap*.xml`
- All requests are HEAD

**Hard human** (any of):
- POST to `/api/papers/{claim,disown,merge}` or `/api/authors/merge-request`
- GET `/callback` with `?code=` (ORCID OAuth)
- Search: `/v1/names/{etype}` with non-empty `?q=`
- Loaded both an HTML page and `/tiles/`, `/pic/`, or `/pathlogo/` from same session within 5s of the page request

**Soft signals** (each adds a score; threshold +3 → likely_human, −3 → likely_bot):
- UA contains `Mozilla` AND (`Chrome|Safari|Firefox|Edge`): +2
- UA is plain `Mozilla/5.0` only (no engine): −2
- Referrer present and not self-domain: +1
- ≥3 distinct route templates visited: +1
- ≥20 requests in <30s: −2
- Diurnal: requests cluster in a <12h window: +1; flat across 24h: −1
- Cache HIT rate >90% with no asset loads: −1 (looks like SSR-only scraping)

Final bucket: `bot_known | bot_likely | human_known | human_likely | unknown`.

`signals_json` records which rules fired (for the per-session debug page).

**Acceptance**:
- Hand-craft 8 fixture sessions covering each bucket; assertion test in `test_classify.py`.
- On real one-day batch: bucket counts printed; sanity check `bot_known + bot_likely + human_known + human_likely > 90%` of sessions.

---

## Phase 4 — Aggregates

Create `pyscripts/reporting/aggregate.py`.

```python
def rebuild_aggregates() -> None:
    """Recompute aggregates/hourly.parquet and aggregates/daily.parquet from archive."""
```

Read all hot+cold archives, group by `(time_bucket, route_template, status_family, bot_class, cs)`, compute:
- `n` (count)
- `bytes` (sum size)
- `urt_mean, urt_p50, urt_p95, urt_p99, urt_p999`
- `n_429, n_5xx, n_4xx`
- `n_cache_hit, n_cache_miss, n_cache_bypass`

Hourly is full resolution (everything). Daily is rolled-up further.

Cheap to do every run (full rebuild is fine — single pass over parquet, ~few seconds for a year of data).

**Acceptance**:
- Aggregate row counts in daily match sums in hourly within 1 row tolerance.
- KPIs computed from aggregates match KPIs computed from raw archive on a sample day.

---

## Phase 5 — Static site renderer

Create `pyscripts/reporting/render/` with one module per page and Jinja templates in `pyscripts/reporting/templates/`.

```
render/
  __init__.py       # render_all(mode: Literal["local", "public"])
  base.py           # jinja env, shared filters, asset URLs
  landing.py
  traffic.py
  performance.py
  sessions.py
  runs.py
  errors.py
templates/
  _base.html.j2
  _kpi_card.html.j2
  landing.html.j2
  traffic.html.j2
  performance.html.j2
  sessions_index.html.j2
  session_detail.html.j2
  runs_index.html.j2
  run_detail.html.j2
  errors.html.j2
```

### Modes

- `mode="local"` → output `site/`, IPs raw, full UA strings shown.
- `mode="public"` → output `site-public/`, IPs replaced with their daily hash, UA → `ua_family`, referrer → registered domain.

### Pages

**`/index.html` (landing)**: KPI cards (last 1h / 24h / 7d / 30d) for: total requests, unique sessions, human-session %, error rate, p99 urt, cache hit %. Each card shows a sparkline (Plotly mini). Below: links to other pages, last-run timestamp.

**`/traffic.html`**: 
- Bot vs human stacked area over 30 days
- Top 30 user agents (by sessions) with class
- Top 30 referrers
- Top 30 source paths (for human-likely sessions only — true content popularity)
- Status code distribution (donut)

**`/performance.html`**:
- Per-route-template table (DataTables): n, p50, p95, p99, error %, cache-hit %, sparkline of p99 over 24h
- Per-route latency multi-line chart over 24h (toggle which routes)
- Cache hit % over time
- Slow-request log (top 100 slowest urt in last 24h, with route + status + cs)

**`/errors.html`**: 5xx and 4xx (excluding 404 from bots) catalog. Group by (status, route_template); show count, last seen, sample paths.

**`/sessions/index.html`**: filter (bot_class, date), table of sessions linking to detail.

**`/sessions/<session_id>.html`**: chronological request list, signals_json shown, mini map of route diversity.

**`/runs/index.html`**: index of every cron run with KPIs.

**`/runs/<ts>.html`**: snapshot of that run's pull (lines pulled, time range covered, parse errors, archive write counts, top unmatched paths).

### Assets

CDN-only: Plotly.js (`https://cdn.plot.ly/plotly-2.x.min.js`), DataTables.js (`https://cdn.datatables.net/...`), a 200-line hand-written `style.css` copied into output.

### Templates

`_base.html.j2` provides nav, dark theme, footer with last-run time + commit hash + mode badge. Pages extend it.

**Acceptance**:
- `python -m pyscripts.reporting render --mode=local` produces a fully navigable site under `reports-v2/site/`.
- `python -m pyscripts.reporting render --mode=public` produces `reports-v2/site-public/` with no raw IPs (grep test: `grep -rE '\b\d+\.\d+\.\d+\.\d+\b' reports-v2/site-public/` returns nothing).
- Open both in a browser, all charts render, all tables sortable.

---

## Phase 6 — Publish to gh-pages

Create `pyscripts/reporting/publish.py`.

```python
def publish_to_ghpages(repo_dir: Path = Path(".")) -> None:
    """Push site-public/ to gh-pages branch via worktree."""
```

Algorithm:
1. Worktree path: `/tmp/rankless-ghpages` (gitignored).
2. If absent: `git worktree add -B gh-pages /tmp/rankless-ghpages origin/gh-pages || git worktree add --orphan gh-pages /tmp/rankless-ghpages`.
3. `git -C /tmp/rankless-ghpages reset --hard` (always start clean).
4. Empty the worktree (preserve `.git`), then `rsync -a --delete reports-v2/site-public/ /tmp/rankless-ghpages/`.
5. Add `.nojekyll` (so paths starting with `_` work).
6. `git -C ... add -A; git -C ... commit -m "report $(date -Iminutes)"; git -C ... push origin gh-pages`.

GitHub Pages settings (one-time, user does manually): repo settings → Pages → source = gh-pages branch, root.

**Custom domain** (optional, ask user): if user wants `reports.rankless.org`, add `CNAME` file to `site-public/` and CNAME the subdomain to `<user>.github.io`.

**Acceptance**:
- After first run: `https://<user>.github.io/rankless/` (or custom CNAME) shows the landing page.
- Subsequent runs only push diffs (commit small).

---

## Phase 7 — Entrypoint, scheduling, cleanup

### `__main__.py`

CLI:
```
python -m pyscripts.reporting              # full run: pull → archive → aggregate → render(local) → render(public) → publish
python -m pyscripts.reporting --no-publish # skip gh-pages push (default for ad-hoc runs)
python -m pyscripts.reporting --no-pull    # use existing archive only
python -m pyscripts.reporting --render-only
python -m pyscripts.reporting --dry-run
```

Each step logs a structured JSON line to `reports-v2/logs/run-YYYYMMDD.log` and to stdout. Run-detail page reads these.

### Scheduling

Provide `cloudinit/rankless-reporting.{service,timer}` (systemd user units). Service runs the entrypoint with `--publish`. Timer is hourly:13 (off the top of the hour to dodge nginx rotation, which usually runs at :00).

Document in this plan how to install:
```
mkdir -p ~/.config/systemd/user
cp cloudinit/rankless-reporting.* ~/.config/systemd/user/
systemctl --user enable --now rankless-reporting.timer
```

### Cleanup

Once Phases 1–7 are verified end-to-end on a real day of data:
- Delete `pyscripts/report.py`
- Delete `pyscripts/log_parsing.py` (dead, used only by the old `log-anal.sh` workflow which we can adapt or also delete)
- Update `logs/log-anal.sh`: either delete or rewrite to use the new archive (read parquet, optionally still pipe a filtered view to goaccess for the embedded `/goaccess.html` page).
- Add to `.gitignore`: `reports-v2/`, `/tmp/rankless-ghpages/`.

**Acceptance**:
- `systemctl --user list-timers` shows the timer next-fire on the hour.
- Two consecutive timer fires complete cleanly with no duplicate archive rows.
- Public site updates after each fire.

---

## Open extension points (do not implement now)

- **Geo / ASN**: requires MaxMind GeoLite2 download + dependency. Skipped initially. Add later if useful.
- **goaccess embed**: stretch. After Phase 6 stable, add a step that runs goaccess on the day's filtered raw lines and copies output to `site-public/goaccess.html`.
- **Alerting**: out of scope here. `live_monitoring.py` already covers paging.
- **Cohort analysis** (returning vs new sessions): possible once daily salts make linkage impossible across days — would need a separate, never-published "stable hash" file kept only locally.

---

## Quick-reference: column schemas

Hot archive (`archive/YYYY/MM/DD.parquet`):
```
t              datetime64[ns, UTC]
addr           str
method         category
path           str
route_template category   # added at archive-write time
status         uint16
size           uint32
referrer       str
ua             str
ua_family      category   # added at archive-write time
bot_class      category   # added at archive-write time
rt, uct, uht, urt  float32
cs             category
session_id     str        # added at archive-write time, daily-salted
```

Cold archive (`archive-cold/YYYY/MM.parquet`): same schema **minus** `path, ua, referrer` (the high-entropy text columns).

Daily salts (`salts.json`, never published):
```json
{ "2026-04-28": "<hex>", "2026-04-27": "<hex>", ... }
```

State (`state.json`):
```json
{
  "last_inode": 12345,
  "last_size": 9876543,
  "last_event_ts": "2026-04-28T13:00:00+00:00",
  "last_run": "2026-04-28T13:13:02+00:00",
  "salt_date": "2026-04-28"
}
```
