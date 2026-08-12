"""Stress-suite driver + memory sampler (phases in
.cril/writeups/2026-07-10-alpha-stress-suite.md).

    uv run -m pyscripts stress --corpus slugs.gz --ssh-host rankless-alpha   # DEFAULT: meltdown
    uv run -m pyscripts stress capacity                    # fleet ceiling (= `make capacity`)
    uv run -m pyscripts stress capacity --worker-port 4000 --restart   # one worker, isolated
    uv run -m pyscripts stress feleak --abort --corpus slugs.gz --ssh-host rankless-alpha \
        --worker-port 4200 --local-port 14005 --restart   # single-worker leak regression test
    uv run -m pyscripts stress churn --corpus slugs.gz --base https://alpha-api.rankless.org
    uv run -m pyscripts stress sample --ssh-host rankless-alpha

`meltdown` (DEFAULT) tears the FE deployment down: a bounded abort-flood
(requests that disconnect MID-RENDER — the real leak trigger) round-robin across
ALL workers on the box until it OOMs. bun retains the request context when the
client aborts before the response finishes; live hits this via nginx->bun
upstream timeouts/resets. Add `--abort` to `feleak` for the isolated single-worker
version (the fix's regression test: RSS climbs = leak, flat = ok). `capacity`
(= `make capacity`) measures the serving ceiling of the WHOLE active fleet
through the real path: it drives https://alpha from wherever it is invoked,
carrying the secret X-Loadtest token (LOADTEST_TOKEN in .env, rendered into the
alpha nginx conf by `make sync_nginx_to_alpha`) that exempts it from the per-IP
rate limit and bypasses the proxy caches. nginx round-robins the fleet, gzip
keeps the bandwidth off-box-friendly, and — the point — every test request is
an access-log line, uniform with the concurrent external traffic (alpha is
public). The report pulls the log and prints the two yardsticks: the total
request frequency where render latency degrades (log `urt`, upstream response
time — immune to client-link drain, unlike `rt`) and where 5xx start; 429s
would reveal the rate limiter throttling SSR fetches, `hit` a broken cache
bypass. Levels are per-worker concurrency (total = level x fleet size, size
detected via deploy.py). `--worker-port` instead ramps ONE tunneled worker over
loopback — the nginx-free pure-bun baseline for isolation work. Use capacity
before/after a perf change (sync FE / restart backend, re-run).
`churn` (T3) hammers tree computes over a slug corpus (lines like
`authors/some-slug`, `.gz` ok) with fixed concurrency, cycling shuffled slugs
across random tids; emits periodic JSONL stats. `replay` (T6) re-fires a real
nginx request stream (TSV: offset-seconds, host, path) at original timing
compressed by --speedup, hosts rewritten via --host-map — pages exercise the
FE fleet, `/v1` lines carry the true endpoint mix. `feleak` isolates ONE bun FE
worker: it opens an SSH tunnel to that worker's port, floods it with page
renders from THIS machine at lean concurrency, and samples the worker's cgroup
RSS over SSH — measuring the bun leak with zero cross-worker CPU contention (the
12-way on-box flood just CPU-thrashes: bun SSR is single-threaded per worker, so
concurrency must stay ~2/worker or render latency collapses and the leak stalls).
`sample` reads the backend cgroup + user@ PSI over SSH every interval into a CSV
— PSI is what oomd kills on, so it is a first-class column. The sampler outlives
the target dying: a row with an `err` marker records the outage window.

Standalone-runnable (stdlib + httpx only): scp this file to a box and
`uv run --with httpx stress.py replay ...` — no repo needed there.
"""

import argparse
import asyncio
import contextlib
import gzip
import json
import os
import random
import re
import shlex
import socket
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, TYPE_CHECKING
from urllib.parse import quote_plus

import httpx

if TYPE_CHECKING:
    from pyscripts.deploy import Transper

