-include .env
export

.PHONY: bootstrap dev build-nano-artifact test-dev-env py-build
.PHONY: check format check-rs check-py check-js format-rs format-py format-js

PY_LINT_PATHS := pyscripts sql-yardstick

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

build-nano-artifact:
	uv run -m pyscripts.dev.build_nano_artifact

# End-to-end test of the bootstrap flow inside a clean Ubuntu container.
# Requires `nano-snapshot.tar.zst` reachable from the container — by default
# the entrypoint hits http://127.0.0.1:8000/nano-snapshot.tar.zst via
# --network=host, so run `python -m http.server 8000` in the dir holding the
# artifact first.
test-dev-env:
	docker build -t rankless-dev-test -f docker/Dockerfile.dev-test docker/
	docker run --rm --network=host \
		-v "$(CURDIR)":/host:ro \
		-e NANO_ARTIFACT_URL="$(or $(NANO_ARTIFACT_URL),http://127.0.0.1:8000/nano-snapshot.tar.zst)" \
		-e NANO_ARTIFACT_SHA256="$(NANO_ARTIFACT_SHA256)" \
		rankless-dev-test

py-build:
	@if [ "$$(uname -s)" = "Darwin" ]; then \
		brew install libpq; \
	else \
		sudo apt install libpq-dev; \
	fi
	uv sync

include rankless_rs/Makefile

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

test-rs:
	export CARGO_INCREMENTAL=0
	export RUSTFLAGS="-Cinstrument-coverage"
	export RUSTDOCFLAGS="-Cinstrument-coverage"
	cargo clean
	cargo test

	grcov . \
	  --binary-path ./target/debug/ \
	  -s . \
	  -t html \
	  --branch \
	  --ignore-not-existing \
	  --ignore "/*" \
	  -o ./target/coverage/html

	rm default_*.profraw
	rm ./*/default_*.profraw

test-js:
	bun run test
	cat logs/paragraph_texts.txt | xxclip

test: test-rs test-js
	echo OK

extend_csvs lib_data_generation bm live_monitoring reporting sitemap_validation survey_result_export log_parsing nobel sql_comparison export_user_ledger mega_test:
	uv run -m pyscripts.$@

hit-paper-analysis field-citation-ratio author-missed-works:
	uv run notebooks/$@.py

cache_big_prep cache_big_read cache_do_rest cache_validate_all cache_validate_bigs:
	uv run -m pyscripts.cache_prompting $@

pull_live_certs sync_fe_to_alpha sync_fe_to_live sync_fe_to_local setup_local_test bump_v bump_v_minor rolling_restart_live_fe new_small_alpha new_large_alpha:
	echo "from pyscripts.deploy import $@;$@()" | uv run -

post-csvs: filter extend_csvs rankless_rs/src/gen/derive_links5.rs lib_data_generation
	@echo Complete

complete: to-csv post-csvs
	@echo Complete

big-test:
	cargo test --release -p rankless-trees --tests instances::tests::big_tree -- --nocapture

profile:
	cargo build --release
	echo "-1"  | sudo tee /proc/sys/kernel/perf_event_paranoid
	echo "0" | sudo tee /proc/sys/kernel/kptr_restrict
	# flamegraph -o make_fg.svg -- target/release/dmove fix-atts $(OA_ROOT)
	# flamegraph -o make_fg.svg -- target/release/rankless-server $(OA_ROOT)
	# flamegraph -o make_fg.svg -- cargo test --release -p rankless-trees --tests instances::tests::big_tree  -- --nocapture
	flamegraph -o make_fg.svg -- target/release/rankless-trees
	echo "4"  | sudo tee /proc/sys/kernel/perf_event_paranoid
	echo "1" | sudo tee /proc/sys/kernel/kptr_restrict
	# install linux-tools-generic

heaptrack:
	# cargo build --release
	# heaptrack target/release/rankless-server $(OA_ROOT) 
	sudo sysctl kernel.yama.ptrace_scope=0 # 1 is default
	heaptrack -p $(pidof rankless-server)

restart-service:
	cargo build --release
	systemctl --user restart rankless-backend.service

nuke: clean-cache
	rm -rf $(OA_ROOT)
	rm data/rankless.sqlite

#WET: These know names of directories
clean-filters:
	rm -rf $(OA_ROOT)/filter-steps

clean-cache:
	rm -rf $(OA_ROOT)/cache
	rm -rf /tmp/dmove-parts

clean-ledger:
	rm -rf $(OA_ROOT)/user-ledger

clean-profile:
	rm perf.data*
	rm make_fg.svg
	rm default_*.profraw
	rm ./*/default_*.profraw
