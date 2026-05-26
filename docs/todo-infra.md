# To-do — Infrastructure & reporting

Remaining ops/analytics work. Delete a section when it lands.

---

## Reporting v2

Replace `pyscripts/report.py` with a richer static site that runs hourly, archives parsed
nginx events forever (cold-compressed past 90 days), and publishes to GitHub Pages. Two
pillars: **traffic** (bot-vs-human estimation) and **performance** (per-endpoint latency,
cache hit rate, error catalog).

### Architecture summary

- **Run host:** any host with SSH to live; cron hourly; missed runs auto-recover via
  byte-offset bookkeeping.
- **Stack:** Python (pandas + pyarrow + jinja2 + ssh) → static HTML + Plotly.js + DataTables.js
  (both CDN). No Node, no build step.
- **Storage** under `reports-v2/` (gitignored): `archive/YYYY/MM/DD.parquet` (hot, ≤90d,
  one row/request), `archive-cold/YYYY/MM.parquet` (month-merged, >90d, heavy zstd, drops
  free-text columns), `aggregates/{hourly,daily}.parquet`, `state.json`, `salts.json` (daily
  IP-hash salts, never published), `site/` (raw IPs, local only), `site-public/` (anonymized,
  pushed to gh-pages).
- **Anonymization:** IP → `sha256(daily_salt || ip)[:10]` (stable within a day, unlinkable
  across days); UA → bucketed family + bot class; referrer → registered domain.
- **Path templating** to a small set of route shapes before aggregation; **sessions** =
  `(ip, ua)` by 30-min idle window; **bot/human** = rule-based scorer (hard signals + soft
  aggregation), bucket per session.
- **Deploy:** gh-pages worktree push (public repo, anonymized site only).

### Phase 0 — nginx `log_format` adds `$upstream_cache_status` (USER, do first)

Edit `pyscripts/deploy.py` lines ~488–491 to append ` cs=$upstream_cache_status` to the line
(does not alter existing field spacing, so the current parser keeps working until removed):

```python
log_format = '''log_format upstream_time '$remote_addr - $remote_user [$time_local] '
                         '"$request" $status $body_bytes_sent '
                         '"$http_referer" "$http_user_agent"'
                         'rt=$request_time uct="$upstream_connect_time" uht="$upstream_header_time" urt="$upstream_response_time" cs=$upstream_cache_status';'''
```

Then ssh to live, run `tpr.setup_nginx()` + `tpr.restart_nginx()` (or `nginx -s reload`).
**Acceptance:** `tail -1 /var/log/nginx/access.log` ends with `cs=HIT|MISS|BYPASS|-`.

### Phase 6 — publish to gh-pages (USER finalization)

Worktree push of `site-public/` is implemented in `pyscripts/reporting/publish.py`. One-time
setup: GitHub repo Settings → Pages → source = `gh-pages` branch, root. Optional custom
domain via a `CNAME` file. First run creates the orphan `gh-pages` branch if absent remotely.

### Open extension points (not now)

- **Geo / ASN** — needs MaxMind GeoLite2 download + dependency. Skipped initially.
- **goaccess embed** — stretch; run goaccess on the day's filtered raw lines, copy to
  `site-public/goaccess.html`.
- **Alerting** — out of scope (`live_monitoring.py` covers paging).
- **Cohort analysis** (returning vs new) — needs a separate never-published stable-hash file
  (daily salts make cross-day linkage impossible by design).

### Column schemas (reference)

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
session_id     str        # daily-salted, added at archive-write time
```

Cold archive (`archive-cold/YYYY/MM.parquet`): same schema **minus** `path, ua, referrer`.

`state.json`: `{ last_inode, last_size, last_event_ts, last_run, salt_date }`.
`salts.json` (never published): `{ "YYYY-MM-DD": "<hex>", … }`.
