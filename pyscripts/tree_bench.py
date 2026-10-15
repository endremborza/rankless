"""Cold tree-build bench: the warm's worklist built one tree at a time by one server binary on
one data root, each tree's wall time and peak resident memory recorded.

    uv run -m pyscripts tree-bench run --binary target/release/rankless-server --root "$OA_ROOT" --label mine [--trees-only]
    uv run -m pyscripts tree-bench compare base mine

`run` empties the root's tree cache, starts the binary on the backend port (stopping the
backend service for the run when it holds the port, and starting it again after) and requests
every tree the warm builds, smallest first. Each request computes and writes every period,
which is the warm's work; each request's wall time and the server's CPU time over it are
recorded, the CPU time holding up better when other jobs share the machine. A tree's peak is the server's VmHWM over its request, reset just
before through `/proc/<pid>/clear_refs`; the server runs with mimalloc's purge delay at zero so
freed pages leave the resident set at once and each peak is the tree's own. A run lands in
`logs/tree-bench/<label>/`: `record.json` and the served trees, entity keys replaced by names so
the trees of two pipeline runs compare (dm ids follow file order; two entities of one name under
one parent collapse into one node). A trees-only run also records the resident memory of a
full startup, and a build that walks years logs its records and runs per tree, which the
record picks up.

`compare` joins two runs on (root type, semantic id, tid): resident memory at startup, wall
time and peak per tree size, and the structural diff of the served trees (`tree_diff`).
"""

import gzip
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from protocli import Dispatcher
from tqdm import tqdm

from wire.rankless_server.consts import PORT, TREES_ONLY_FLAG
from wire.rankless_server.responses import TREE_SPECS

from .cache_prompting import DMIC, RTC, SIDC, TIDC, BatchRequester
from .deploy import be_service_name
from .fleet.config import DEFAULT_MIN_CITATIONS
from .server_ops import DEFAULT_BE_ADDR, ServerConfig, ServerProcess, port_free
from .tree_diff import make_diff_df, metric_stats, top_source_stats

BENCH_ROOT = Path("logs/tree-bench")
RECORD = "record.json"
TREES = "trees.jsonl.gz"
# mimalloc's delay before it returns freed pages to the OS.
PURGE_DELAY_VAR = "MIMALLOC_PURGE_DELAY"
KEY = [RTC, SIDC, TIDC]
SIZE_BINS_M = [0, 1, 3, 10, np.inf]
GB_KB = 2**20
CLOCK_TICKS = os.sysconf("SC_CLK_TCK")
# The line a year-walking build logs per tree (`part_iterator.rs`).
RUNS_LINE = re.compile(
    r"^([\w-]+)\((\d+):(\d+)/p\d+ .*\): (\d+) records in (\d+) runs, the largest (\d+)$"
)
RUN_COLS = ["records", "runs", "largest_run"]


def run(
    *,
    binary: str,
    root: str,
    label: str,
    trees_only: bool = False,
    min_citations: int = DEFAULT_MIN_CITATIONS,
    limit: int = 0,
) -> Path:
    """Build every warm tree of --root cold with --binary, one at a time.

    The run lands in logs/tree-bench/<label>/; --limit keeps the smallest N trees, 0 all."""
    out = BENCH_ROOT / label
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    shutil.rmtree(Path(root) / "cache", ignore_errors=True)
    config = ServerConfig(
        data_root=Path(root), binary=Path(binary), env={PURGE_DELAY_VAR: "0"}
    )
    record: dict = {"binary": binary, "root": root, "trees_only": trees_only}
    record["load_before"] = os.getloadavg()
    with _PortFreed():
        if trees_only:
            with ServerProcess(config) as full:
                record["full_startup"] = _start(full, out / "full-server.log")
            config.flags = (TREES_ONLY_FLAG,)
        with ServerProcess(config) as server:
            record["startup"] = _start(server, out / "server.log")
            rows = _build_all(server, min_citations, limit, out / TREES)
    trees = pd.DataFrame(rows).merge(
        _runs(out / "server.log"), on=[RTC, DMIC, TIDC], how="left"
    )
    record["trees"] = json.loads(trees.drop(columns=DMIC).to_json(orient="records"))
    record["load_after"] = os.getloadavg()
    (out / RECORD).write_text(json.dumps(record))
    print(f"{len(rows)} trees in {trees.wall_s.sum():.0f} s -> {out}")
    return out


