from pathlib import Path

import pytest

from pyscripts.cache_prompting import tree_cached
from pyscripts.fleet import drive, preflight
from pyscripts.fleet.config import Fleet, Worker
from pyscripts.fleet.preflight import Check

N_PERIODS = 12


def _workers() -> list[Worker]:
    return [
        Worker(name="ok"),
        Worker(name="dead", host="dead-box", repo_dir="/r", data_root="/d"),
    ]


def test_phase_failure_becomes_gate_row() -> None:
    def fn(w: Worker) -> list[Check]:
        if w.name == "dead":
            raise RuntimeError("rsync exploded")
        return [Check(w.name, "version", True, "")]

    results = drive._phase(
        _workers(),
        fn,
        on_error=lambda w, e: [Check(w.name, "prepare", False, str(e))],
    )
    rows = [c for cs in results.values() for c in cs]  # iterable for every worker
    assert {(c.worker, c.name, c.ok) for c in rows} == {
        ("ok", "version", True),
        ("dead", "prepare", False),
    }
    with pytest.raises(SystemExit, match="dead/prepare"):
        preflight.gate(rows)


def test_phase_default_keeps_exception_as_result() -> None:
    def fn(w: Worker) -> None:
        if w.name == "dead":
            raise RuntimeError("compute died")

    results = drive._phase(_workers(), fn)
    assert results["ok"] is None
    assert isinstance(results["dead"], RuntimeError)


def test_select_unknown_worker() -> None:
    fleet = Fleet(_workers())
    assert drive._select(fleet, None) == fleet.workers
    assert [w.name for w in drive._select(fleet, "ok")] == ["ok"]
    with pytest.raises(SystemExit, match="no worker named"):
        drive._select(fleet, "ghost")


def test_tree_cached_rejects_torn_dir(tmp_path: Path) -> None:
    s = {"rt": "authors", "dmId": 7, "tid": 0}
    d = tmp_path / "cache" / "authors" / "7" / "0"
    assert not tree_cached(s, N_PERIODS, str(tmp_path))  # no dir at all

    d.mkdir(parents=True)
    for pid in range(4):  # kill mid-read: only the newest periods landed
        (d / f"{pid}.zst").touch()
        (d / f"wide-{pid}.zst").touch()
    assert not tree_cached(s, N_PERIODS, str(tmp_path))

    for pid in range(4, N_PERIODS):
        (d / f"{pid}.zst").touch()
    (d / "shallow1-0.zst").touch()  # conditional variants never count
    assert tree_cached(s, N_PERIODS, str(tmp_path))
