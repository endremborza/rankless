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
  across days); UA → bucketed family + bot class; referrer → registered domain. Run-log error
  text (`error`/`trace`) can echo raw log content, so it is dropped from the public site and
  kept only locally.
- **Classification:** paths templated to a small set of route shapes before aggregation;
  sessions = `(ip, ua)` by 30-min idle window; bot/human = rule-based scorer (hard signals + soft
  aggregation), bucket per session.
- **nginx log line** carries `cs=$upstream_cache_status host=$host` (emitted by
  `pyscripts/deploy.py`), always present. `cs` gives the cache hit rate; `host` lets the report
  keep only live-vhost rows — live instances are **promoted alphas**, so their access.log mixes
  live traffic with the box's prior alpha vhosts and junk hitting it by raw IP / EC2 hostname /
  spoofed Host. `parse.keep_live_hosts` keeps an allowlist (`config.LIVE_HOSTS`), robust where an
  `alpha*` prefix denylist let the old alpha box's raw IP score as live. `host` is never persisted.
- **Publish:** `pyscripts/reporting/publish.py` does a gh-pages worktree push of `site-public/`
  (public repo, anonymized site only). One-time GitHub setup: repo Settings → Pages → source =
  `gh-pages` branch, root; optional custom domain via a `CNAME` file. First run creates the orphan
  `gh-pages` branch if absent remotely.
- **Reset:** `make report-reset` wipes the local `reports-v2/` history and force-pushes an empty
  `gh-pages` (preserving `CNAME`); the next run rebuilds from scratch. Run it when promoting a new
  live instance. `ARGS="--local-only"` keeps the published site.

## Runbook: promoting a new live instance (scrub history)

A live instance is a promoted alpha, so its access.log mixes prior alpha traffic with live.
`parse.keep_live_hosts` filters rows going forward; before the switch, wipe the old history so
nothing from the prior box lingers:

1. `make report-reset` — type `scrub` to confirm. Wipes local `reports-v2/` (archive,
   aggregates, sites, run logs, `state.json`, `salts.json`) and force-pushes an empty
   `gh-pages` (CNAME kept).
2. Promote / deploy the new live box (`rankless-live` SSH id points at it).
3. Next hourly `make reporting` run: `state.last_inode == 0` → tails the last ~200k lines,
   drops non-live hosts, archives + renders + publishes fresh.

The reset is idempotent.

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