def compare(base: str, cand: str) -> None:
    """Print the candidate run against the base run, both labels under logs/tree-bench/."""
    a, b = (_Run(BENCH_ROOT / label) for label in (base, cand))
    for r, name in [(a, base), (b, cand)]:
        full = f", full startup {r.full_rss_gb:.2f} GB" if r.full_rss_gb else ""
        print(f"{name}: resident at startup {r.rss_gb:.2f} GB{full}")
    joined = a.trees.merge(b.trees, on=KEY, suffixes=("_a", "_b"))
    print(
        f"trees: {len(a.trees)} base, {len(b.trees)} candidate, {len(joined)} in both"
    )
    mcut = joined.cut_basis_a / 1e6
    joined = joined.assign(
        mcut=mcut,
        wall=joined.wall_s_b / joined.wall_s_a,
        cpu=joined.cpu_s_b / joined.cpu_s_a.replace(0, np.nan),
        peak=joined.peak_kb_b / joined.peak_kb_a.replace(0, np.nan),
        size=pd.cut(mcut, SIZE_BINS_M),
    )
    by_size = joined.groupby("size", observed=True).agg(
        trees=("wall", "size"),
        base_s=("wall_s_a", "sum"),
        cand_s=("wall_s_b", "sum"),
        wall_ratio_median=("wall", "median"),
        base_cpu_s=("cpu_s_a", "sum"),
        cand_cpu_s=("cpu_s_b", "sum"),
        cpu_ratio_median=("cpu", "median"),
        base_peak_gb=("peak_kb_a", lambda kb: kb.max() / GB_KB),
        cand_peak_gb=("peak_kb_b", lambda kb: kb.max() / GB_KB),
        peak_ratio_median=("peak", "median"),
    )
    print(f"\nby M cut_basis:\n{by_size.round(3).to_string()}")
    big = joined.loc[joined.mcut >= 1]
    for col, unit, scale in [
        ("wall_s", "s", 1),
        ("cpu_s", "cpu s", 1),
        ("peak_kb", "GB", GB_KB),
    ]:
        a_per, b_per = ((big[f"{col}_{s}"] / scale / big.mcut).median() for s in "ab")
        print(
            f"{unit} per M cut_basis (trees >= 1M, median): {a_per:.4f} -> {b_per:.4f}"
        )
    print(f"\nstructure per tree:\n{_structure(a.path, b.path, joined).to_string()}")


class _Run:
    def __init__(self, path: Path) -> None:
        self.path = path
        record = json.loads((path / RECORD).read_text())
        self.rss_gb = record["startup"]["rss_kb"] / GB_KB
        full = record.get("full_startup")
        self.full_rss_gb = full["rss_kb"] / GB_KB if full else None
        self.trees = pd.DataFrame(record["trees"])


class _PortFreed:
    """Stops the backend service for the bench when it runs; starts it again after."""

    def __enter__(self):
        active = subprocess.run(
            ["systemctl", "--user", "is-active", "--quiet", be_service_name]
        )
        self.stopped = active.returncode == 0
        if self.stopped:
            subprocess.run(["systemctl", "--user", "stop", be_service_name], check=True)
        if not port_free(PORT):
            raise SystemExit(
                f"{DEFAULT_BE_ADDR} is held by something other than {be_service_name}"
            )
        return self

    def __exit__(self, *_):
        if self.stopped:
            subprocess.run(
                ["systemctl", "--user", "start", be_service_name], check=True
            )


def _start(server: ServerProcess, log: Path) -> dict:
    started = time.perf_counter()
    server.start(log)
    server.wait_ready()
    assert server.pid is not None
    listening = subprocess.run(
        ["ss", "-Hltnp", f"sport = :{PORT}"], capture_output=True, text=True
    ).stdout
    assert f"pid={server.pid}," in listening, f"port {PORT} is not the bench server's"
    return {"seconds": time.perf_counter() - started, **_status(server.pid)}