YEAR = 1950
LOG_DIR = Path(__file__).parent.parent / "logs" / "stress"
CG_USER = "/sys/fs/cgroup/user.slice/user-1000.slice/user@1000.service"
CG_BE = f"{CG_USER}/app.slice/rankless-backend.service"
# Payload/latency problems worth flagging on their own (product perf debt, not
# just load-test noise): observed author pages up to 1.5 MB and ~600 ms renders.
# A page should not ship a megabyte of HTML nor take half a second to render —
# both inflate FE working-set per in-flight request and cap render throughput,
# which is what makes the bun leak bite. Every phase counts + surfaces these.
PAGE_SIZE_WARN = 500_000  # bytes
LATENCY_WARN = 0.30  # seconds
# FE ports: blue 4000-4011, green 4200-4211 (FE_BUILD_PORTS_STARTS in deploy.py).
# The live blue/green slot flips on each deploy, so derive the cgroup slice from
# the port rather than hardcoding a color.
FE_GREEN_START = 4200
SAMPLE_COMM = (
    f"cat {CG_BE}/memory.current; "
    f"grep -E '^(anon|file) ' {CG_BE}/memory.stat; "
    f"cat {CG_BE}/memory.peak 2>/dev/null || echo 0; "
    f"cat {CG_USER}/memory.pressure; "
    "grep MemAvailable /proc/meminfo"
)
SAMPLE_COLS = [
    "ts",
    "mem_current",
    "anon",
    "file",
    "mem_peak",
    "psi_some_avg10",
    "psi_some_avg60",
    "psi_full_avg10",
    "psi_full_avg60",
    "mem_avail_kb",
    "err",
]


