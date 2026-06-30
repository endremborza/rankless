# Reporting

The traffic + performance reporting site (`pyscripts/reporting/`). Runs hourly from any host
with SSH to live, archives parsed nginx events forever (cold-compressed past 90 days), and
publishes an anonymized static site to GitHub Pages. Two pillars: **traffic** (bot-vs-human
estimation) and **performance** (per-endpoint latency, cache hit rate, error catalog).

## Architecture

- **Run host:** any host with SSH to live; cron hourly; missed runs auto-recover via
  byte-offset bookkeeping (`state.json`).
- **Stack:** Python (pandas + pyarrow + jinja2 + ssh) → static HTML + Plotly.js + DataTables.js
  (both CDN). No Node, no build step.
- **Storage** under `reports-v2/` (gitignored):
  - `archive/YYYY/MM/DD.parquet` — hot, ≤90d, one row per request.
  - `archive-cold/YYYY/MM.parquet` — month-merged, >90d, heavy zstd, drops free-text columns.
  - `aggregates/{hourly,daily}.parquet`, `state.json`, `salts.json` (daily IP-hash salts, never
    published), `site/` (raw IPs, local only), `site-public/` (anonymized, pushed to gh-pages).
- **Anonymization:** IP → `sha256(daily_salt || ip)[:10]` (stable within a day, unlinkable
  across days); UA → bucketed family + bot class; referrer → registered domain.
- **Classification:** paths templated to a small set of route shapes before aggregation;
  sessions = `(ip, ua)` by 30-min idle window; bot/human = rule-based scorer (hard signals + soft
  aggregation), bucket per session.
- **nginx log line** carries `cs=$upstream_cache_status host=$host` (emitted by
  `pyscripts/deploy.py`), so cache hit-rate and per-host (live vs alpha) splits are available.
- **Publish:** `pyscripts/reporting/publish.py` does a gh-pages worktree push of `site-public/`
  (public repo, anonymized site only). One-time GitHub setup: repo Settings → Pages → source =
  `gh-pages` branch, root; optional custom domain via a `CNAME` file. First run creates the orphan
  `gh-pages` branch if absent remotely.

## Column schemas

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
