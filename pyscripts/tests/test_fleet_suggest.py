import math
from pathlib import Path

import pytest

from pyscripts.fleet import calibrate, config
from pyscripts.fleet.calibrate import Probe
from pyscripts.fleet.config import Fleet, Model, Worker

CUTS = sorted(
    [0.5] * 50 + [5.0] * 20 + [20.0] * 10 + [80.0] * 5 + [200.0] * 3 + [500.0, 800.0]
)

PROBES = {
    "local": Probe("local", mem_total_gb=64, cores=16),
    "mid": Probe("mid", mem_total_gb=128, cores=8),
    "big": Probe("big", mem_total_gb=256, cores=8),
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
    loaded = config.load_config(str(p))  # full validation: tiling, arity, open top
    assert [w.name for w in loaded.workers] == ["local", "mid", "big"]
    assert loaded.model == fleet.model


def test_bands_respect_ram_ceilings() -> None:
    workers = calibrate.suggest_workers(_bandless_fleet(), PROBES, CUTS)
    by_name = {w.name: w for w in workers}
    for name in ("local", "mid"):
        band = by_name[name].band
        assert band is not None
        assert band[1] <= calibrate.ceiling_mcut(PROBES[name], Model()) + 0.1
    # the open top band lands on the highest-ceiling box, its last bin one tree at a time
    top = by_name["big"]
    assert top.band is not None and top.band[1] == math.inf and top.procs[-1] == 1


def test_bands_tile_and_cover_worklist() -> None:
    workers = calibrate.suggest_workers(_bandless_fleet(), PROBES, CUTS)
    bands = sorted(w.band for w in workers)  # type: ignore[arg-type]
    assert bands[0][0] == 0.0
    for (_, hi), (nlo, _) in zip(bands, bands[1:]):
        assert hi == nlo
    assert bands[-1][1] == math.inf


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
