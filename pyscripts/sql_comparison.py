"""SQL (Flask/PostgreSQL) vs Rust server comparison.

Runs both backends as Docker containers, queries the same entities via both,
and evaluates correctness and timing. The Flask/PG container is kept running
between invocations by default for fast iteration.

Run via the unified CLI:
    uv run -m pyscripts compare-sql [options]

Options:
    --rebuild-rust LEVEL   none | binary | pipeline | full  (default: binary)
    --rebuild-sql          rebuild + restart Flask/PG container (default: skip if running)
    --no-keep-sql          stop Flask/PG container after run (default: keep running)
    --samples N            entities per citation-count bin (default: 4)
    --artifacts PATH       output directory (default: logs/comparison-artifacts)

Artifacts written to logs/comparison-artifacts/{timestamp}-sql-vs-rust/:
summary.csv, grouped.csv, memory_samples.csv (raw memory time-series), the
PNG debug report (report.html), and poster-quality vector figures
(timing/memory/accuracy as .svg + .pdf, via poster_figures).
"""

import argparse
import re
import subprocess
from datetime import datetime
from pathlib import Path

import ccl_science_data
import pandas as pd
import requests
from ccl_science_data.common import load_map, oa_root
from ccl_science_data.gen import EntC

from pyscripts.cache_prompting import RTC, BatchRequester
from pyscripts.comparison_driver import (
    prepare_backend,
    run_query_loop,
    sample_entities,
    write_artifacts,
)
from pyscripts.comparison_report import (
    ARTIFACTS_ROOT,
    MemoryTracker,
    logger,
    setup_logging,
)
from pyscripts.server_ops import DockerServer, FlaskPgServer, port_free
from pyscripts.stow_ops import RebuildLevel

CCL_LIB = Path(ccl_science_data.__file__).parent.parent

RUST_IMAGE = RUST_CONTAINER = "rankless-rust-sql"
RUST_PORT = 3038
FLASK_IMAGE = FLASK_CONTAINER = "rankless-pg-python"
FLASK_PORT = 5000

MEMORY_LIMIT = "8g"
CPU_LIMIT = "4"

SAMPLE_BINS = [5_000, 10_000, 30_000, 100_000, 200_000]
SUPPORTED_ETYPES = {
    EntC.AUTHORS,
    EntC.INSTITUTIONS,
    EntC.COUNTRIES,
    EntC.SOURCES,
    EntC.SUBFIELDS,
    EntC.TOPICS,
    EntC.WORKS,
}


# ── OA → DM ID translation ────────────────────────────────────────────────────


def _id_to_cc(val: int) -> str:
    chars = []
    while val > 0:
        chars.append(chr(val & 0xFF))
        val >>= 8
    return "".join(chars)


def _build_oa_to_dm_maps() -> dict[str, dict[str, str]]:
    maps: dict[str, dict[str, str]] = {}
    for ent in SUPPORTED_ETYPES:
        if ent == EntC.COUNTRIES:
            raw = load_map(ent)
            maps[ent] = {
                _id_to_cc(int(k)): str(v) for k, v in raw.items() if _id_to_cc(int(k))
            }
        else:
            maps[ent] = {str(k): str(v) for k, v in load_map(ent).items()}
    return maps


def _translate_tree(
    children: dict, breakdowns: list[dict], maps: dict, depth: int = 0
) -> dict:
    if depth >= len(breakdowns):
        return children
    etype = breakdowns[depth]["attributeType"]
    oa_to_dm = maps.get(etype, {})
    translated = {}
    for k, v in children.items():
        dm_key = oa_to_dm.get(str(k), str(k))
        new_v = dict(v)
        if "children" in new_v:
            new_v["children"] = _translate_tree(
                new_v["children"], breakdowns, maps, depth + 1
            )
        translated[dm_key] = new_v
    return translated


# ── sampling + per-query fetch ──────────────────────────────────────────────────


def _build_sample_df(urled_sample: pd.DataFrame, e_per_bin: int) -> pd.DataFrame:
    """Attach OpenAlex ids (Flask queries by OA id) then stratified-sample."""
    with_oa = pd.concat(
        pd.DataFrame(
            [{"dmId": v, "oa_id": k2} for k2, v in load_map(k).items()]
        ).assign(**{RTC: k})
        for k in urled_sample[RTC].unique()
    ).merge(urled_sample)
    return sample_entities(with_oa, SAMPLE_BINS, e_per_bin).drop_duplicates(
        [RTC, "oa_id"]
    )


