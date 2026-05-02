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

## Phase 6 — Publish to gh-pages (manual finalization)

Worktree-based push of `site-public/` is implemented in `pyscripts/reporting/publish.py`. **One-time user setup**:
1. In GitHub: repo Settings → Pages → source = `gh-pages` branch, root.
2. (Optional) Custom domain: add a `CNAME` file via env var or extend `publish_to_ghpages` if you want `reports.rankless.org`.
3. The first run will create the `gh-pages` branch as orphan if it does not exist remotely.

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