@dataclass
class WindowStats:
    started: float = field(default_factory=time.monotonic)
    by_status: dict[str, int] = field(default_factory=dict)
    times: list[float] = field(default_factory=list)
    bytes_: int = 0
    wire_bytes: int = 0  # on-the-wire (compressed) — the link-saturation signal
    max_bytes: int = 0
    big: int = 0  # responses over PAGE_SIZE_WARN
    slow: int = 0  # responses over LATENCY_WARN

    def add(self, status: str, elapsed: float, nbytes: int, wire: int = 0) -> None:
        self.by_status[status] = self.by_status.get(status, 0) + 1
        self.times.append(elapsed)
        self.bytes_ += nbytes
        self.wire_bytes += wire
        self.max_bytes = max(self.max_bytes, nbytes)
        self.big += nbytes > PAGE_SIZE_WARN
        self.slow += elapsed > LATENCY_WARN

    def flush(self) -> dict:
        dt_s = time.monotonic() - self.started
        ts = sorted(self.times)
        n = len(ts)
        out = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "n": n,
            "by_status": dict(sorted(self.by_status.items())),
            "rps": round(n / dt_s, 1),
            "mbps": round(self.bytes_ * 8 / dt_s / 1e6, 1),
            "wire_mbps": round(self.wire_bytes * 8 / dt_s / 1e6, 1),
            "p50_ms": round(ts[n // 2] * 1e3) if n else None,
            "p99_ms": round(ts[int(n * 0.99)] * 1e3) if n else None,
            "max_kb": round(self.max_bytes / 1024),
            "big": self.big,
            "slow": self.slow,
        }
        self.__init__()
        return out


def load_corpus(path: Path) -> list[tuple[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as fh:
        pairs = [tuple(ln.strip().split("/", 1)) for ln in fh if "/" in ln]
    random.seed(42)
    random.shuffle(pairs)
    return pairs


def get_tids(base: str) -> dict[str, int]:
    specs = httpx.get(f"{base}/v1/specs", timeout=30).json()["specs"]
    return {rt: len(ss) for rt, ss in specs.items()}


async def get_once(client: httpx.AsyncClient, url: str, stats: WindowStats) -> None:
    t0 = time.monotonic()
    try:
        resp = await client.get(url)
        stats.add(
            str(resp.status_code),
            time.monotonic() - t0,
            len(resp.content),
            resp.num_bytes_downloaded,
        )
    except httpx.HTTPError as e:
        stats.add(type(e).__name__, time.monotonic() - t0, 0)


async def report_loop(
    stats: WindowStats, out_path: Path, every: int, stop: asyncio.Event
) -> None:
    with out_path.open("a") as fh:
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=every)
            except TimeoutError:
                pass
            line = json.dumps(stats.flush())
            fh.write(line + "\n")
            fh.flush()
            print(line, flush=True)


def make_client(
    concurrency: int, timeout: float, headers: dict[str, str] | None = None
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        limits=httpx.Limits(max_connections=concurrency + 4),
        timeout=httpx.Timeout(timeout, connect=15),
        headers=headers,
    )


async def churn(args: argparse.Namespace) -> None:
    corpus = load_corpus(Path(args.corpus))
    tids = get_tids(args.base)
    corpus = [(rt, slug) for rt, slug in corpus if rt in tids]
    print(f"corpus: {len(corpus)} slugs, tids: {tids}")

    out_path = LOG_DIR / f"churn-{datetime.now():%m%d-%H%M}.jsonl"
    deadline = time.monotonic() + args.hours * 3600
    stats = WindowStats()
    stop = asyncio.Event()
    cursor = [0]

    async def worker(client: httpx.AsyncClient) -> None:
        while time.monotonic() < deadline:
            rt, slug = corpus[cursor[0] % len(corpus)]
            cursor[0] += 1
            url = (
                f"{args.base}/v1/trees/{rt}/{quote_plus(slug)}"
                f"?tid={random.randrange(tids[rt])}&year={YEAR}"
            )
            await get_once(client, url, stats)
        stop.set()

    async with make_client(args.concurrency, args.timeout) as client:
        await asyncio.gather(
            report_loop(stats, out_path, args.report_every, stop),
            *(worker(client) for _ in range(args.concurrency)),
        )
    print(f"done: {out_path}")


async def replay(args: argparse.Namespace) -> None:
    # Corpus lines: "offset_s<TAB>host<TAB>path" (see the extraction awk in
    # docs of the stress plan); --host-map rewrites log hosts to target bases.
    base_map = dict(kv.split("=", 1) for kv in args.host_map.split(","))
    path = Path(args.corpus)
    opener = gzip.open if path.suffix == ".gz" else open
    events = []
    with opener(path, "rt") as fh:
        for ln in fh:
            parts = ln.rstrip("\n").split("\t")
            if len(parts) == 3 and parts[1] in base_map:
                events.append((float(parts[0]), base_map[parts[1]], parts[2]))
    events.sort(key=lambda e: e[0])
    span = events[-1][0] - events[0][0]
    print(f"replay: {len(events)} events / {span / 3600:.2f}h, x{args.speedup}")

    out_path = LOG_DIR / f"replay-{datetime.now():%m%d-%H%M}.jsonl"
    stats = WindowStats()
    stop = asyncio.Event()
    sem = asyncio.Semaphore(args.concurrency)

    async def fire(client: httpx.AsyncClient, url: str) -> None:
        try:
            await get_once(client, url, stats)
        finally:
            sem.release()

    async def producer(client: httpx.AsyncClient) -> None:
        t_zero, start = events[0][0], time.monotonic()
        pending = set()
        for off, base, pth in events:
            delay = start + (off - t_zero) / args.speedup - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            await sem.acquire()
            task = asyncio.create_task(fire(client, base + pth))
            pending.add(task)
            task.add_done_callback(pending.discard)
        while pending:
            await asyncio.sleep(1)
        stop.set()

    async with make_client(args.concurrency, args.timeout) as client:
        await asyncio.gather(
            report_loop(stats, out_path, args.report_every, stop), producer(client)
        )
    print(f"done: {out_path}")


@contextlib.contextmanager
def ssh_tunnel(host: str, local_port: int, remote_port: int):
    """Local `local_port` -> host's 127.0.0.1:`remote_port`, torn down on exit."""
    proc = subprocess.Popen(
        [
            "ssh", "-N",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=30",
            "-L", f"{local_port}:127.0.0.1:{remote_port}",
            host,
        ]
    )  # fmt: skip
    try:
        for _ in range(40):
            with contextlib.suppress(OSError):
                socket.create_connection(("127.0.0.1", local_port), timeout=1).close()
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(f"tunnel to {host}:{remote_port} never bound")
        print(f"tunnel up: localhost:{local_port} -> {host}:{remote_port}")
        yield
    finally:
        proc.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=5)


def fe_worker_stat(host: str, port: int) -> tuple[int, int, float]:
    """(worker process RSS MiB, NRestarts, box 1-min loadavg) over SSH.

    Reads the bun MainPID's VmRSS — the btop number and the OOM-relevant heap.
    NOT cgroup `memory.current`, which counts reclaimable page cache and gave a
    false "balloon" on the disk-card-cache-writing card path (2026-07-11).
    """
    color = "green" if port >= FE_GREEN_START else "blue"
    unit = f"rankless-frontend-{color}@{port}"
    comm = (
        f"pid=$(systemctl --user show {unit} -p MainPID --value); "
        "awk '/VmRSS/{print $2}' /proc/$pid/status 2>/dev/null || echo 0; "
        f"systemctl --user show {unit} -p NRestarts --value 2>/dev/null || echo 0; "
        "cut -d' ' -f1 /proc/loadavg"
    )
    out = subprocess.check_output(
        ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", host, comm],
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=25,
    )
    rss_kb, nr, ld = out.split()
    return int(rss_kb) // 1024, int(nr), float(ld)


def detect_fe(host: str) -> list[tuple[str, int]]:
    """Running FE workers as (color, port) pairs, sorted by port — handles a
    mixed blue+green pool (e.g. after an OOM recovery relit both slots)."""
    out = subprocess.check_output(
        [
            "ssh",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "BatchMode=yes",
            host,
            "systemctl --user list-units 'rankless-frontend-*.service' "
            "--state=running --no-legend --plain | awk '{print $1}'",
        ],
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=25,
    )
    pairs = [(m[1], int(m[2])) for m in re.finditer(r"frontend-(\w+)@(\d+)", out)]
    assert pairs, "no running FE workers found on the box"
    return sorted(pairs, key=lambda cp: cp[1])


def fleet_stat(host: str, workers: list[tuple[str, int]]) -> tuple[int, int, int]:
    """(total FE RSS MiB, hottest worker MiB, box MemAvailable MiB) in one SSH."""
    units = " ".join(f"rankless-frontend-{c}@{p}" for c, p in workers)
    comm = (
        f"tot=0; mx=0; for u in {units}; do "
        "pid=$(systemctl --user show $u -p MainPID --value); "
        'r=$(awk "/VmRSS/{print \\$2}" /proc/$pid/status 2>/dev/null || echo 0); '
        'm=$((r/1024)); tot=$((tot+m)); [ "$m" -gt "$mx" ] && mx=$m; done; '
        'echo "$tot $mx $(free -m | awk "/Mem:/{print \\$7}")"'
    )
    out = subprocess.check_output(
        ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", host, comm],
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=25,
    )
    tot, mx, avail = out.split()
    return int(tot), int(mx), int(avail)


def build_meltdown_corpus(base: str, n_slugs: int = 50000) -> Path:
    """Fetch distinct author slugs from the backend into a temp corpus (so
    `make stress` needs no corpus file). Aborts leak per-request, so ~50k
    distinct slugs cycled is plenty to OOM the box."""
    slugs, step = [], 5000
    for start in range(0, 5_000_000, step):
        rows = httpx.get(
            f"{base}/v1/slice/authors/{start}/{start + step}", timeout=30
        ).json()
        if not rows:
            break
        slugs += [r["semanticId"] for r in rows if r.get("semanticId")]
        if len(slugs) >= n_slugs:
            break
    slugs = slugs[:n_slugs]
    path = LOG_DIR / "meltdown-corpus.gz"
    with gzip.open(path, "wt") as fh:
        fh.writelines(f"authors/{s}\n" for s in slugs)
    print(f"built corpus: {len(slugs)} author slugs from {base}")
    return path


def meltdown(args: argparse.Namespace) -> None:
    """Tear the whole FE deployment down: bounded abort-flood (client disconnects
    mid-render) round-robin across ALL workers on the box until the box OOMs.

    Reproduces the real outage — the leak is that bun retains the request context
    when the client aborts before the response completes (live's nginx->bun
    upstream timeouts/resets). Runs on the box (loopback), monitors to death.
    """
    host, kind, n = args.ssh_host, args.page_kind, args.n
    workers = detect_fe(host)
    ports = [p for _, p in workers]
    print(f"meltdown: {len(ports)} workers {ports[0]}-{ports[-1]}, {n} aborts")
    local_corpus = (
        Path(args.corpus) if args.corpus else build_meltdown_corpus(args.base)
    )
    remote_corpus = "/tmp/stress_meltdown_corpus.gz"
    subprocess.run(
        ["scp", "-q", str(local_corpus), f"{host}:{remote_corpus}"],
        check=True,
        timeout=180,
    )
    ports_str = " ".join(map(str, ports))
    # Cycle the slug list to N requests round-robin across ports (aborts leak
    # per-request, not per-distinct-slug, so a modest corpus reaches OOM).
    flood = (
        f"zcat {remote_corpus} | awk -F/ '$1==\"{kind}\"{{print $2}}' | "
        f"awk -v pl='{ports_str}' -v N={n} 'BEGIN{{np=split(pl,P,\" \")}}"
        f"{{s[NR]=$0}} END{{for(i=0;i<N;i++)"
        f' print "http://127.0.0.1:" P[(i%np)+1] "/{kind}/" s[(i%NR)+1]}}\' | '
        f"xargs -P {args.concurrency} -I{{}} "
        f"curl -s -o /dev/null --max-time {args.abort_timeout} {{}}"
    )
    subprocess.run(
        [
            "ssh",
            host,
            f"setsid bash -c {shlex.quote(flood)} </dev/null >/dev/null 2>&1 &",
        ],
        check=True,
        timeout=30,
    )
    print("abort flood launched on box; monitoring to OOM (Ctrl-C to stop)...")
    t0 = time.monotonic()
    while True:
        el = round((time.monotonic() - t0) / 60)
        try:
            tot, mx, avail = fleet_stat(host, workers)
        except (subprocess.SubprocessError, OSError):
            print(f"*** BOX UNREACHABLE at {el}min — MELTDOWN (session OOM-killed) ***")
            return
        note = "  >>> OOM imminent" if avail < 1500 else ""
        print(f"t={el}min FE_total={tot}MB max={mx}MB avail={avail}MB{note}")
        time.sleep(args.interval)


def restart_fe_worker(host: str, port: int) -> None:
    color = "green" if port >= FE_GREEN_START else "blue"
    subprocess.run(
        ["ssh", host, f"systemctl --user restart rankless-frontend-{color}@{port}"],
        check=True,
        timeout=30,
    )
    time.sleep(8)


async def feleak(args: argparse.Namespace) -> None:
    kind = args.page_kind
    if args.restart:
        restart_fe_worker(args.ssh_host, args.worker_port)
    slugs = [s for k, s in load_corpus(Path(args.corpus)) if k == kind]
    assert slugs, f"no '{kind}' slugs in corpus"
    base, prefix = f"http://127.0.0.1:{args.local_port}", f"/{kind}/"
    baseline, _, _ = fe_worker_stat(args.ssh_host, args.worker_port)
    print(
        f"feleak: {len(slugs)} {kind} slugs -> worker {args.worker_port} "
        f"(conc {args.concurrency}); baseline {baseline}MiB"
    )
    out_path = LOG_DIR / f"feleak-{args.worker_port}-{datetime.now():%m%d-%H%M}.csv"
    deadline = time.monotonic() + args.hours * 3600
    stats, stop, cursor = WindowStats(), asyncio.Event(), [0]

    async def flood(client: httpx.AsyncClient) -> None:
        while time.monotonic() < deadline:
            slug = slugs[cursor[0] % len(slugs)]
            cursor[0] += 1
            await get_once(client, f"{base}{prefix}{quote_plus(slug)}", stats)
        stop.set()

    async def sampler(fh) -> None:
        cols = "ts,elapsed_s,worker_mib,delta_mib,restarts,boxload,rps,p50_ms,p99_ms,max_kb,big,slow"
        fh.write(cols + "\n")
        fh.flush()
        t0 = time.monotonic()
        while not stop.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=args.interval)
            try:
                mib, nr, ld = await asyncio.to_thread(
                    fe_worker_stat, args.ssh_host, args.worker_port
                )
            except (subprocess.SubprocessError, OSError):
                mib, nr, ld = -1, -1, -1.0
            w = stats.flush()
            row = [
                datetime.now().isoformat(timespec="seconds"),
                round(time.monotonic() - t0),
                mib, mib - baseline, nr, ld,
                w["rps"], w["p50_ms"], w["p99_ms"], w["max_kb"], w["big"], w["slow"],
            ]  # fmt: skip
            fh.write(",".join(map(str, row)) + "\n")
            fh.flush()
            print(
                f"t={row[1]}s worker={mib}MiB (+{mib - baseline}) restarts={nr} "
                f"load={ld} rps={w['rps']} p50={w['p50_ms']}ms max={w['max_kb']}KB "
                f"big={w['big']} slow={w['slow']}",
                flush=True,
            )

    with out_path.open("a") as fh:
        async with make_client(args.concurrency, args.timeout) as client:
            await asyncio.gather(
                sampler(fh), *(flood(client) for _ in range(args.concurrency))
            )
    print(f"done: {out_path}")


