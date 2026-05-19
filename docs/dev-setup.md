# Local dev environment

For designers and collaborators who just want a running rankless on their
machine — no pipeline, no OpenAlex snapshot, no metaprogramming detours.

## Prerequisites

- macOS or Linux
- Git
- (macOS) Xcode Command-Line Tools: `xcode-select --install`
- (macOS) Homebrew: <https://brew.sh>

Everything else (Rust, uv, Bun, zstd) is checked and reported by
`make bootstrap`; install the missing pieces and re-run.

## One-time setup

```sh
git clone git@github.com:endremborza/rankless.git
cd rankless
make bootstrap
```

This:
1. Clones `ccl-science-data` into `~/.cache/rankless/` and regenerates its
   reader bindings against this checkout.
2. `uv sync` + `bun install`.
3. Downloads the nano OpenAlex *snapshot* (filtered raw JSON, ~100 MB) into
   `./data/nano-snapshot/`.
4. Runs the rankless pipeline (`RANKLESS_ENV=nano`) on it to produce
   `./data/nano-root/` — this is the slow part, ~10 min the first time
   because cargo builds the pipeline binaries from scratch.
5. Builds `rankless-server` (also `RANKLESS_ENV=nano` so its compile-time
   constants match the data).

Bootstrap is idempotent — re-running skips finished steps (stamp files at
`./data/nano-snapshot/.ready` and `./data/nano-root/.pipeline-done`).

## Daily flow

```sh
make dev
```

This brings up the backend (`127.0.0.1:3038`) and the SvelteKit dev server
(`127.0.0.1:5173`) in one foreground process. Logs are interleaved with
`[be]` and `[fe]` prefixes. `Ctrl-C` shuts both down cleanly.

Pass `--open` to launch your browser automatically:

```sh
uv run -m pyscripts.dev.run --open
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `port 3038/5173 already in use` | another instance is running — `lsof -nP -iTCP:3038 -sTCP:LISTEN` to find it |
| `backend never became ready` | inspect `make dev` output; usually OA_ROOT is incomplete — re-run `make bootstrap` |
| `NANO_ARTIFACT_URL` 404 | the http server that hosts the artifact isn't reachable; ask whoever owns it for a fresh URL |
| ccl-science-data import error | `rm -rf libs/ccl-science-data && make bootstrap` |

## Where things live

- `data/nano-snapshot/` — filtered OpenAlex JSON, downloaded by bootstrap (gitignored)
- `data/nano-root/` — pipeline output the backend serves, built locally (gitignored)
- `libs/ccl-science-data` — symlink → `~/.cache/rankless/ccl-science-data` (the
  actual clone lives outside the repo so it never appears as a nested git
  checkout; override the target with `CCL_CLONE_DIR=<path> make bootstrap`)
- `target/release/rankless-server` — the backend binary
- `.env` — your local config (gitignored, seeded from `.env.example`)

## Maintainer: refreshing the snapshot artifact

The artifact is just the filtered raw JSON snapshot — no pipeline output, no
cargo-built binaries. Designers' bootstrap runs the pipeline locally so their
binary and data are end-to-end consistent for whatever commit they're on.

Prereq: `$OA_TEST_ROOT/nano-snapshot/` exists. If not, build it once with
`uv run -m pyscripts.make_test_dataset` (needs a full OpenAlex snapshot).

```sh
uv run -m pyscripts.dev.build_nano_artifact     # tars + zstds the snapshot
python -m http.server 8000                      # serve nano-snapshot.tar.zst
```

The script prints the SHA-256 and the `NANO_ARTIFACT_URL` / `NANO_ARTIFACT_SHA256`
lines to paste into collaborators' `.env` (or the canonical host).

## End-to-end test in Docker

`make test-dev-env` runs the full bootstrap inside a clean Ubuntu container
and then spins the backend up briefly to confirm it serves. It uses
`--network=host`, so the artifact you're serving on the host (`python -m
http.server 8000`) is reachable from inside the container without any extra
wiring. Requires Linux for the host networking; macOS hosts would need to
swap the URL for `host.docker.internal:8000` (not the target audience here).

```sh
make build-nano-artifact                        # one time, after `make complete`
python -m http.server 8000 &                    # serve the artifact
make test-dev-env                               # builds the image, runs bootstrap, verifies
```

Override the URL if your artifact lives elsewhere:

```sh
NANO_ARTIFACT_URL=http://10.0.0.5:9000/nano-root.tar.zst make test-dev-env
```
