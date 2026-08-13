"""Calibration helper: probe machines, draft bands/procs/limits for warm.toml.

`probe` gathers per-box facts (RAM, disk, /tmp, cores, checkout, backend unit,
toolchain) — the readiness checklist for adding a machine to the fleet.
`suggest` turns probes + the actual warm worklist into a complete draft config:
bands tiled so estimated wall-clock is balanced by each box's `speed` weight,
every band capped by what the box's RAM can hold (the [model] coefficients),
the top band + bigs duty on the highest-ceiling box, `big_chunk` from /tmp.

The output is a draft to paste into data/warm.toml and hand-tune — the same
[model] numbers the preflight gate enforces are printed with it, so a lie here
fails loudly there.
"""

from dataclasses import dataclass, replace

from pyscripts import gitutil, services
from pyscripts.fleet.config import DEFAULT_PORT, Fleet, Model, Worker
from pyscripts.fleet.remote import Host

GB = 1024**3
MAX_PROCS = 16  # client-parallelism ceiling per bin
MAX_BIG_CHUNK = 8
COST_FLOOR_M = 1.0  # per-tree overhead so tiny trees still carry weight


@dataclass(frozen=True)
class Probe:
    name: str
    mem_total_gb: float = -1
    mem_avail_gb: float = -1
    cores: int = -1
    data_avail_gb: float = -1
    tmp_avail_gb: float = -1
    head: str = "?"
    unit: str = "?"
    tools_ok: bool = False


def probe(
    name: str, host: str | None, repo_dir: str = "", data_root: str = ""
) -> Probe:
    h = Host(name, host)
    fields: dict = {}

    def _try(key, comm, conv):
        try:
            fields[key] = conv(h.out(comm).strip())
        except Exception:
            pass  # absent facts stay at the dataclass sentinel

    _try("mem_total_gb", "free -b | awk '/Mem:/ {print $2}'", lambda s: int(s) / GB)
    _try("mem_avail_gb", "free -b | awk '/Mem:/ {print $7}'", lambda s: int(s) / GB)
    _try("cores", "nproc", int)
    _try("tmp_avail_gb", "df --output=avail -B1 /tmp | tail -1", lambda s: int(s) / GB)
    _try("unit", f"systemctl --user is-active {services.BACKEND_UNIT} || true", str)
    _try(
        "tools_ok",
        "command -v cargo >/dev/null && command -v uv >/dev/null && echo ok",
        lambda s: s == "ok",
    )
    if data_root:
        _try(
            "data_avail_gb",
            f"df --output=avail -B1 {data_root} | tail -1",
            lambda s: int(s) / GB,
        )
    if repo_dir:
        _try("head", f"cd {repo_dir} && {gitutil.HEAD_CMD}", str)
    return Probe(name=name, **fields)


def probe_fleet(fleet: Fleet) -> dict[str, Probe]:
    return {
        w.name: probe(w.name, w.host, w.repo_dir, w.data_root) for w in fleet.workers
    }


def print_probes(probes: dict[str, Probe]) -> None:
    hdr = f"{'worker':12} {'ram':>6} {'avail':>6} {'cores':>5} {'data':>7} {'/tmp':>7} {'unit':>8} {'tools':>5}  head"
    print(hdr)
    for p in probes.values():
        print(
            f"{p.name:12} {p.mem_total_gb:5.0f}G {p.mem_avail_gb:5.0f}G {p.cores:5} "
            f"{p.data_avail_gb:6.0f}G {p.tmp_avail_gb:6.0f}G {p.unit:>8} "
            f"{'ok' if p.tools_ok else 'MISS':>5}  {p.head}"
        )


def ceiling_mcut(p: Probe, model: Model) -> float:
    """Largest single in-flight tree (M cut_basis) this box can hold in RAM."""
    budget = p.mem_total_gb - model.mem_base_gb - model.headroom_gb
    return max(0.0, budget / model.gb_per_mcut)


