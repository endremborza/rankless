import json
from pathlib import Path

import pytest

from pyscripts import release_report as rr


def _record(run_id: str, works: int, authors: int, applied: dict, events: int) -> dict:
    return {
        "run_id": run_id,
        "stamp": f"{run_id}:aaaaaaaaaaaa",
        "git_commit": "cafe00000000",
        "rankless_env": "mini",
        "snapshot": {"name": f"snap-{run_id[:7]}", "date": run_id[:7]},
        "ledger": {"site": events},
        "filter_counts": {
            "10": {"works": {"in": None, "kept": works + 20}},
            "11": {"works": {"in": works + 20, "kept": works}},
            "20": {"authors": {"in": None, "kept": authors}},
        },
        "applied": applied,
        "skipped": {"oa_id_not_in_dataset": 2},
    }


PREV = _record("2026-07-01T00:00:00Z", 80, 7, {"disown_paper": 3, "merge_papers": 1}, 4)
CUR = _record(
    "2026-08-13T11:25:57Z",
    90,
    9,
    {"disown_paper": 5, "merge_papers": 1, "merge_authors": 1},
    7,
)
CUR["forced_works"] = {
    "cohort": 3,
    "forced_total": 40,
    "outside_standard": 12,
    "outside_type": 9,
    "outside_citations": 5,
    "claim_auto": 1,
    "claim_merged": 0,
    "author_rescues": 1,
}


def test_report_without_previous() -> None:
    report = rr.build_report(CUR)
    assert report["previous"] is None and report["deltas"] is None
    assert report["restored"] == CUR["forced_works"]
    # a record predating forced-works sidecars renders without the section
    assert rr.build_report(PREV)["restored"] is None

    assert list(report["entities"]) == ["works", "authors"]
    works = report["entities"]["works"]
    assert works["final"] == 90
    assert [s["kept"] for s in works["steps"]] == [110, 90]
    assert works["steps"][1]["label"] == rr.STEP_LABELS[("11", "works")]

    ledger = report["ledger"]
    assert ledger == {
        "sources": 1,
        "events": 7,
        "applied": CUR["applied"],
        "applied_total": 7,
        "skipped": {"oa_id_not_in_dataset": 2},
        "skipped_total": 2,
    }
    # feed names never appear publicly
    assert "site" not in json.dumps(report)


def test_report_deltas() -> None:
    report = rr.build_report(CUR, PREV)
    assert report["previous"]["run_id"] == PREV["run_id"]

    deltas = report["deltas"]
    assert deltas["entities"]["works"] == {"previous": 80, "current": 90, "change": 10}
    assert deltas["applied"]["merge_authors"] == {"previous": 0, "current": 1, "new": 1}
    assert deltas["applied"]["merge_papers"]["new"] == 0
    assert deltas["applied_total"] == {"previous": 4, "current": 7, "new": 3}


def test_render_md() -> None:
    md = rr.render_md(rr.build_report(CUR, PREV))
    assert "data release 2026-08-13" in md
    assert "90" in md and "7 correction(s) integrated" in md
    assert "Papers restored by their authors: 12" in md
    assert "+3 newly integrated" in md
    assert "site" not in md


def _seed_releases(root: Path, *records: dict) -> None:
    rdir = root / "releases"
    rdir.mkdir()
    for rec in records:
        (rdir / f"{rec['run_id']}.json").write_text(json.dumps(rec))
    (rdir / "release.json").write_text(json.dumps(records[-1]))


def test_asset_and_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_releases(tmp_path, PREV, CUR)
    asset = tmp_path / "release-report.json"
    monkeypatch.setattr(rr, "ASSET_PATH", asset)

    assert rr.write_report_asset(tmp_path) == asset
    report = json.loads(asset.read_text())
    assert report["run_id"] == CUR["run_id"]
    assert report["deltas"]["entities"]["works"]["change"] == 10

    served = f"cafe00000000|mini|{CUR['stamp']}"
    assert rr.assert_report_documents(served, asset)["run_id"] == CUR["run_id"]
    with pytest.raises(SystemExit, match="not the reported release"):
        rr.assert_report_documents(f"cafe00000000|mini|{PREV['stamp']}", asset)
    with pytest.raises(SystemExit, match="no release report asset"):
        rr.assert_report_documents(served, tmp_path / "missing.json")


def test_asset_warn_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    asset = tmp_path / "release-report.json"
    monkeypatch.setattr(rr, "ASSET_PATH", asset)
    assert rr.write_report_asset(tmp_path, warn_missing=True) is None
    assert not asset.exists()
