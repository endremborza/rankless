import json
import subprocess
from pathlib import Path

import pytest
from ccl_science_data.gen import StowC

from pyscripts import snapshot

NOTES = """OPENALEX STANDARD-FORMAT SNAPSHOT RELEASE NOTES

Public releases land on the second Wednesday of January, April, July and October (UTC).

RELEASE 2026-10-14
- quarterly snapshot with bug fixes and improvements

RELEASE 2026-09-23
- quarterly snapshot with bug fixes and improvements
"""


def _release(prefix: Path, date: str, complete: bool) -> Path:
    d = Path(f"{prefix}{date}")
    d.mkdir(parents=True)
    if complete:
        (d / snapshot.COMPLETE_NAME).write_text(f"{date}\n")
    return d


def _entity(snap: Path, entity: str, parts: dict[str, bytes]) -> Path:
    edir = snap / snapshot.JSONL / entity
    files = []
    for rel, body in parts.items():
        part = edir / rel
        part.parent.mkdir(parents=True, exist_ok=True)
        part.write_bytes(body)
        files.append(
            {
                "url": f"{snapshot.BUCKET}/{part.relative_to(snap)}",
                "meta": {"content_length": len(body), "record_count": 1},
            }
        )
    (edir / snapshot.MANIFEST_NAME).write_text(json.dumps({"files": files}))
    return edir


def test_the_newest_release_is_the_latest_date_the_notes_list() -> None:
    assert snapshot.latest_release(NOTES) == "2026-10-14"
    assert snapshot.release_notes(NOTES, "2026-09-23") == (
        "- quarterly snapshot with bug fixes and improvements"
    )


def test_the_pipeline_reads_the_newest_release_once_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = tmp_path / "openalex-snapshot-"
    monkeypatch.delenv(snapshot.SNAPSHOT_VAR, raising=False)
    monkeypatch.setenv(snapshot.PREFIX_VAR, str(prefix))
    _release(prefix, "2026-09-23", complete=True)
    _release(prefix, "2026-06", complete=True)
    newest = _release(prefix, "2026-10-14", complete=False)
    with pytest.raises(SystemExit, match="not complete"):
        snapshot.current()

    (newest / snapshot.COMPLETE_NAME).write_text("2026-10-14\n")
    assert snapshot.current() == newest

    monkeypatch.setenv(snapshot.SNAPSHOT_VAR, str(tmp_path / "mini-snapshot"))
    assert snapshot.current() == tmp_path / "mini-snapshot"


def test_a_part_off_its_manifest_is_a_mismatch(tmp_path: Path) -> None:
    edir = _entity(tmp_path, "fields", {"updated_date=2026-10-14/part_0000.gz": b"ab"})
    assert snapshot.mismatches(tmp_path) == []

    (edir / "updated_date=2026-10-14/part_0000.gz").write_bytes(b"a")
    (edir / "updated_date=2026-10-14/part_0001.gz").write_bytes(b"c")
    assert len(snapshot.mismatches(tmp_path)) == 2


def test_a_complete_release_downloads_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = tmp_path / "openalex-snapshot-"
    monkeypatch.setenv(snapshot.PREFIX_VAR, str(prefix))
    monkeypatch.setattr(snapshot, "_fetch", lambda _: NOTES)
    synced: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **_: synced.append(cmd))
    _release(prefix, "2026-10-14", complete=True)
    snapshot.download()
    assert synced == []


def test_a_download_is_complete_only_once_it_matches_its_manifests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = tmp_path / "openalex-snapshot-"
    target = Path(f"{prefix}2026-10-14")
    monkeypatch.setenv(snapshot.PREFIX_VAR, str(prefix))
    monkeypatch.setattr(snapshot, "_fetch", lambda _: NOTES)
    parts = {"updated_date=2026-10-14/part_0000.gz": b"ab"}

    def torn_sync(cmd: list[str], **_: object) -> None:
        edir = _entity(target, "works", parts)
        (edir / "updated_date=2026-10-14/part_0000.gz").write_bytes(b"a")

    monkeypatch.setattr(subprocess, "run", torn_sync)
    with pytest.raises(SystemExit, match="differs from its manifests"):
        snapshot.download()
    assert not (target / snapshot.COMPLETE_NAME).exists()

    monkeypatch.setattr(subprocess, "run", lambda cmd, **_: None)
    (
        target / snapshot.JSONL / "works/updated_date=2026-10-14/part_0000.gz"
    ).write_bytes(b"ab")
    snapshot.download()
    assert (target / snapshot.COMPLETE_NAME).exists()


def test_the_entity_csvs_name_their_snapshot(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="rerun `make to-csv`"):
        snapshot.recorded(tmp_path)
    (tmp_path / StowC.entity_csvs).mkdir()
    snapshot.record(tmp_path, Path("/x/openalex-snapshot-2026-10-14"))
    assert snapshot.recorded(tmp_path) == {
        "name": "openalex-snapshot-2026-10-14",
        "date": "2026-10-14",
    }