CAPACITY_UA = "rankless-capacity"
CAP_HEADER = (
    f"{'conc/w':>6} {'total':>6} {'req/s':>7} {'p50ms':>6} {'p99ms':>6} "
    f"{'MB/s':>6} {'wire':>6} {'err%':>5}"
)


def fmt_cap_row(r: dict) -> str:
    # MB/s = decompressed page bytes; wire = compressed on-the-wire MB/s — the
    # column to watch for driver-link saturation.
    return (
        f"{r['conc']:>6} {r['total']:>6} {r['rps']:>7} {str(r['p50_ms']):>6} "
        f"{str(r['p99_ms']):>6} {r['mbps'] / 8:>6.1f} {r['wire_mbps'] / 8:>6.1f} "
        f"{r['err_pct']:>5.1f}"
    )


async def capacity_ramp(
    args: argparse.Namespace, base_root: str, headers: dict[str, str], n_workers: int
) -> list[dict]:
    """Ramp completing-request concurrency against `base_root` and print the
    client-side curve. Levels are per-worker and may be fractional (0.5 = one
    in-flight request per two workers): total = round(level x n_workers), so
    the ramp traces the pre-saturation knee — a 12-worker fleet saturates near
    1/worker. The slug cursor is global so later levels keep hitting fresh
    slugs instead of re-warmed ones."""
    kind = args.page_kind
    slugs = [s for k, s in load_corpus(Path(args.corpus)) if k == kind]
    assert slugs, f"no '{kind}' slugs in corpus"
    base = f"{base_root}/{kind}/"
    rows: list[dict] = []
    cursor = [0]
    print(f"capacity: {base_root}, x{n_workers} workers, {args.step_seconds}s/level")
    print(CAP_HEADER)
    for lvl in (float(x) for x in args.levels.split(",")):
        conc = int(lvl) if lvl.is_integer() else lvl
        total = max(1, round(lvl * n_workers))
        stats = WindowStats()
        deadline = time.monotonic() + args.step_seconds

        async def one(client: httpx.AsyncClient) -> None:
            while time.monotonic() < deadline:
                slug = slugs[cursor[0] % len(slugs)]
                cursor[0] += 1
                await get_once(client, base + quote_plus(slug), stats)

        t0 = time.time()
        async with make_client(total, args.timeout, headers) as client:
            await asyncio.gather(*(one(client) for _ in range(total)))
        w = stats.flush()
        errs = sum(v for k, v in w["by_status"].items() if not k.startswith("2"))
        row = {
            "conc": conc,
            "total": total,
            "t0": round(t0, 3),
            "t1": round(time.time(), 3),
            "err_pct": round(100 * errs / max(1, w["n"]), 2),
            **w,
        }
        rows.append(row)
        print(fmt_cap_row(row), flush=True)
        if row["err_pct"] > args.err_threshold:
            print(f"  >>> >{args.err_threshold}% errors at {conc}/worker — ceiling")
            break
    return rows


