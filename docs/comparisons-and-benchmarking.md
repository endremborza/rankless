# Comparisons and Benchmarking

Scripts for running tree queries at scale against one or more server instances, comparing branches for correctness and performance.

---

## Overview

Two comparison modes exist:

| Mode | Script | Purpose |
|------|--------|---------|
| **Branch comparison** | `pyscripts/branch_comparison.py` | Two Docker containers (one per branch), structural tree diff — correctness + timing |
| **SQL comparison** | `pyscripts/sql_comparison_eval.py` | Flask/PostgreSQL vs Rust — structural diff, Pearson correlation, relative error |

Both produce identical artifact sets via the shared `pyscripts/comparison_report.py` module.

---

## Shared Infrastructure

### `pyscripts/comparison_report.py`
Shared analysis and reporting — used by both comparison scripts:
- `CompResult` — dataclass with `time_a`, `time_b`, `diff_df` (always `"a_"`/`"b_"` prefixed columns)
- `setup_logging(log_path)` — attaches DEBUG file handler + INFO console handler to `rankless.comparison` logger
- `build_summary_df(results)` — per-query metrics: Pearson, rel-error, missing nodes
- `build_grouped_df(summary_df)` — aggregated by `root_type × bd_label`, with `time_rate = time_a / time_b`
- `build_totals(results, summary_df)` — scalar summary dict
- `print_report(grouped_df, totals, label_a, label_b)` — console table
- `plot_timing(results, label_a, label_b, out_path)` — log-log scatter with regression by breakdown depth
- `plot_accuracy(grouped_df, label_a, label_b, out_path)` — horizontal bar chart of rel-error by entity type
- `save_markdown(grouped_df, totals, label_a, label_b, out_path, plot_paths)` — committable markdown report
- `save_html(grouped_df, totals, label_a, label_b, out_path, plot_paths)` — styled HTML with color-coded table and external image links

**Label convention:** `diff_df` always uses `"a"` and `"b"` as tree labels (from `make_diff_df`). Display labels (`label_a`, `label_b`) are caller-supplied and appear only in headers, titles, and filenames.

**Color coding in HTML:** green/yellow/red thresholds — Pearson >0.99/>0.95, rel-error <1%/<5%, top-source ID match >90%/>70%, top-source link rel-error <2%/<10%.

### `pyscripts/tree_diff.py`
Structural tree diff primitives:
- `METRICS` — `["linkCount", "sourceCount"]`
- `flatten_tree(children)` — recursive flatten to path-keyed rows
- `make_diff_df(children_a, label_a, children_b, label_b)` — outer-join both trees; always call with `"a"`, `"b"` as labels
- `metric_stats(df, col, label_a, label_b)` — Pearson + rel-error scoped to label_a-present nodes; returns `missing_in_b` count; `None` if mean relerr > 5%
- `top_source_stats(df, label_a, label_b)` — top-source ID match rate and link rel-error

### `pyscripts/cache_prompting.py`
Core query infrastructure:
- `BatchRequester(min_citations, big_limit, addr)` — samples entities, generates URLs
- `get_specs_and_ys(addr)` — fetches breakdown specs from the server

### `pyscripts/server_ops.py`
Server lifecycle:
- `ServerProcess(config)` — local Rust server: `start()`, `wait_ready()`, `stop()`
- `DockerServer(container, image, host_port, data_root)` — Rust server in Docker: `build_image()`, `start()`, `wait_ready()`, `stop()`
- `build_server()` — `cargo build --release`
- `current_branch()` / `checkout(branch)` — git helpers

### `pyscripts/stow_ops.py`
Data directory stashing via rsync:
- `RebuildLevel` enum: `none | binary | pipeline | full`
- `StowManager` — `stash(label)`, `data_root_for(label)`, `has_data(label)`
- Stash = full rsync of `data_root` → `/tmp/rankless-stow/{label}/`

---

## Artifacts

Both comparison scripts write the same set of artifacts to `docs/comparison-artifacts/{timestamp}-{slug}/`:

| File | Purpose | Committable |
|------|---------|-------------|
| `report.md` | Markdown summary with tables and image links | Yes |
| `report.html` | Styled HTML with color-coded table and plots | Yes |
| `timing_plot.png` | Log-log response time scatter by breakdown depth | Yes |
| `accuracy_plot.png` | Rel-error bar chart by entity type | Yes |
| `comparison.log` | Full DEBUG log of every query result and error | No |
| `summary.csv` | Per-query rows | No |
| `grouped.csv` | Aggregated by root_type × breakdown | No |

---

## Branch Comparison

Runs two Docker containers simultaneously (branch A on port 3038, branch B on port 3039), queries both with the same entity set, diffs tree structure node-by-node.

### Usage

```bash
make branch_comparison

# With options:
python -m pyscripts.branch_comparison --branch-a move-from-server --branch-b rankless-main
python -m pyscripts.branch_comparison --rebuild-a pipeline --rebuild-b pipeline
python -m pyscripts.branch_comparison --rebuild-a none --rebuild-b none   # reuse images
python -m pyscripts.branch_comparison --samples 8
python -m pyscripts.branch_comparison --artifacts /tmp/my-cmp
```

### Rebuild Levels

| Level | Binary | Pipeline | Cache | Docker image | Use when |
|-------|--------|----------|-------|--------------|---------|
| `none` | — | — | — | existing | nothing changed since last run |
| `binary` | rebuild | existing data | cleared | rebuilt | server/tree code changed |
| `pipeline` | rebuild | `make filter` | cleared | rebuilt | pipeline code changed |
| `full` | rebuild | `make to-csv` + `make filter` | cleared | rebuilt | input data changed |

### Stow Mechanism

After a `pipeline` or `full` rebuild, the full data root is rsynced to `/tmp/rankless-stow/{branch}/`. On subsequent runs with `--rebuild-* none`, each container mounts its stowed directory. The binary is captured in the Docker image.

### Correctness Signal

`relerr_sc` (sourceCount relative error) is the primary correctness metric — values near 0 mean branches produce equivalent results. `missing_in_b` counts nodes present in A's tree that are absent in B's.

---

## Benchmarking

```bash
make bm
```

`pyscripts/bm.py` — Standalone throughput/latency benchmark:
- Builds and starts a local server, runs 2 × 250 queries across citation-count bins
- Automatically switches to `rankless-main` and repeats for cross-branch timing comparison
- Collects response times, server-side log timings, memory (RSS/VMS via psutil), directory sizes
- Writes compressed CSV reports to `/tmp/dmove-bm/{timestamp}/`

---

## SQL / Reference Comparison

```bash
make start_comparison   # start Docker containers (Rust + Flask/PG)
make sql_comparison_eval
```

`pyscripts/start_comparison.py` — builds and starts:
- `rankless-rust` — current binary on host network port 3038
- `rankless-pg-python` — Flask + PostgreSQL on port 5000

`pyscripts/sql_comparison_eval.py` — structural comparison:
- OA→DM ID translation via `translate_tree` for fair key comparison
- `label_a="flask"`, `label_b="rs"` — time ratio = flask/rs (>1 means flask is slower)
- Produces the same artifact set as branch comparison (see Artifacts table above)

---

## Typical Workflows

### First branch comparison (binary-level)

```bash
python -m pyscripts.branch_comparison --rebuild-a binary --rebuild-b binary
```

### Subsequent run (no rebuild)

```bash
python -m pyscripts.branch_comparison --rebuild-a none --rebuild-b none
```

### After pipeline code change

```bash
python -m pyscripts.branch_comparison --rebuild-a pipeline --rebuild-b pipeline
```
