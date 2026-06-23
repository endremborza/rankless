"""Perf comparison of two git refs of the Rankless server.

Benchmarks cold tree-build cost (the server's ``tlog`` phase timers) and peak
memory of two refs (tags / branches / commit-ish) on the SAME dataset, in
isolated git worktrees — the working tree you are sitting in is never touched.

    uv run -m pyscripts compare-branch --config pyscripts/perf_comparisons.toml
    uv run -m pyscripts compare-branch --only heap-to-sort
    make compare-branch ARGS="--only heap-to-sort"

Each comparison: each ref is checked out detached into /tmp/rankless-perf, built,
imaged (cached by sha), then run sequentially (one container at a time, so timing
is contention-free) against the same sampled query set. Queries use
``cacheable=false`` + no ``year`` over a read-only data mount, so every request is
a full cold recompute. See docs/perf-benchmark-framework.md.
"""

import argparse
import dataclasses
import datetime as dt
import re
import statistics
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote_plus

import requests
from ccl_science_data.common import oa_root
from tqdm import tqdm

from pyscripts import perf_report
from pyscripts.cache_prompting import BatchRequester
from pyscripts.comparison_driver import sample_entities
from pyscripts.comparison_report import ARTIFACTS_ROOT, logger, setup_logging
from pyscripts.perf_report import QueryPerf, RefPerf
from pyscripts.server_ops import (
    DockerServer,
    build_perf_image,
    cgroup_mem_bytes,
    ensure_worktree,
    remove_worktree,
)

DEFAULT_CONFIG = Path("pyscripts/perf_comparisons.toml")
PORT = 3038
MIB = 1024 * 1024

PHASE_LINE = re.compile(
    r"\): (got heaps|got roots|converted, ingested and wrote trees) in (\d+)ms"
)
PHASE_MAP = {
    "got heaps": "heaps",
    "got roots": "roots",
    "converted, ingested and wrote trees": "serialize",
}


@dataclass
class Settings:
    repeats: int = 3  # timed cold recomputes per query (median + min reported)
    warmups: int = 1  # untimed runs to warm the OS page cache for the mmaps
    samples: int = 3  # entities per citation bin
    min_citations: int = 100_000
    bins: list[int] = field(
        default_factory=lambda: [100_000, 1_000_000, 5_000_000, 20_000_000]
    )
    cpus: str = "4"
    mem_limit: str = "32g"  # generous so peak reflects real usage, not a cap
    keep_worktrees: bool = True


@dataclass
class Comparison:
    name: str
    a: str  # candidate ref
    b: str  # baseline ref
    settings: Settings


class LogTailer:
    """Incrementally read a container's stdout (the ``tlog`` phase lines)."""

    def __init__(self, container: str) -> None:
        self.container = container
        self.offset = 0

    def new_lines(self) -> list[str]:
        r = subprocess.run(
            ["docker", "logs", self.container], capture_output=True, text=True
        )
        lines = r.stdout.splitlines()
        new = lines[self.offset :]
        self.offset = len(lines)
        return new


def _settings(defaults: dict, override: dict) -> Settings:
    valid = {f.name for f in dataclasses.fields(Settings)}
    merged = {**defaults, **override}
    unknown = set(merged) - valid
    if unknown:
        raise SystemExit(f"unknown config keys: {sorted(unknown)}")
    return Settings(**merged)


def load_config(path: Path, only: str | None) -> list[Comparison]:
    data = tomllib.loads(path.read_text())
    defaults = data.get("defaults", {})
    comps = [
        Comparison(
            name=c["name"],
            a=c["a"],
            b=c["b"],
            settings=_settings(
                defaults, {k: v for k, v in c.items() if k not in ("name", "a", "b")}
            ),
        )
        for c in data.get("comparison", [])
    ]
    if only:
        comps = [c for c in comps if c.name == only]
        if not comps:
            raise SystemExit(f"no comparison named {only!r} in {path}")
    return comps


def _bd_label(specs: dict, rt: str, tid: int) -> str:
    try:
        bds = specs[rt][tid]["breakdowns"]
    except (KeyError, IndexError):
        return f"tid{tid}"
    return ";".join(
        f"{b['attributeType']}-{'S' if b['sourceSide'] else 'T'}" for b in bds
    )


