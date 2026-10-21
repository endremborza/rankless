# Reporting

The traffic + performance report on the live site is [ramore](https://github.com/endremborza/ramore) (`ramore report`), configured by `ramore.toml` at the repo root and run from there; how the report works, what it stores and the log format it parses are in ramore's `docs/report.md`. The report store is `reports-v2/` (gitignored) and the site publishes to this repo's `gh-pages` branch.

## What rankless gives it

- **The box:** the live box over the `rankless-live` ssh alias. ramore installs its own side there (its request log and the `[metrics]` sampler, see ramore's `docs/report.md`), and every report run reinstalls it when it is missing or outdated. The request log is an http-level `access_log`, so it covers every server block `pyscripts/deploy.py` writes only because none of them sets an `access_log` of its own (`test_deploy.py` holds that). Live instances are promoted alphas, so the log mixes live traffic with the box's prior alpha vhosts and junk hitting it by raw IP or spoofed Host; `[source] hosts` keeps the live domains (`LIVE_DOMAIN`, `MAIN_DOMAIN`, `LIVE_BACKEND` in `pyscripts/hosts.py`).
- **The units:** `[metrics] units` names the backend, the frontend workers, the MCP server and nginx; the box page of the local site charts their memory and open files.
- **The routes:** the `/v1` paths from `API_ROUTES` (`rankless_server/src/routes.rs`, `#[wire]`, so `make types` carries a new endpoint into the report) and the frontend's from the SvelteKit tree under `src/routes`.
- **Search and logins:** `[search]` names the name-search route, the bot classifier's search signal; `[login]` names the ORCID OAuth return and the status it answers once the session is set (4xx = a failed callback).
- **The poster:** `[site] include` publishes `docs/poster/` under the site.

## Runbook: promoting a new live instance (scrub history)

1. `make report-reset` (type `scrub` to confirm; `ARGS="--local-only"` keeps the published site, `ARGS="--yes"` skips the prompt): wipes `reports-v2/` and force-pushes an empty `gh-pages` (CNAME kept).
2. Promote / deploy the new live box (`rankless-live` points at it).
3. The next `make reporting` run installs ramore's side on the new box, starts from the new log's tail as a first run, drops non-live hosts, archives, renders and publishes fresh.
