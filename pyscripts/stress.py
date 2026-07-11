"""Stress-suite driver + memory sampler (phases in
.cril/plans/2026-07-10-alpha-stress-suite.md).

    uv run -m pyscripts stress --corpus slugs.gz --ssh-host rankless-alpha   # DEFAULT: meltdown
    uv run -m pyscripts stress feleak --abort --corpus slugs.gz --ssh-host rankless-alpha \
        --worker-port 4200 --local-port 14005 --restart   # single-worker leak regression test
    uv run -m pyscripts stress churn --corpus slugs.gz --base https://alpha-api.rankless.org
    uv run -m pyscripts stress sample --ssh-host rankless-alpha

`meltdown` (DEFAULT) tears the FE deployment down: a bounded abort-flood
(requests that disconnect MID-RENDER — the real leak trigger) round-robin across
ALL workers on the box until it OOMs. bun retains the request context when the
client aborts before the response finishes; live hits this via nginx->bun
upstream timeouts/resets. Add `--abort` to `feleak` for the isolated single-worker
version (the fix's regression test: RSS climbs = leak, flat = ok).
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
import random
import re
import shlex
import socket
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import httpx

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
    max_bytes: int = 0
    big: int = 0  # responses over PAGE_SIZE_WARN
    slow: int = 0  # responses over LATENCY_WARN

    def add(self, status: str, elapsed: float, nbytes: int) -> None:
        self.by_status[status] = self.by_status.get(status, 0) + 1
        self.times.append(elapsed)
        self.bytes_ += nbytes
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
        stats.add(str(resp.status_code), time.monotonic() - t0, len(resp.content))
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


def make_client(concurrency: int, timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        limits=httpx.Limits(max_connections=concurrency + 4),
        timeout=httpx.Timeout(timeout, connect=15),
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


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "phase",
        nargs="?",
        default="meltdown",
        choices=("meltdown", "churn", "replay", "feleak", "sample"),
        help="default 'meltdown' = tear the FE deployment down (abort-flood to OOM)",
    )
    parser.add_argument("--base", default="https://alpha-api.rankless.org")
    parser.add_argument(
        "--corpus", help="churn: rt/slug lines; replay: ts-host-path TSV (.gz ok)"
    )
    parser.add_argument(
        "--concurrency", type=int, default=16, help="feleak wants ~2/worker (e.g. 4)"
    )
    parser.add_argument("--hours", type=float, default=8.0)
    parser.add_argument("--speedup", type=float, default=1.0)
    parser.add_argument(
        "--host-map",
        default="www.rankless.org=https://alpha.rankless.org,"
        "api.rankless.org=https://alpha-api.rankless.org",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--report-every", type=int, default=60)
    parser.add_argument("--ssh-host", default="rankless-alpha")
    parser.add_argument("--interval", type=int, default=30)
    # feleak
    parser.add_argument("--worker-port", type=int, default=4000, help="bun FE port")
    parser.add_argument(
        "--local-port", type=int, default=14001, help="tunnel local port"
    )
    parser.add_argument(
        "--page-kind", default="authors", help="corpus slug kind to flood"
    )
    parser.add_argument(
        "--n", type=int, default=180000, help="meltdown: total abort requests to flood"
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="feleak: restart the worker first for a clean baseline",
    )
    # abort (the real leak trigger): client disconnects mid-render
    parser.add_argument(
        "--abort",
        action="store_true",
        help="feleak: abort requests mid-render (the leak trigger)",
    )
    parser.add_argument(
        "--abort-timeout",
        type=float,
        default=0.3,
        help="per-request timeout that forces a mid-render disconnect",
    )


def run(args: argparse.Namespace) -> None:
    """Stress driver / sampler. See module docstring."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if args.phase == "sample":
        sample(args)
        return
    if args.phase == "meltdown":
        meltdown(args)  # auto-builds a corpus from --base if --corpus omitted
        return
    assert args.corpus, f"{args.phase} needs --corpus"
    # --abort forces a mid-render client disconnect (the leak trigger); the short
    # per-request timeout makes httpx close the connection before bun finishes.
    if args.abort:
        args.timeout = args.abort_timeout
    tunneled = {"feleak": feleak}
    if args.phase in tunneled:
        with ssh_tunnel(args.ssh_host, args.local_port, args.worker_port):
            asyncio.run(tunneled[args.phase](args))
        return
    asyncio.run({"churn": churn, "replay": replay}[args.phase](args))


if __name__ == "__main__":
    _p = argparse.ArgumentParser(description=__doc__)
    add_arguments(_p)
    run(_p.parse_args())