def suggest_workers(
    fleet: Fleet, probes: dict[str, Probe], cuts_m: list[float]
) -> list[Worker]:
    model = fleet.model
    cuts = sorted(cuts_m)
    if not cuts:
        raise SystemExit("empty worklist — nothing to band")
    unprobed = [n for n, p in probes.items() if p.mem_total_gb <= 0]
    if unprobed:
        raise SystemExit(
            f"no RAM probe for: {', '.join(unprobed)} — fix ssh/probe before suggesting"
        )
    ceil = {name: ceiling_mcut(p, model) for name, p in probes.items()}
    order = sorted(fleet.workers, key=lambda w: ceil[w.name])
    big_limit = round(min(ceil[order[-1].name], cuts[-1] + 1), 1)
    in_band = [c for c in cuts if c <= big_limit]
    costs = [c + COST_FLOOR_M for c in in_band]
    total_cost, total_speed = sum(costs), sum(w.speed for w in order)

    out, lo, cum, j, speed_cum = [], 0.0, 0.0, 0, 0.0
    for k, w in enumerate(order):
        speed_cum += w.speed
        if k == len(order) - 1:
            hi = big_limit
        else:
            # Never advance the cost cursor past this box's RAM ceiling —
            # clamped-off work must count toward the later boxes' targets.
            target = total_cost * speed_cum / total_speed
            cap = ceil[w.name]
            while j < len(in_band) and cum < target and in_band[j] <= cap:
                cum += costs[j]
                j += 1
            hi = round(min(in_band[j - 1] if j else lo, cap), 1)
        if hi <= lo:
            raise SystemExit(
                f"[{w.name}] gets an empty band at [{lo}, {hi}) — its RAM ceiling "
                f"({ceil[w.name]:.0f}M) or speed weight is too small for its slot"
            )
        bins, procs = _bins_and_procs(lo, hi, probes[w.name], model)
        out.append(
            replace(
                w,
                band=(lo, hi),
                bins=bins,
                procs=procs,
                bigs=k == len(order) - 1,
                big_chunk=_big_chunk(probes[w.name], model),
            )
        )
        lo = hi
    return out


def summarize(workers: list[Worker], cuts_m: list[float], model: Model) -> str:
    from pyscripts.fleet.preflight import est_peak_gb

    lines = []
    for w in workers:
        assert w.band is not None
        lo, hi = w.band
        n = sum(lo < c <= hi for c in cuts_m)
        extra = f" (+{sum(c > hi for c in cuts_m)} bigs)" if w.bigs else ""
        lines.append(
            f"  {w.name:12} band ({lo}, {hi}] → {n} trees{extra}, "
            f"est peak {est_peak_gb(w, model):.0f}G"
        )
    return "\n".join(lines)


def render_toml(fleet: Fleet, workers: list[Worker]) -> str:
    model = fleet.model
    lines = [
        "# drafted by `uv run -m pyscripts fleet suggest` — hand-tune freely;",
        "# machine-local and gitignored (docs/deploy.md documents every knob)",
        "",
        "[fleet]",
        f"min_citations = {fleet.min_citations}",
        "",
        "[model]  # UNCALIBRATED defaults unless you measured them",
        f"mem_base_gb = {model.mem_base_gb}",
        f"gb_per_mcut = {model.gb_per_mcut}",
        f"headroom_gb = {model.headroom_gb}",
        f"parts_gb_per_big = {model.parts_gb_per_big}",
    ]
    for w in workers:
        assert w.band is not None
        lines += ["", "[[worker]]", f'name = "{w.name}"']
        if w.host:
            lines += [
                f'host = "{w.host}"',
                f'repo_dir = "{w.repo_dir}"',
                f'data_root = "{w.data_root}"',
            ]
        lines.append(f"band = [{w.band[0]:.1f}, {w.band[1]:.1f}]")
        lines.append(f"bins = [{', '.join(f'{b:.1f}' for b in w.bins)}]")
        lines.append(f"procs = [{', '.join(map(str, w.procs))}]")
        if w.port != DEFAULT_PORT:
            lines.append(f"port = {w.port}")
        if w.speed != 1.0:
            lines.append(f"speed = {w.speed}")
        if w.bigs:
            lines += ["bigs = true", f"big_chunk = {w.big_chunk}"]
    return "\n".join(lines) + "\n"


def worklist_mcuts(min_citations: int) -> list[float]:
    from pyscripts.cache_prompting import BatchRequester

    df = BatchRequester(min_citations=min_citations).urled_sample
    return sorted(df["cut_basis"] / 1e6)


def _bins_and_procs(
    lo: float, hi: float, p: Probe, model: Model
) -> tuple[list[float], list[int]]:
    budget = max(1.0, p.mem_total_gb - model.mem_base_gb - model.headroom_gb)
    cores = p.cores if p.cores > 0 else 4

    def procs_at(m: float) -> int:
        return max(1, min(cores, MAX_PROCS, int(budget // (m * model.gb_per_mcut))))

    interior = sorted({round(e, 1) for e in (hi / 16, hi / 4) if lo < round(e, 1) < hi})
    edges = [*interior, hi]  # each sub-bin's hi drives its parallelism
    per_edge = [procs_at(e) for e in edges]
    bins, procs = [], [per_edge[0]]
    for boundary, pr in zip(edges[:-1], per_edge[1:]):
        if pr != procs[-1]:
            bins.append(boundary)
            procs.append(pr)
    return bins, procs


def _big_chunk(p: Probe, model: Model) -> int:
    if p.tmp_avail_gb <= 0:
        return 1
    return max(1, min(MAX_BIG_CHUNK, int(p.tmp_avail_gb // model.parts_gb_per_big)))