def _make_fetch_pair(flask_url: str, oa_dm_maps: dict):
    impact_url = f"{flask_url}/impact-tree"

    def fetch_pair(row, tid, bds):
        flask_bds = [
            {"node": b["attributeType"], "sourceSide": b["sourceSide"]} for b in bds
        ]
        root_id = (
            _id_to_cc(int(row["oa_id"])) if row[RTC] == EntC.COUNTRIES else row["oa_id"]
        )
        payload = {"root_type": row[RTC], "root_id": root_id, "breakdowns": flask_bds}
        url = re.sub(r"tid=\d", f"tid={tid}", row["url"])
        flask_resp = requests.post(impact_url, json=payload)
        flask_resp.raise_for_status()
        rs_resp = requests.get(url)
        rs_resp.raise_for_status()
        flask_children = _translate_tree(flask_resp.json()["children"], bds, oa_dm_maps)
        rs_children = rs_resp.json()["tree"]["children"]
        return (
            flask_children,
            rs_children,
            flask_resp.elapsed.total_seconds(),
            rs_resp.elapsed.total_seconds(),
        )

    return fetch_pair


def _preflight(rust: DockerServer) -> None:
    """Fail fast on environment problems before the expensive build + benchmark."""
    if subprocess.run(["docker", "version"], capture_output=True).returncode != 0:
        raise RuntimeError("docker is unavailable — is the daemon running?")
    rust.stop()  # drop any stale comparison container so its host port frees up
    if not port_free(rust.host_port):
        raise RuntimeError(
            f"host port {rust.host_port} is already in use — the Rust comparison "
            f"container cannot bind it. If your local rankless backend is running on "
            f"{rust.host_port}, stop it first (e.g. `systemctl --user stop "
            f"rankless-backend`), then retry."
        )
    logger.info("preflight OK — docker available, port %d free", rust.host_port)


# ── entry point ───────────────────────────────────────────────────────────────


def run_comparison(
    rebuild_rust: RebuildLevel,
    rebuild_sql: bool,
    keep_sql: bool,
    e_per_bin: int,
    artifacts_dir: Path,
) -> None:
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(artifacts_dir / "comparison.log")
    logger.info(f"SQL (Flask/PG) vs Rust comparison from {oa_root}")

    flask = FlaskPgServer(
        container=FLASK_CONTAINER,
        image=FLASK_IMAGE,
        host_port=FLASK_PORT,
        data_root=oa_root,
        ccl_lib=CCL_LIB,
        memory=MEMORY_LIMIT,
        cpus=CPU_LIMIT,
    )
    rust = DockerServer(
        container=RUST_CONTAINER,
        image=RUST_IMAGE,
        host_port=RUST_PORT,
        data_root=oa_root,
        memory=MEMORY_LIMIT,
        cpus=CPU_LIMIT,
    )

    _preflight(rust)
    prepare_backend(rebuild_rust, rust)

    if rebuild_sql or not flask.is_running():
        logger.info("starting Flask/PG container")
        flask.build_image()
        flask.start()
        flask.wait_ready()
    else:
        logger.info("reusing running Flask/PG container at %s", flask.base_url)

    rust.start()
    rust.wait_ready()

    requester = BatchRequester(min_citations=SAMPLE_BINS[0], addr=rust.base_url)
    sample_df = _build_sample_df(requester.urled_sample, e_per_bin)
    fetch_pair = _make_fetch_pair(flask.base_url, _build_oa_to_dm_maps())

    mem_tracker = MemoryTracker({rust.container: "rs", flask.container: "flask"})
    try:
        mem_tracker.start()
        results = list(
            run_query_loop(
                sample_df,
                requester.specs,
                fetch_pair,
                bd_filter=lambda bds: all(
                    b["attributeType"] in SUPPORTED_ETYPES for b in bds
                ),
            )
        )
    finally:
        mem_tracker.stop()
        rust.stop()
        if not keep_sql:
            flask.stop()

    write_artifacts(
        results,
        "flask",
        "rs",
        artifacts_dir,
        mem_tracker=mem_tracker,
        mem_colors={"flask": "#e45756", "rs": "#4c78a8"},
        save_mem_csv=True,
        poster=True,
    )


def add_arguments(parser: argparse.ArgumentParser) -> None:
    rvals = [r.value for r in RebuildLevel]
    parser.add_argument(
        "--rebuild-rust",
        default="binary",
        choices=rvals,
        help="Rebuild level for Rust container (default: binary)",
    )
    parser.add_argument(
        "--rebuild-sql",
        action="store_true",
        help="Rebuild and restart Flask/PG container (default: skip if running)",
    )
    parser.add_argument(
        "--no-keep-sql",
        action="store_true",
        help="Stop Flask/PG container after run (default: keep running)",
    )
    parser.add_argument(
        "--samples", type=int, default=4, help="Entities per citation-count bin"
    )
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=ARTIFACTS_ROOT,
        help=f"Output directory (default: {ARTIFACTS_ROOT})",
    )


def run(args: argparse.Namespace) -> None:
    ts = datetime.now().strftime("%Y-%m-%d-%H-%M")
    run_comparison(
        rebuild_rust=RebuildLevel(args.rebuild_rust),
        rebuild_sql=args.rebuild_sql,
        keep_sql=not args.no_keep_sql,
        e_per_bin=args.samples,
        artifacts_dir=args.artifacts / f"{ts}-sql-vs-rust",
    )
