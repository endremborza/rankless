"""SQL (Flask/PostgreSQL) vs Rust server comparison.

Runs both backends as Docker containers, queries the same entities via both,
and evaluates correctness and timing. The Flask/PG container is kept running
between invocations by default for fast iteration.

Usage:
    python -m pyscripts.sql_comparison [options]

Options:
    --rebuild-rust LEVEL   none | binary | pipeline | full  (default: binary)
    --rebuild-sql          rebuild + restart Flask/PG container (default: skip if running)
    --no-keep-sql          stop Flask/PG container after run (default: keep running)
    --samples N            entities per citation-count bin (default: 4)
    --artifacts PATH       output directory (default: logs/comparison-artifacts)

Artifacts written to logs/comparison-artifacts/{timestamp}-sql-vs-rust/.
"""

import argparse
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

import ccl_science_data
import pandas as pd
import requests
from ccl_science_data.common import EntC, load_map, oa_root
from tqdm import tqdm

from pyscripts.cache_prompting import RTC, BatchRequester, get_specs_and_ys
from pyscripts.comparison_report import (
    ARTIFACTS_ROOT,
    CompResult,
    MemoryTracker,
    build_grouped_df,
    build_mem_stats,
    build_summary_df,
    build_totals,
    logger,
    open_report,
    plot_accuracy,
    plot_memory,
    plot_timing,
    print_report,
    save_html,
    save_markdown,
    setup_logging,
)
from pyscripts.server_ops import DockerServer, build_server
from pyscripts.stow_ops import RebuildLevel
from pyscripts.tree_diff import make_diff_df

CCL_LIB = Path(ccl_science_data.__file__).parent.parent

RUST_IMAGE = "rankless-rust-sql"
RUST_CONTAINER = "rankless-rust-sql"
RUST_PORT = 3038

FLASK_IMAGE = "rankless-pg-python"
FLASK_CONTAINER = "rankless-pg-python"
FLASK_PORT = 5000
FLASK_DOCKERFILE = "sql-yardstick/docker/Dockerfile.pg-python"

MEMORY_LIMIT = "8g"
CPU_LIMIT = "4"

FINAL_STEP = "rankless_rs/src/gen/derive_links5.rs"

SUPPORTED_ETYPES = {
    EntC.AUTHORS,
    EntC.INSTITUTIONS,
    EntC.COUNTRIES,
    EntC.SOURCES,
    EntC.SUBFIELDS,
    EntC.TOPICS,
    EntC.WORKS,
}


# ── Flask/PG container ────────────────────────────────────────────────────────


@dataclass
class FlaskPgServer:
    data_root: Path
    ccl_lib: Path
    container: str = FLASK_CONTAINER
    image: str = FLASK_IMAGE
    host_port: int = FLASK_PORT
    memory: str = MEMORY_LIMIT
    cpus: str = CPU_LIMIT
    dockerfile: str = FLASK_DOCKERFILE

    @property
    def base_url(self) -> str:
        return f"http://localhost:{self.host_port}"

    def is_running(self) -> bool:
        r = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", self.container],
            capture_output=True,
            text=True,
        )
        return r.returncode == 0 and r.stdout.strip() == "true"

    def build_image(self) -> None:
        _docker(["build", "-f", self.dockerfile, "-t", self.image, "."])

    def stop(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.container], capture_output=True)

    def start(self) -> None:
        self.stop()
        _docker(
            [
                "run",
                "-d",
                "--name",
                self.container,
                "--memory",
                self.memory,
                "--cpus",
                self.cpus,
                "-p",
                f"{self.host_port}:5000",
                "-v",
                f"{self.data_root}:/data/oa-root:ro",
                "-v",
                f"{self.ccl_lib}:/ccl-science-data:ro",
                self.image,
            ]
        )

    def wait_ready(self, max_attempts: int = 500) -> None:
        for _ in tqdm(range(max_attempts), desc=f"waiting for {self.container}"):
            try:
                requests.get(self.base_url, timeout=5)
                return  # any HTTP response = server is up
            except Exception:
                time.sleep(3)
        raise TimeoutError(
            f"Flask server at {self.base_url} not ready after {max_attempts * 3}s"
        )


def _docker(args: list) -> None:
    cmd = ["docker", *[str(a) for a in args]]
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True)


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


# ── comparison ────────────────────────────────────────────────────────────────


