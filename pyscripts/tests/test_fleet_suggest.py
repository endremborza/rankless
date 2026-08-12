from pathlib import Path

import pytest

from pyscripts.fleet import calibrate, config
from pyscripts.fleet.calibrate import Probe
from pyscripts.fleet.config import Fleet, Model, Worker

CUTS = sorted(
    [0.5] * 50 + [5.0] * 20 + [20.0] * 10 + [80.0] * 5 + [200.0] * 3 + [500.0, 800.0]
)

PROBES = {
    "local": Probe("local", mem_total_gb=64, cores=16, tmp_avail_gb=30),
    "mid": Probe("mid", mem_total_gb=128, cores=8, tmp_avail_gb=50),
    "big": Probe("big", mem_total_gb=256, cores=8, tmp_avail_gb=100),
}


def _bandless_fleet() -> Fleet:
    return Fleet(
        [
            Worker(name="local"),
            Worker(name="mid", host="mid", repo_dir="/r", data_root="/d", speed=0.6),
            Worker(name="big", host="big", repo_dir="/r", data_root="/d", speed=0.6),
        ]
    )


def test_suggestion_is_a_valid_fleet(tmp_path: Path) -> None:
    fleet = _bandless_fleet()
    workers = calibrate.suggest_workers(fleet, PROBES, CUTS)
    toml = calibrate.render_toml(fleet, workers)
    p = tmp_path / "warm.toml"
    p.write_text(toml)
    loaded = config.load_config(str(p))  # full validation: tiling, arity, bigs
    assert [w.name for w in loaded.workers] == ["local", "mid", "big"]
    assert loaded.model == fleet.model


def test_bands_respect_ram_ceilings() -> None:
    workers = calibrate.suggest_workers(_bandless_fleet(), PROBES, CUTS)
    by_name = {w.name: w for w in workers}
    for name, w in by_name.items():
        assert w.band is not None
        ceiling = calibrate.ceiling_mcut(PROBES[name], Model())
        assert w.band[1] <= ceiling + 0.1
    # bigs duty lands on the highest-ceiling box, which owns the top band
    assert by_name["big"].bigs and not by_name["mid"].bigs
    assert by_name["big"].band[1] == max(w.band[1] for w in workers)  # type: ignore[index]


def test_bands_tile_and_cover_worklist() -> None:
    workers = calibrate.suggest_workers(_bandless_fleet(), PROBES, CUTS)
    bands = sorted(w.band for w in workers)  # type: ignore[arg-type]
    assert bands[0][0] == 0.0
    for (_, hi), (nlo, _) in zip(bands, bands[1:]):
        assert hi == nlo
    top = bands[-1][1]
    n_banded = sum(c <= top for c in CUTS)
    n_bigs = sum(c > top for c in CUTS)
    assert n_banded + n_bigs == len(CUTS)


def test_unprobed_box_refused() -> None:
    probes = {**PROBES, "mid": Probe("mid")}  # ssh failed: all sentinels
    with pytest.raises(SystemExit, match="no RAM probe"):
        calibrate.suggest_workers(_bandless_fleet(), probes, CUTS)


def test_too_small_box_fails_loudly() -> None:
    probes = {**PROBES, "local": Probe("local", mem_total_gb=40, cores=16)}
    with pytest.raises(SystemExit, match="empty band"):
        calibrate.suggest_workers(_bandless_fleet(), probes, CUTS)


def test_bins_and_procs_shape() -> None:
    for w in calibrate.suggest_workers(_bandless_fleet(), PROBES, CUTS):
        assert len(w.procs) == len(w.bins) + 1
        assert w.procs == sorted(w.procs, reverse=True)  # bigger trees, fewer procs
        assert all(1 <= p <= calibrate.MAX_PROCS for p in w.procs)


def test_big_chunk_from_tmp() -> None:
    model = Model()  # 20G parts per big
    assert calibrate._big_chunk(PROBES["big"], model) == 5
    assert calibrate._big_chunk(Probe("x", tmp_avail_gb=500), model) == 8  # capped
    assert calibrate._big_chunk(Probe("x"), model) == 1  # unknown → minimal