def _parse_phases(lines: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for ln in lines:
        m = PHASE_LINE.search(ln)
        if m:
            out[PHASE_MAP[m.group(1)]] = float(m.group(2))
    return out


def _make_server(sha: str, image: str, s: Settings) -> DockerServer:
    return DockerServer(
        container=f"rankless-perf-{sha[:12]}",
        image=image,
        host_port=PORT,
        data_root=oa_root,
        memory=s.mem_limit,
        cpus=s.cpus,
    )


def _measure_query(
    server: DockerServer, tailer: LogTailer, row, bd_label: str, s: Settings
) -> QueryPerf | None:
    sem = row["semanticId"]
    url = (
        f"{server.base_url}/v1/trees/{row['rt']}/{quote_plus(sem)}"
        f"?tid={int(row['tid'])}&cacheable=false"
    )
    for _ in range(s.warmups):
        try:
            requests.get(url, timeout=600).raise_for_status()
        except Exception as e:
            logger.warning("warmup failed %s: %s", url, e)
            return None
    tailer.new_lines()  # discard warmup phase lines

    peak_before = cgroup_mem_bytes(server.container, "peak") or 0
    per_phase: dict[str, list[float]] = {}
    https: list[float] = []
    children: dict = {}
    for i in range(s.repeats):
        try:
            resp = requests.get(url, timeout=600)
            resp.raise_for_status()
        except Exception as e:
            logger.warning("query failed %s: %s", url, e)
            return None
        https.append(resp.elapsed.total_seconds())
        for k, v in _parse_phases(tailer.new_lines()).items():
            per_phase.setdefault(k, []).append(v)
        if i == 0:
            children = resp.json().get("tree", {}).get("children", {})
    peak_after = cgroup_mem_bytes(server.container, "peak") or peak_before

    if not per_phase:
        logger.warning("no phase timers parsed for %s — skipping", url)
        return None
    return QueryPerf(
        rt=row["rt"],
        sem=sem,
        tid=int(row["tid"]),
        bd_label=bd_label,
        citations=int(row["citations"]),
        http_s=statistics.median(https),
        phases_ms={k: statistics.median(v) for k, v in per_phase.items()},
        phases_min_ms={k: min(v) for k, v in per_phase.items()},
        mem_delta_mib=(peak_after - peak_before) / MIB,
        children=children,
    )


def _measure_ref(
    server: DockerServer, label: str, sha: str, sample_df, specs: dict, s: Settings
) -> RefPerf:
    tailer = LogTailer(server.container)
    baseline = (cgroup_mem_bytes(server.container, "current") or 0) / MIB
    queries: list[QueryPerf] = []
    try:
        for _, row in tqdm(list(sample_df.iterrows()), desc=label):
            q = _measure_query(
                server, tailer, row, _bd_label(specs, row["rt"], int(row["tid"])), s
            )
            if q:
                queries.append(q)
        peak = (cgroup_mem_bytes(server.container, "peak") or 0) / MIB
    finally:
        server.stop()
    return RefPerf(
        label=label, sha=sha, baseline_mib=baseline, peak_mib=peak, queries=queries
    )


def _label(ref: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._~-]", "-", ref)


def run_comparison(comp: Comparison, artifacts_root: Path) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d-%H-%M")
    artifacts_dir = artifacts_root / f"{ts}-perf-{comp.name}"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(artifacts_dir / "comparison.log")
    s = comp.settings
    logger.info("perf %s: A=%s vs B=%s", comp.name, comp.a, comp.b)

    sha_a, wt_a = ensure_worktree(comp.a)
    sha_b, wt_b = ensure_worktree(comp.b)
    img_a = build_perf_image(sha_a, wt_a)
    img_b = build_perf_image(sha_b, wt_b)

    server_a = _make_server(sha_a, img_a, s)
    server_a.start()
    server_a.wait_ready()
    requester = BatchRequester(min_citations=s.min_citations, addr=server_a.base_url)
    sample_df = sample_entities(requester.urled_sample, s.bins, s.samples).sort_values(
        "citations"
    )
    logger.info("sampled %d (entity, tid) queries", len(sample_df))
    run_a = _measure_ref(server_a, _label(comp.a), sha_a, sample_df, requester.specs, s)

    server_b = _make_server(sha_b, img_b, s)
    server_b.start()
    server_b.wait_ready()
    run_b = _measure_ref(server_b, _label(comp.b), sha_b, sample_df, requester.specs, s)

    perf_report.write_report(run_a, run_b, artifacts_dir)

    if not s.keep_worktrees:
        remove_worktree(wt_a)
        remove_worktree(wt_b)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG, help="TOML comparison config"
    )
    parser.add_argument(
        "--only", default=None, help="run only the comparison with this name"
    )
    parser.add_argument(
        "--artifacts", type=Path, default=ARTIFACTS_ROOT, help="output directory root"
    )


def run(args: argparse.Namespace) -> None:
    for comp in load_config(args.config, args.only):
        run_comparison(comp, args.artifacts)
