from pathlib import Path

import pytest

from pyscripts.fleet import config

CONF = """
[fleet]
min_citations = 50000

[[worker]]
name = "local"
band = [0.0, 14.0]
bins = [6.0]
procs = [16, 8]

[[worker]]
name = "mid-box"
host = "mid-box"
repo_dir = "/home/x/rankless"
data_root = "/home/x/rankless-data"
band = [14.0, 160.0]
bins = [48.0]
procs = [4, 1]
speed = 0.6

[[worker]]
name = "big-box"
host = "big-box"
repo_dir = "/home/x/rankless"
data_root = "/home/x/rankless-data"
band = [160.0, 320.0]
procs = [2]
bigs = true
big_chunk = 3
"""


def _load(tmp_path: Path, text: str, **kwargs) -> config.Fleet:
    p = tmp_path / "warm.toml"
    p.write_text(text)
    return config.load_config(str(p), **kwargs)


def test_load_and_cache_flags(tmp_path: Path) -> None:
    fleet = _load(tmp_path, CONF)
    assert fleet.min_citations == 50000
    local, mid, big = fleet.workers
    assert local.host is None and fleet.local() is local
    assert fleet.bigs_worker() is big and fleet.big_limit() == 320.0
    assert local.cache_flags(fleet.min_citations) == [
        "--min=0.0",
        "--limit=14.0",
        "--bins=6.0",
        "--procs=16,8",
        "--chunk=4",
        "--min-citations=50000",
    ]
    assert big.actions() == ["bigs", "rest"] and mid.actions() == ["rest"]
    assert "--bins=" in big.cache_flags(50000)  # single-bin band → empty list
    assert "--chunk=3" in big.cache_flags(50000)


def test_cache_flags_roundtrip(tmp_path: Path) -> None:
    # The flags a worker emits must parse back through the cache CLI unchanged.
    from protocli import _build_parser

    from pyscripts import cache_prompting

    parser = _build_parser("cache", cache_prompting.main)
    fleet = _load(tmp_path, CONF)
    local, _, big = fleet.workers

    args = parser.parse_args(["rest", *local.cache_flags(fleet.min_citations)])
    assert (args.min, args.limit) == local.band
    assert args.bins == local.bins and args.procs == local.procs
    assert args.min_citations == fleet.min_citations

    args = parser.parse_args(["bigs", *big.cache_flags(fleet.min_citations)])
    assert args.bins == [] and args.procs == [2] and args.chunk == 3


def test_fleet_section_optional(tmp_path: Path) -> None:
    no_fleet = "\n".join(CONF.splitlines()[4:])
    fleet = _load(tmp_path, no_fleet)
    assert fleet.min_citations == config.DEFAULT_MIN_CITATIONS


def test_model_overrides(tmp_path: Path) -> None:
    assert _load(tmp_path, CONF).model == config.Model()
    tuned = CONF + "\n[model]\ngb_per_mcut = 0.5\n"
    model = _load(tmp_path, tuned).model
    assert model.gb_per_mcut == 0.5
    assert model.mem_base_gb == config.Model().mem_base_gb


def test_structural_validation(tmp_path: Path) -> None:
    bad_procs = CONF.replace("procs = [16, 8]", "procs = [16]")
    with pytest.raises(SystemExit, match="procs"):
        _load(tmp_path, bad_procs)
    two_local = CONF.replace('host = "mid-box"\n', "")
    with pytest.raises(SystemExit, match="local"):
        _load(tmp_path, two_local)
    dup_names = CONF.replace('name = "mid-box"', 'name = "local"')
    with pytest.raises(SystemExit, match="unique"):
        _load(tmp_path, dup_names)


@pytest.mark.parametrize(
    ("mangle", "match"),
    [
        (("band = [14.0, 160.0]", "band = [15.0, 160.0]"), "gap"),
        (("band = [14.0, 160.0]", "band = [12.0, 160.0]"), "overlap"),
        (("band = [0.0, 14.0]", "band = [1.0, 14.0]"), "start at 0"),
        (("bigs = true\n", ""), "exactly one"),
        (("speed = 0.6", "bigs = true"), "exactly one"),
        (
            (
                "band = [160.0, 320.0]\nprocs = [2]",
                "band = [160.0, 320.0]\nbins = [400.0]\nprocs = [2, 1]",
            ),
            "inside the band",
        ),
    ],
)
def test_tiling_validation(tmp_path: Path, mangle: tuple, match: str) -> None:
    with pytest.raises(SystemExit, match=match):
        _load(tmp_path, CONF.replace(*mangle))


def test_bigs_must_own_top_band(tmp_path: Path) -> None:
    swapped = CONF.replace(
        "procs = [4, 1]\nspeed = 0.6", "procs = [4, 1]\nbigs = true"
    ).replace("procs = [2]\nbigs = true\nbig_chunk = 3", "procs = [2]")
    with pytest.raises(SystemExit, match="top band"):
        _load(tmp_path, swapped)


def test_bands_optional_for_calibration(tmp_path: Path) -> None:
    bandless = "\n".join(
        line
        for line in CONF.splitlines()
        if not line.startswith(("band", "bins", "procs"))
    )
    fleet = _load(tmp_path, bandless, require_bands=False)
    assert [w.band for w in fleet.workers] == [None] * 3
    with pytest.raises(SystemExit, match="suggest"):
        _load(tmp_path, bandless)
