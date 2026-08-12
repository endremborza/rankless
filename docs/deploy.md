# Deploy / release flow

One release = five stages, each one command, run in order on the primary data box
(the machine holding `$OA_ROOT` and AWS + worker-fleet ssh access). Stages are thin
make aliases over `uv run -m pyscripts release <stage>` (`pyscripts/release.py`);
box/EC2 primitives are `uv run -m pyscripts deploy <action>` (`pyscripts/deploy.py`);
pass flags via `ARGS`. Every stage is idempotent — rerunning resumes or verifies.

```
make refresh-data       # data + backend + showcase from the current snapshot/ledger
make commit-artifacts   # commit + push exactly the generated files
make warm-caches        # precompute the response cache across the worker fleet
make ship-alpha         # fresh large alpha box (full setup + DB handoff + smoke)
make promote            # flip alpha to live (DB catch-ups + smoke)
```

`refresh-data` and `warm-caches` take a pipeline lock (`/tmp/rankless-pipeline.lock`):
`/tmp/dmove-parts` is shared, two data pipelines on one box corrupt each other.

## refresh-data

Merges the live box's user DB into the local copy (so the ledger export sees every
accepted claim), then: `make filter extend_csvs` → forced gen-ladder rebuild →
`make lib_data_generation restart-service homepage_showcase`.

- `ARGS="--from-snapshot"` prepends `make to-csv` (a new OpenAlex snapshot landed;
  `make download-snapshot` stays manual).
- `ARGS="--no-db-pull"` skips the DB merge (box without AWS access).
- Ends by writing the data-root **stamp** (`$OA_ROOT/stamp`, `<run_id>:<digest12>`)
  before restarting the backend — the backend echoes it in `/v1/specs.version`,
  which is what the warm fleet's preflight handshake compares. After any manual
  data surgery: `uv run -m pyscripts fleet stamp` + `make restart-service`.
- The ladder force is deliberate and scoped: the generated `rankless_rs/Makefile`
  only tracks `steps/*.rs`, so make cannot see that the data changed under the
  ladder — and after `filter` it always has. Only the ladder subgraph is forced
  (this replaces the old blanket `make -B post-csvs` habit). `build-data` /
  `complete` remain as internal targets for from-scratch builders (bootstrap,
  branch comparison, mega_test).

## commit-artifacts

Commits exactly the pipeline outputs — `rankless_rs/src/gen/`, `src/lib/assets/data/`
— and pushes. Aborts if anything is already staged (the artifact commit must stay
pure), or if the branch is behind origin. Message: `data artifacts: <run_id>` (the
ledger snapshot run_id when present, else the date). Deploy boxes clone from origin,
so this must precede `ship-alpha`; hand-written changes stay yours to commit.

## warm-caches

Drives the worker fleet declared in `data/warm.toml` (`pyscripts/fleet/`). The
config is machine-local and gitignored — it names this box's ssh peers, paths and
memory-fit bands, so it lives with the other per-machine state under `data/`:

```toml
[fleet]
min_citations = 100000 # warm worklist floor, uniform across workers

[model]                # resource model for preflight + suggest (fleet-wide)
mem_base_gb = 37.0     # backend startup baseline (full env)
gb_per_mcut = 0.25     # peak compute GB per M cut_basis per in-flight tree
headroom_gb = 8.0      # OS + page cache + safety margin
parts_gb_per_big = 20.0 # /tmp/dmove-parts footprint per prepped big

[[worker]]
name = "local"
band = [0.0, 14.0]     # (lo, hi] in millions of cut_basis (pd.cut right-inclusive)
bins = [6.0]           # interior breaks; one fewer than procs
procs = [16, 8]        # client parallelism per size bin

[[worker]]
name = "bolero"
host = "bolero"        # ssh alias; omit for the local worker
repo_dir = "/home/borza/rankless"
data_root = "/home/borza/rankless-data"
band = [14.0, 160.0]
bins = [48.0]
procs = [4, 1]
speed = 0.6            # relative throughput; weighs `fleet suggest` splits

[[worker]]
name = "sscub"
host = "sscub-borza"
repo_dir = "/home/borza/rankless"
data_root = "/home/borza/rankless-data"
band = [160.0, 320.0]
procs = [1]
bigs = true            # owns the top band + everything above it
big_chunk = 4          # trees of /tmp/dmove-parts at a time
```

Design rules: **the cache directory is the state** (a worker's backend serves
already-cached responses instantly, the bigs runner skips cached trees, so a
crashed run resumes by rerunning the stage), and **nothing is trusted before the
preflight gate passes**.

`load_config` statically rejects bands that don't tile `(0, top]` (gap = coverage
failure hours later, overlap = double compute) and fleets without exactly one
`bigs` worker owning the top band. The stage then runs in phases:

