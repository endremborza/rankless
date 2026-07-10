-include .env
export

.PHONY: bootstrap dev build-nano-artifact py-build mcp-server deep-explore type-audit mcp-manifest mcp-worker setup-services
.PHONY: check format check-rs check-py check-js format-rs format-py format-js

PY_LINT_PATHS := pyscripts sql-yardstick mcp_server

# Read-only verification gate. Run before every change; must be clean.
check: check-rs check-py check-js

# Auto-fix everything that can be fixed mechanically, then run `check`.
format: format-rs format-py format-js

check-rs:
	cargo fmt --check
	cargo check --workspace --all-targets

check-py:
	uv run ruff format --check $(PY_LINT_PATHS)
	uv run ruff check $(PY_LINT_PATHS)

check-js:
	bun run lint
	bun run check

format-rs:
	cargo fmt

format-py:
	uv run ruff check --fix $(PY_LINT_PATHS)
	uv run ruff format $(PY_LINT_PATHS)

format-js:
	bun run format
	bun run lint:fix

bootstrap:
	python3 -m pyscripts.dev.bootstrap

dev:
	uv run -m pyscripts.dev.run

# MCP proxy over the backend (stdio); see docs/mcp-server.md.
mcp-server:
	uv run -m mcp_server

# Agentic deep exploration via the MCP tools; writes to .cril/writeups/.
# e.g. make deep-explore ARGS="--backend live --foci all"
deep-explore:
	uv run -m pyscripts.explore.deep $(ARGS)

# Cross-language type/API-shape coherence audit; see docs/type-audit.md.
# ARGS="--strict" also fails on warnings.
type-audit:
	uv run -m pyscripts.typeaudit $(ARGS)

# Bake the /mcp demo page manifest from the live tool/prompt sources.
mcp-manifest:
	uv run -m pyscripts.build_mcp_manifest $(ARGS)

# Host worker for admin-created exploration sessions (systemd in prod).
mcp-worker:
	uv run -m pyscripts.mcp_worker $(ARGS)

# Render deploy/ unit templates + install systemd --user services for a machine
# profile (dev / small-alpha / live); see docs/mcp-server.md.
# e.g. make setup-services ARGS="--profile dev --mcp-backend alpha"
setup-services:
	uv run -m pyscripts.services $(ARGS)

build-nano-artifact:
	uv run -m pyscripts.dev.build_nano_artifact

py-build:
	@if [ "$$(uname -s)" = "Darwin" ]; then \
		brew install libpq; \
	else \
		sudo apt install libpq-dev; \
	fi
	uv sync

include rankless_rs/Makefile
include Makefile.test

download-snapshot:
	aws s3 sync "s3://openalex" $(OA_SNAPSHOT) --no-sign-request

get-release-notes:
	curl -s https://openalex.s3.amazonaws.com/RELEASE_NOTES.txt | head -50

build-prep:
	cargo build --release -p dmove-macro
	./target/release/dmove-macro -p rankless_rs make-setup
	./target/release/dmove-macro -p rankless_rs make-setup --fast

to-csv: 
	cargo run --release -p rankless-rs -- $@ $(OA_ROOT) $(OA_SNAPSHOT)/data

filter: export_user_ledger clean-filters clean-cache
	cargo build --release -p rankless-rs 
	time ./target/release/rankless-rs $@ $(OA_ROOT)

run-server:
	cargo run --release -p rankless-server -- $(OA_ROOT) 

extend_csvs lib_data_generation homepage_showcase live_monitoring reporting sitemap_validation survey_result_export log_parsing nobel export_user_ledger:
	uv run -m pyscripts.$@

hit-paper-analysis field-citation-ratio author-missed-works:
	uv run notebooks/$@.py

# Benchmark / comparison tooling — unified CLI (`uv run -m pyscripts -h`).
# Pass extra flags via ARGS, e.g. `make compare-sql ARGS="--rebuild-rust pipeline"`.
bench:
	uv run -m pyscripts bench

compare-sql compare-branch:
	uv run -m pyscripts $@ $(ARGS)

cache-prep cache-read cache-rest cache-validate-all cache-validate-bigs:
	uv run -m pyscripts cache $(@:cache-%=%)

pull_live_certs sync_fe_to_alpha sync_fe_to_live sync_fe_to_local sync_data_to_alpha sync_data_to_live setup_local_test bump_v bump_v_minor rolling_restart_live_fe new_small_alpha new_large_alpha kill_dangling kill_alpha:
	echo "from pyscripts.deploy import $@;$@()" | uv run -

# MCP + ledger DB movement: {merge,sync}_db_{to,from}_{live,alpha} (see pyscripts/deploy.py).
merge_db_from_live sync_db_from_live merge_db_to_live sync_db_to_live merge_db_from_alpha sync_db_from_alpha merge_db_to_alpha sync_db_to_alpha:
	echo "from pyscripts.deploy import $@;$@()" | uv run -

post-csvs: filter extend_csvs rankless_rs/src/gen/derive_links5.rs lib_data_generation
	@echo Complete

# Backend-independent data build: everything the server reads, no running server
# required. Used by from-scratch builders (bootstrap, branch comparison).
build-data: to-csv post-csvs
	@echo data built

# One command, in order: build the data, restart the backend on it, then bake the
# homepage showcase (which queries the freshly-restarted backend — homepage_showcase
# waits for the service to finish loading before it queries).
complete: build-data restart-service homepage_showcase
	@echo Complete

restart-service:
	cargo build --release
	systemctl --user restart rankless-backend.service

nuke: clean-cache
	rm -rf $(OA_ROOT)
	rm -f data/rankless.sqlite

#WET: These know names of directories
clean-filters:
	rm -rf $(OA_ROOT)/filter-steps

clean-cache:
	rm -rf $(OA_ROOT)/cache
	rm -rf /tmp/dmove-parts

clean-ledger:
	rm -rf $(OA_ROOT)/user-ledger