def _build_all(
    server: ServerProcess, min_citations: int, limit: int, trees_path: Path
) -> list[dict]:
    assert server.pid is not None
    work = BatchRequester(min_citations, DEFAULT_BE_ADDR).urled_sample
    work = work.sort_values("cut_basis").reset_index(drop=True)
    if limit:
        work = work.head(limit)
    rows = []
    with gzip.open(trees_path, "wt") as trees:
        for s in tqdm(work.itertuples(), total=len(work)):
            key = {k: getattr(s, k) for k in KEY}
            row, children = _build(server.pid, s.url, s.rt, s.tid)
            rows.append(key | row | {DMIC: s.dmId, "cut_basis": s.cut_basis})
            trees.write(json.dumps(key | {"children": children}) + "\n")
    return rows


def _build(pid: int, url: str, rt: str, tid: int) -> tuple[dict, dict]:
    before = _status(pid)
    Path(f"/proc/{pid}/clear_refs").write_text("5")
    cpu = _cpu_s(pid)
    started = time.perf_counter()
    resp = requests.get(url)
    wall = time.perf_counter() - started
    cpu = _cpu_s(pid) - cpu
    after = _status(pid)
    resp.raise_for_status()
    body = resp.json()
    assert body, f"no tree at {url}"
    levels = [b["attributeType"] for b in TREE_SPECS["specs"][rt][tid]["breakdowns"]]
    row = {
        "wall_s": wall,
        "cpu_s": cpu,
        "rss_before_kb": before["rss_kb"],
        "peak_kb": after["hwm_kb"] - before["rss_kb"],
    }
    return row, _relabel(body["tree"]["children"], levels, body["atts"])


def _status(pid: int) -> dict:
    fields = {"VmRSS": "rss_kb", "VmHWM": "hwm_kb", "RssAnon": "anon_kb"}
    pairs = (
        line.split(":", 1)
        for line in Path(f"/proc/{pid}/status").read_text().splitlines()
    )
    return {fields[k]: int(v.split()[0]) for k, v in pairs if k in fields}


# The server's user + system time; with one request in flight, a request's is its delta.
def _cpu_s(pid: int) -> float:
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return (int(fields[11]) + int(fields[12])) / CLOCK_TICKS


def _runs(log: Path) -> pd.DataFrame:
    found = (RUNS_LINE.match(line) for line in log.read_text().splitlines())
    rows = [(m[1], int(m[2]), int(m[3]), *map(int, m.groups()[3:])) for m in found if m]
    return pd.DataFrame(rows, columns=[RTC, DMIC, TIDC, *RUN_COLS]).astype(
        {DMIC: int, TIDC: int}
    )


# Keys are dm ids, which follow file order and so differ between pipeline runs; names do not.
# A level without labels (quartiles) keeps its keys.
def _relabel(children: dict, levels: list[str], atts: dict) -> dict:
    labels = atts.get(levels[0], {})
    return {
        labels.get(k, {}).get("name", k): v
        | (
            {"children": _relabel(v["children"], levels[1:], atts)}
            if "children" in v
            else {}
        )
        for k, v in children.items()
    }


def _trees(path: Path) -> dict[tuple, dict]:
    with gzip.open(path / TREES, "rt") as f:
        lines = (json.loads(line) for line in f)
        return {tuple(t[k] for k in KEY): t["children"] for t in lines}


def _structure(a: Path, b: Path, joined: pd.DataFrame) -> pd.DataFrame:
    ta, tb = _trees(a), _trees(b)
    stats = []
    for s in joined.itertuples():
        k = tuple(getattr(s, c) for c in KEY)
        diff = make_diff_df(ta[k], "a", tb[k], "b")
        both = diff.loc[(diff.a_linkCount > 0) & (diff.b_linkCount > 0)]
        links = metric_stats(diff, "linkCount", "a", "b") or {}
        stats.append(
            {
                "nodes": len(diff),
                "exact_links": (both.a_linkCount == both.b_linkCount).mean(),
                "exact_sources": (both.a_sourceCount == both.b_sourceCount).mean(),
                **{f"links_{m}": v for m, v in links.items()},
                **top_source_stats(diff, "a", "b"),
            }
        )
    return pd.DataFrame(stats).describe().T[["count", "mean", "min", "max"]].round(4)


_dispatcher = Dispatcher("pyscripts tree-bench", {"run": run, "compare": compare})