1. **prepare** (parallel per worker): pre-checks — clean checkout (the driver
   too: a dirty driver runs code no commit describes while still reporting a
   matching baked commit, so warm-caches mechanically requires
   commit-artifacts first), `.env` agreement (`OA_ROOT`, `RANKLESS_ENV`), disk
   headroom for the push and (bigs)
   `/tmp/dmove-parts`, RAM ≥ the `[model]` peak estimate for the band — then
   rsync data (`--delete` mirror of the pushed subdirs; per-box dirs excluded)
   - seed the union cache, `git pull --ff-only`, a frozen dep sync
     (`--no-install-package` for the science-data editable + psycopg2 — workers
     outside the `/mnt/data` sync network can't resolve/build them and don't
     need them; compute then runs `uv run --no-sync`), `make restart-service`
     (binaries are per-box: `target-cpu=native`), wait for `/v1/specs` (fast-fails
     if the unit enters `failed`), then post-checks: stamp equality, full data
     manifest digest equality (torn transfers fail here), and the **version
     handshake** — the worker's `/v1/specs.version`
     (`<git commit>|<RANKLESS_ENV>|<stamp>`) must equal the primary's expectation,
     which proves the _running process_ is the right build on the right data (a
     rebuilt-but-still-old-process backend fails here, not silently). The local
     worker skips pull/push but also rebuilds + restarts — `commit-artifacts`
     moves HEAD after `refresh-data` built the running binary, so without a
     restart its own version handshake would fail on every real release.
2. **gate**: all checks print as one table; any failure aborts before any
   compute. `HEAD == origin` is asserted up front (workers pull from origin).
3. **compute** (parallel): banded `cache bigs` / `cache rest` per worker, cache
   files rsynced back every 10 minutes plus a final pass; the local worker runs
   in-process.
4. **verify**: the disk-only coverage gate — every sampled tree cached on the
   primary root (no requests, so a gap can never trigger an out-of-memory
   compute locally).

Bigs = everything above the top band's `hi`, computed via chunked prep→read:
`big_chunk` trees prepped into `/tmp/dmove-parts`, then read (the server deletes
each tree's parts after its read), then the next chunk. Raise `big_chunk` if the
SSD allows, lower it if it fills — preflight enforces `big_chunk ×
parts_gb_per_big` of `/tmp` headroom.

Flags: `--config <toml>`, `--only <worker>`, `--no-push` (skip the data rsync),
`--gate-only` (just re-check coverage). Single-box primitives stay available as
`make cache-bigs / cache-rest / cache-validate-all / cache-validate-bigs`, banded
via the cache CLI's flags (the same ones the driver ships per worker):
`ARGS="--min 14 --limit 320 --bins 48 --procs 4,1 --chunk 4 --min-citations 100000"`.
`data/warm.toml` is the only place bands are configured — the old `BIG_LIMIT`/
`RL_BINS`/`RL_PROCS` env knobs are gone, and preflight fails any worker whose
`.env` still sets one (exactly those three; other `RL_*` vars belong to the
deploy tooling and stay).

### Fleet helpers (`uv run -m pyscripts fleet <action>`, or `make fleet ARGS=…`)

- `probe` — per-machine facts: RAM, cores, data-root + `/tmp` free space,
  checkout HEAD, backend-unit state, cargo/uv presence. Adding a machine =
  ssh-config alias + checkout + `.env` (`OA_ROOT`, `RANKLESS_ENV`) +
  `make setup-services ARGS="--profile worker --no-start"` (backend unit only;
  the driver starts it after the data push) + cargo/uv; `probe --host <alias>`
  (then with `--repo-dir/--data-root`) checks each step's result.
- `suggest` — drafts a complete `warm.toml`: probes every configured worker,
  pulls the real worklist from the local backend, tiles bands so estimated
  wall-clock is balanced by `speed` and every band fits its box's RAM under
  `[model]`, puts the top band + bigs duty on the highest-ceiling box, derives
  `bins`/`procs` and `big_chunk`. Bandless `[[worker]]` stanzas (just
  name/host/paths) are enough as input; paste + hand-tune the output.
- `preflight` — the full check table against the current fleet, changing
  nothing. Run it any time; `warm-caches` enforces the same gate itself.
- `stamp` — (re)write `$OA_ROOT/stamp`; needed once on first adoption and after
  manual data surgery (`refresh-data` stamps automatically). Restart the
  backend afterwards so `/v1/specs` serves it.

The `[model]` coefficients start uncalibrated (defaults implied by the
historical hand-tuned bands). After a real run, read each box's
`systemctl --user show rankless-backend -p MemoryPeak` and fit `gb_per_mcut` =
(peak − base) / (procs × band hi); preflight and suggest sharpen together.

## ship-alpha

Guards first: no uncommitted artifact files, `HEAD == origin/<branch>`. Then
`new_large_alpha` (EC2 instance, full setup from nothing) which includes the user-DB
handoff — live → local → new box, all user tables, unexpired auth sessions included
(see [mcp-server.md](mcp-server.md) → Moving sessions between boxes) — and an
observability bootstrap: a detached `ops` tmux session (btop + user-unit journal
tail) so later logins just `tmux attach -t ops`. Ends with smoke checks: frontend
root, `/v1/specs`, a slice, one tree response, and the per-FE-worker memory table.

## promote

`promote_alpha_to_live`: pre-flip DB catch-up (everything users did on live while
alpha baked, merged with claims made on alpha during validation), frontend re-built
for the live domain, nginx + EIP flip, cert refresh, then a post-flip final DB merge
from the old live box (it keeps running on a fresh ephemeral IP as a safety net).
Ends with live smoke checks and a reminder: once satisfied, `make kill_dangling`.

## Related

- DB movement mechanics + manual `{merge,sync}_db_*` targets: [mcp-server.md](mcp-server.md)
- Backend/frontend/MCP systemd units + machine profiles: `deploy/` templates,
  `pyscripts/services.py` ([mcp-server.md](mcp-server.md) → Deployment)
- EC2 primitives (`new_large_alpha`, `promote_alpha_to_live`, cert and nginx
  plumbing): `pyscripts/deploy.py`