def capacity_fleet(args: argparse.Namespace) -> None:
    """Drive the whole fleet through nginx via the X-Loadtest lane (see module
    docstring), then draw the yardsticks from the access log — where our
    requests and concurrent external traffic are uniform lines."""
    from pyscripts.deploy import ALPHA_DOMAIN, get_running_tpr

    token = os.environ.get("LOADTEST_TOKEN")
    assert token, "LOADTEST_TOKEN not in env (.env) — see setup_nginx in deploy.py"
    tpr = get_running_tpr(False)
    conf = tpr.get_fe_systems()[-1]  # active (nginx-routed) slot
    print(f"fleet: {conf.n_procs} active workers from port {conf.start_port}")
    if args.restart:
        print("restarting the active fleet (brief public blip) ...")
        for service in tpr._iter_conf_services(conf):
            service.restart()
        while tpr._validate_fe(conf):
            pass
    headers = {"X-Loadtest": token, "User-Agent": CAPACITY_UA}
    rows = asyncio.run(
        capacity_ramp(args, f"https://{ALPHA_DOMAIN}", headers, conf.n_procs)
    )
    capacity_report(tpr, rows)


def merge_log_windows(
    df, rows: list[dict], page_host: str, be_host: str, ua: str
) -> None:
    """Fold each level's nginx-log window into its row. Every request is a log
    line: the frequency axis is total FE-host req/s (ours + external, assets
    included); `urt` (upstream response time) is the render-side latency,
    immune to client-link drain, from OUR lines only (split by user agent)."""
    import pandas as pd

    def p_ms(series, q: float) -> int | None:
        v = series.quantile(q)
        return None if pd.isna(v) else round(v * 1e3)

    for r in rows:
        t0, t1 = (pd.Timestamp(r[k], unit="s", tz="UTC") for k in ("t0", "t1"))
        w = df[(df["t"] >= t0) & (df["t"] < t1)]
        dur = max(r["t1"] - r["t0"], 1e-9)
        fe = w[w["host"] == page_host]
        ours = fe[fe["agent"] == ua]
        be = w[w["host"] == be_host]
        r["log_rps"] = round(len(fe) / dur, 1)
        r["ext_rps"] = round((len(fe) - len(ours)) / dur, 1)
        r["urt_p50_ms"] = p_ms(ours["urt"], 0.5)
        r["urt_p99_ms"] = p_ms(ours["urt"], 0.99)
        r["be_rps"] = round(len(be) / dur, 1)
        r["be_p50_ms"] = p_ms(be["urt"], 0.5)
        r["log_5xx"] = int((w["code"] >= 500).sum())
        r["log_429"] = int((w["code"] == 429).sum())
        r["our_hits"] = int((ours["cs"] == "HIT").sum())  # >0 = cache bypass broken


