from pathlib import Path

import pytest

from pyscripts.cache_prompting import tree_cached
from pyscripts.fleet import drive, preflight
from pyscripts.fleet.config import Fleet, Worker
from pyscripts.fleet.preflight import Check, Primary

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


class _StampHost:
    def __init__(self, stamp: str):
        self.stamp = stamp
        self.cmds: list[str] = []

    def out(self, cmd: str, check: bool = True) -> str:
        self.cmds.append(cmd)
        return self.stamp if cmd.startswith("cat") else ""


def test_stale_worker_cache_wiped_on_stamp_change() -> None:
    w = Worker(name="w", host="box", repo_dir="/r", data_root="/d")
    primary = Primary(
        head="h",
        rankless_env="full",
        oa_root="/p",
        stamp="2026-08-13T11:25:57Z:16310bb25271",
        digest="16310bb25271",
        data_size_gb=1.0,
    )
    stale = _StampHost("2026-07-10T21:56:32Z:5ce8249b5f50")
    drive._invalidate_stale_cache(w, stale, primary)
    assert any(c.startswith("rm -rf") and "/d/cache" in c for c in stale.cmds)

    current = _StampHost(primary.stamp)
    drive._invalidate_stale_cache(w, current, primary)
    assert not any(c.startswith("rm") for c in current.cmds)


def test_prepare_converges_and_gates_without_compute(monkeypatch) -> None:
    calls: list[object] = []
    monkeypatch.setattr(drive, "load_config", lambda c: Fleet(_workers()))
    monkeypatch.setattr(
        drive, "_prepare_gate", lambda ws, f, push: calls.append(("gate", push))
    )
    monkeypatch.setattr(drive, "_compute", lambda *a: calls.append("compute"))
    monkeypatch.setattr(drive, "coverage_gate", lambda *a: calls.append("coverage"))
    drive.prepare("cfg", push=False)
    assert calls == [("gate", False)]


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
