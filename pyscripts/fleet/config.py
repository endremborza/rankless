"""Fleet config: data/warm.toml parsing + every statically checkable invariant.

The config is machine-local and gitignored (example in docs/deploy.md). Bands
are (lo, hi] in millions of cut_basis (citations × breakdown count) — pd.cut
right-inclusive, so a tree exactly on a boundary belongs to the lower band and
`bigs` (strictly above the top hi) tiles exactly. Static validation catches at
load time what used to surface hours in at the coverage gate: bands must tile
(0, big_limit] with no gap or overlap, and exactly one worker owns the top
band with `bigs = true` (it computes everything above it via chunked
prep→read).
"""

import tomllib
from dataclasses import dataclass, field

from pyscripts.fleet.remote import Host

DEFAULT_CONFIG = "data/warm.toml"
DEFAULT_MIN_CITATIONS = 100_000
DEFAULT_BIG_CHUNK = 4
DEFAULT_PORT = 3038


@dataclass(frozen=True)
class Model:
    """Resource model shared by `fleet suggest` and the preflight gate.

    UNCALIBRATED defaults — tune via [model] in warm.toml once a real run's
    systemd MemoryPeak per band is in (see docs/deploy.md).
    """

    mem_base_gb: float = 37.0  # backend startup baseline (full env)
    # implied by the historical hand-tuned bands (128G-class box ↔ ~320M top)
    gb_per_mcut: float = 0.25  # peak compute GB per M cut_basis per in-flight tree
    headroom_gb: float = 8.0  # OS + page cache + safety margin
    parts_gb_per_big: float = 20.0  # /tmp/dmove-parts footprint per prepped big


@dataclass
class Worker:
    name: str
    host: str | None = None  # None → this machine
    repo_dir: str = ""
    data_root: str = ""
    band: tuple[float, float] | None = None
    bins: list[float] = field(default_factory=list)
    procs: list[int] = field(default_factory=list)
    bigs: bool = False
    big_chunk: int = DEFAULT_BIG_CHUNK
    port: int = DEFAULT_PORT
    speed: float = 1.0  # relative single-tree throughput, weighs `fleet suggest`

    def __post_init__(self):
        if self.host and not (self.repo_dir and self.data_root):
            raise SystemExit(f"[{self.name}] remote workers need repo_dir + data_root")

    def conn(self) -> Host:
        return Host(self.name, self.host)

    def validate_banded(self) -> None:
        if self.band is None or not self.procs:
            raise SystemExit(
                f"[{self.name}] has no band/procs — run `fleet suggest` to draft them"
            )
        if len(self.procs) != len(self.bins) + 1:
            raise SystemExit(f"[{self.name}] needs len(procs) == len(bins) + 1")
        lo, hi = self.band
        if not lo < hi:
            raise SystemExit(f"[{self.name}] band must be (lo, hi] with lo < hi")
        if any(not lo < b < hi for b in self.bins):
            raise SystemExit(f"[{self.name}] bins must lie strictly inside the band")

    def cache_flags(self, min_citations: int) -> list[str]:
        assert self.band is not None
        lo, hi = self.band
        return [
            f"--min={lo}",
            f"--limit={hi}",
            f"--bins={','.join(map(str, self.bins))}",
            f"--procs={','.join(map(str, self.procs))}",
            f"--chunk={self.big_chunk}",
            f"--min-citations={min_citations}",
        ]

    def actions(self) -> list[str]:
        return (["bigs"] if self.bigs else []) + ["rest"]

    def bin_edges(self) -> list[tuple[float, int]]:
        """(bin hi, procs) pairs — the unit of the memory model."""
        assert self.band is not None
        his = [*self.bins, self.band[1]]
        return list(zip(his, self.procs))


@dataclass
class Fleet:
    workers: list[Worker]
    # Warm worklist floor (citations). Fleet-level: every worker and the
    # coverage gate must sample the same worklist.
    min_citations: int = DEFAULT_MIN_CITATIONS
    model: Model = field(default_factory=Model)

    def local(self) -> Worker | None:
        return next((w for w in self.workers if w.host is None), None)

    def bigs_worker(self) -> Worker:
        return next(w for w in self.workers if w.bigs)

    def big_limit(self) -> float:
        band = self.bigs_worker().band
        assert band is not None
        return band[1]


def load_config(path: str, require_bands: bool = True) -> Fleet:
    try:
        f = open(path, "rb")
    except FileNotFoundError:
        raise SystemExit(
            f"no fleet config at {path} — it is machine-local (gitignored); "
            "copy the example from docs/deploy.md and tune the bands to this box"
        )
    with f:
        raw = tomllib.load(f)
    workers = [_worker(w) for w in raw.get("worker", [])]
    if not workers:
        raise SystemExit(f"no [[worker]] entries in {path}")
    if sum(w.host is None for w in workers) > 1:
        raise SystemExit("at most one local worker (omit `host` for this machine)")
    if len({w.name for w in workers}) != len(workers):
        raise SystemExit("worker names must be unique")
    try:
        fleet = Fleet(
            workers,
            model=Model(**raw.get("model", {})),
            **raw.get("fleet", {}),
        )
    except TypeError as e:
        raise SystemExit(f"bad [fleet]/[model] key in {path}: {e}")
    if require_bands:
        for w in workers:
            w.validate_banded()
        _check_tiling(workers)
    return fleet


def _worker(raw: dict) -> Worker:
    name = raw.get("name", "?")
    band = raw.get("band")
    if band is not None and (
        len(band) != 2 or not all(isinstance(b, (int, float)) for b in band)
    ):
        raise SystemExit(f"[{name}] band must be [lo, hi]")
    try:
        return Worker(**{**raw, "band": tuple(band) if band else None})
    except TypeError as e:
        raise SystemExit(f"bad [[worker]] key on {name}: {e}")


def _check_tiling(workers: list[Worker]) -> None:
    bands = sorted((w.band, w.name) for w in workers)  # type: ignore[arg-type]
    (lo0, _), _ = bands[0]
    if lo0 != 0:
        raise SystemExit(f"lowest band starts at {lo0}, must start at 0")
    for ((_, hi), name), ((nlo, _), nname) in zip(bands, bands[1:]):
        if hi < nlo:
            raise SystemExit(f"band gap between {name} and {nname}: ({hi}, {nlo}]")
        if hi > nlo:
            raise SystemExit(f"bands of {name} and {nname} overlap at ({nlo}, {hi}]")
    bigs = [w for w in workers if w.bigs]
    if len(bigs) != 1:
        raise SystemExit(
            f"exactly one worker must set bigs = true (found {len(bigs)}) — "
            "it owns everything above the top band"
        )
    top_hi = bands[-1][0][1]
    assert bigs[0].band is not None
    if bigs[0].band[1] != top_hi:
        raise SystemExit(
            f"the bigs worker ({bigs[0].name}) must own the top band: its hi "
            f"{bigs[0].band[1]} != fleet top {top_hi}, so trees in between would "
            "be computed twice"
        )