def yardsticks(rows: list[dict]) -> tuple[dict | None, dict | None, str]:
    """(latency-degradation onset row, error onset row, latency key used);
    None = not reached. Degradation = render-side p50 (log urt; client p50 when
    no log view) above 1.5x the first level's; errors = any client non-2xx or
    any 5xx in the log window."""
    key = "urt_p50_ms" if rows[0].get("urt_p50_ms") else "p50_ms"
    base = rows[0][key]
    degrade = next(
        (r for r in rows if base and r.get(key) and r[key] > 1.5 * base), None
    )
    first_err = next(
        (r for r in rows if r["err_pct"] > 0 or r.get("log_5xx", 0) > 0), None
    )
    return degrade, first_err, key


def capacity_report(tpr: "Transper", rows: list[dict]) -> None:
    from pyscripts.deploy import ALPHA_BACKEND, ALPHA_DOMAIN

    span_min = (time.time() - rows[0]["t0"]) / 60 + 2
    n_lines = min(600_000, max(60_000, int(span_min * 60 * 500)))
    df = tpr.get_nginx_logs_df(minutes=span_min, n=n_lines)
    merge_log_windows(df, rows, ALPHA_DOMAIN, ALPHA_BACKEND, CAPACITY_UA)
    print("\n== nginx-log view (req/s = all FE-host lines, ours + external) ==")
    print(
        f"{'conc/w':>6} {'req/s':>7} {'ext':>5} {'be/s':>6} {'urt50':>6} "
        f"{'urt99':>6} {'be50':>5} {'err%':>5} {'5xx':>5} {'429':>5} {'hit':>4}"
    )
    for r in rows:
        print(
            f"{r['conc']:>6} {r['log_rps']:>7} {r['ext_rps']:>5} {r['be_rps']:>6} "
            f"{str(r['urt_p50_ms']):>6} {str(r['urt_p99_ms']):>6} "
            f"{str(r['be_p50_ms']):>5} {r['err_pct']:>5.1f} {r['log_5xx']:>5} "
            f"{r['log_429']:>5} {r['our_hits']:>4}"
        )
    degrade, first_err, key = yardsticks(rows)
    base, top_rps = rows[0][key], max(r["log_rps"] for r in rows)
    if degrade:
        print(
            f"latency degradation onset: ~{degrade['log_rps']} req/s "
            f"({key} {base} -> {degrade[key]} ms at {degrade['conc']}/worker)"
        )
    else:
        print(
            f"no latency degradation up to ~{top_rps} req/s "
            f"({key} {base} -> {rows[-1][key]} ms)"
        )
    if first_err:
        print(
            f"5xx onset: ~{first_err['log_rps']} req/s (client err "
            f"{first_err['err_pct']}%, log 5xx {first_err['log_5xx']})"
        )
    else:
        print(f"5xx onset: not reached (0 errors up to ~{top_rps} req/s)")
    out_path = LOG_DIR / f"capacity-{datetime.now():%m%d-%H%M}.json"
    out_path.write_text(json.dumps(rows, indent=1))
    print(f"results: {out_path}")