class SqlComparator:
    def __init__(self, rust_url: str, flask_url: str) -> None:
        self.rust_url = rust_url
        self.flask_url = f"{flask_url}/impact-tree"
        self.specs, _ = get_specs_and_ys(rust_url)
        self.oa_dm_maps = _build_oa_to_dm_maps()

    def _build_sample_df(self, e_per_bin: int) -> pd.DataFrame:
        bins = [5_000, 10_000, 30_000, 100_000, 200_000]
        sample_df = BatchRequester(
            min_citations=bins[0], addr=self.rust_url
        ).urled_sample
        return (
            pd.concat(
                pd.DataFrame(
                    [{"dmId": v, "oa_id": k2} for k2, v in load_map(k).items()]
                ).assign(**{RTC: k})
                for k in sample_df[RTC].unique()
            )
            .merge(sample_df)
            .assign(ccut=lambda df: pd.cut(df["citations"], bins))
            .loc[lambda df: df["ccut"].notna()]
            .groupby([RTC, "ccut"], observed=True)
            .apply(
                lambda gdf: gdf.sample(min(e_per_bin, len(gdf)), random_state=742),
                include_groups=False,
            )
            .reset_index()
            .drop_duplicates([RTC, "oa_id"])
        )

    def iter_comparisons(self, e_per_bin: int = 4) -> Iterator[CompResult]:
        df = self._build_sample_df(e_per_bin)
        for _, row in tqdm(list(df.iterrows())):
            root_type: str = row[RTC]
            for tid, tree_spec in enumerate(self.specs[root_type]):
                bds = tree_spec["breakdowns"]
                bd_etypes = [b["attributeType"] for b in bds]
                if not all(et in SUPPORTED_ETYPES for et in bd_etypes):
                    continue
                bd_label = ";".join(
                    f"{b['attributeType']}-{'S' if b['sourceSide'] else 'T'}"
                    for b in bds
                )
                flask_bds = [
                    {"node": b["attributeType"], "sourceSide": b["sourceSide"]}
                    for b in bds
                ]
                root_id = (
                    _id_to_cc(int(row["oa_id"]))
                    if root_type == EntC.COUNTRIES
                    else row["oa_id"]
                )
                payload = {
                    "root_type": root_type,
                    "root_id": root_id,
                    "breakdowns": flask_bds,
                }
                ccount: int = row["citations"]
                url = re.sub(r"tid=\d", f"tid={tid}", row["url"])
                logger.debug(
                    "comparing %s/%s tid=%d ccount=%d", root_type, bd_label, tid, ccount
                )
                try:
                    flask_resp = requests.post(self.flask_url, json=payload)
                    flask_resp.raise_for_status()
                    rs_resp = requests.get(url)
                    rs_resp.raise_for_status()
                    flask_json = flask_resp.json()
                    flask_json["children"] = _translate_tree(
                        flask_json["children"], bds, self.oa_dm_maps
                    )
                    rs_json = rs_resp.json()
                    logger.debug(
                        "  flask=%.3fs rs=%.3fs",
                        flask_resp.elapsed.total_seconds(),
                        rs_resp.elapsed.total_seconds(),
                    )
                    yield CompResult(
                        root_type=root_type,
                        bd_label=bd_label,
                        citation_count=ccount,
                        time_a=flask_resp.elapsed.total_seconds(),
                        time_b=rs_resp.elapsed.total_seconds(),
                        diff_df=make_diff_df(
                            flask_json["children"],
                            "a",
                            rs_json["tree"]["children"],
                            "b",
                        ),
                    )
                except Exception as e:
                    logger.warning(
                        "error for %s/%s tid=%d: %s", root_type, bd_label, tid, e
                    )
                    yield CompResult(
                        root_type,
                        bd_label,
                        ccount,
                        0.0,
                        0.0,
                        pd.DataFrame(),
                        error=str(e),
                    )


# ── preparation ───────────────────────────────────────────────────────────────


def _prepare_rust(level: RebuildLevel, server: DockerServer) -> None:
    if level == RebuildLevel.none:
        return
    match level:
        case RebuildLevel.binary:
            subprocess.run(["make", "clean-cache"], check=True)
            build_server()
        case RebuildLevel.pipeline:
            subprocess.run(["make", "-B", FINAL_STEP], check=True)
            build_server()
        case RebuildLevel.full:
            subprocess.run(["make", "complete"], check=True)
            build_server()
    server.build_image()


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

    flask = FlaskPgServer(data_root=oa_root, ccl_lib=CCL_LIB)
    rust = DockerServer(
        container=RUST_CONTAINER,
        image=RUST_IMAGE,
        host_port=RUST_PORT,
        data_root=oa_root,
        memory=MEMORY_LIMIT,
        cpus=CPU_LIMIT,
    )

    _prepare_rust(rebuild_rust, rust)

    if rebuild_sql or not flask.is_running():
        logger.info("starting Flask/PG container")
        flask.build_image()
        flask.start()
        flask.wait_ready()
    else:
        logger.info("reusing running Flask/PG container at %s", flask.base_url)

    rust.start()
    rust.wait_ready()

    mem_tracker = MemoryTracker({rust.container: "rs", flask.container: "flask"})
    try:
        comparator = SqlComparator(rust_url=rust.base_url, flask_url=flask.base_url)
        mem_tracker.start()
        results = list(comparator.iter_comparisons(e_per_bin))
    finally:
        mem_tracker.stop()
        rust.stop()
        if not keep_sql:
            flask.stop()

    mem_stats = build_mem_stats(mem_tracker.samples)
    summary_df = build_summary_df(results)
    grouped_df = build_grouped_df(summary_df)
    totals = build_totals(results, summary_df)

    summary_df.to_csv(artifacts_dir / "summary.csv", index=False)
    grouped_df.to_csv(artifacts_dir / "grouped.csv", index=False)

    timing_plot = artifacts_dir / "timing_plot.png"
    accuracy_plot = artifacts_dir / "accuracy_plot.png"
    memory_plot = artifacts_dir / "memory_plot.png"
    plot_timing(results, "flask", "rs", timing_plot)
    plot_accuracy(grouped_df, "flask", "rs", accuracy_plot)
    plot_memory(mem_tracker.samples, memory_plot)
    plot_paths = [p for p in [timing_plot, accuracy_plot, memory_plot] if p.exists()]

    print_report(grouped_df, totals, "flask", "rs")
    save_markdown(
        grouped_df,
        totals,
        "flask",
        "rs",
        artifacts_dir / "report.md",
        plot_paths,
        mem_stats=mem_stats,
    )
    html_path = artifacts_dir / "report.html"
    save_html(
        grouped_df,
        totals,
        "flask",
        "rs",
        html_path,
        plot_paths,
        mem_stats=mem_stats,
    )
    open_report(html_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare Flask/PG vs Rust server")
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
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y-%m-%d-%H-%M")
    run_comparison(
        rebuild_rust=RebuildLevel(args.rebuild_rust),
        rebuild_sql=args.rebuild_sql,
        keep_sql=not args.no_keep_sql,
        e_per_bin=args.samples,
        artifacts_dir=args.artifacts / f"{ts}-sql-vs-rust",
    )