def sample(args: argparse.Namespace) -> None:
    out_path = LOG_DIR / f"sample-{datetime.now():%m%d-%H%M}.csv"
    with out_path.open("a") as fh:
        fh.write(",".join(SAMPLE_COLS) + "\n")
        while True:
            row = _sample_row(args.ssh_host)
            fh.write(",".join(map(str, row)) + "\n")
            fh.flush()
            print(
                f"{row[0]} anon={int(row[2]) / 2**30:.2f}G" if not row[-1] else row,
                flush=True,
            )
            time.sleep(args.interval)


def _sample_row(host: str) -> list:
    ts = datetime.now().isoformat(timespec="seconds")
    try:
        out = subprocess.check_output(
            [
                "ssh",
                "-o",
                "ConnectTimeout=10",
                "-o",
                "BatchMode=yes",
                host,
                SAMPLE_COMM,
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=25,
        )
    except (subprocess.SubprocessError, OSError) as e:
        return [ts, *[""] * 9, type(e).__name__]
    lines = out.strip().split("\n")
    current = int(lines[0])
    anon = int(lines[1].split()[1])
    file_ = int(lines[2].split()[1])
    peak = int(lines[3])
    some = dict(kv.split("=") for kv in lines[4].split()[1:])
    full = dict(kv.split("=") for kv in lines[5].split()[1:])
    avail = int(lines[6].split()[1])
    return [
        ts,
        current,
        anon,
        file_,
        peak,
        some["avg10"],
        some["avg60"],
        full["avg10"],
        full["avg60"],
        avail,
        "",
    ]


def main(
    phase: Literal[
        "meltdown", "capacity", "churn", "replay", "feleak", "sample"
    ] = "meltdown",
    *,
    base: str = "https://alpha-api.rankless.org",
    corpus: str | None = None,
    concurrency: int = 16,
    hours: float = 8.0,
    speedup: float = 1.0,
    host_map: str = "www.rankless.org=https://alpha.rankless.org,"
    "api.rankless.org=https://alpha-api.rankless.org",
    timeout: float = 120.0,
    report_every: int = 60,
    ssh_host: str = "rankless-alpha",
    interval: int = 30,
    worker_port: int | None = None,
    local_port: int = 14001,
    page_kind: str = "authors",
    levels: str = "0.25,0.5,1,2,4,8",
    step_seconds: float = 20.0,
    err_threshold: float = 2.0,
    n: int = 180000,
    restart: bool = False,
    abort: bool = False,
    abort_timeout: float = 0.3,
) -> None:
    """Stress driver / sampler; default phase 'meltdown' tears the FE deployment
    down (abort-flood to OOM). See the module docstring for the phases."""
    _run_phases(argparse.Namespace(**locals()))


def _run_phases(args: argparse.Namespace) -> None:
    with contextlib.suppress(OSError):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    if args.phase == "sample":
        sample(args)
        return
    if args.phase == "meltdown":
        meltdown(args)  # auto-builds a corpus from --base if --corpus omitted
        return
    if args.phase == "capacity":
        if not args.corpus:
            args.corpus = str(build_meltdown_corpus(args.base))  # like meltdown
        if args.worker_port:  # ONE tunneled worker, nginx-free bun baseline
            if args.restart:
                restart_fe_worker(args.ssh_host, args.worker_port)
            with ssh_tunnel(args.ssh_host, args.local_port, args.worker_port):
                base = f"http://127.0.0.1:{args.local_port}"
                asyncio.run(capacity_ramp(args, base, {"User-Agent": CAPACITY_UA}, 1))
        else:
            capacity_fleet(args)
        return
    assert args.corpus, f"{args.phase} needs --corpus"
    # --abort forces a mid-render client disconnect (the leak trigger); the short
    # per-request timeout makes httpx close the connection before bun finishes.
    if args.abort:
        args.timeout = args.abort_timeout
    if args.phase == "feleak":
        args.worker_port = args.worker_port or 4000
        with ssh_tunnel(args.ssh_host, args.local_port, args.worker_port):
            asyncio.run(feleak(args))
        return
    asyncio.run({"churn": churn, "replay": replay}[args.phase](args))


if __name__ == "__main__":  # standalone copy on a box: pip install protocli
    from protocli import _build_parser

    _run_phases(_build_parser("stress", main).parse_args())
