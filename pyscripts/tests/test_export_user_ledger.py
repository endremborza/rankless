import json
import sqlite3

import pytest

from pyscripts import export_user_ledger, external_data, paths
from pyscripts.export_user_ledger import CURATED_DIR
from wire.rankless_rs.user_ledger import CURATED_JSONL, SNAPSHOT_MANIFEST


def _line(key: str) -> dict:
    return {
        "key": key,
        "orcid": "0000-0002-9865-121X",
        "kind": "merge_authors",
        "source": "curated",
        "payload": {
            "kind": "merge_authors",
            "keep": {"oa_id": 1},
            "drop": {"oa_id": 2},
        },
    }


def _ledger(tmp_path, monkeypatch, files: dict[str, list[dict]]):
    root = tmp_path / "external"
    occasions = root / "ledger" / CURATED_DIR
    occasions.mkdir(parents=True)
    for name, lines in files.items():
        (occasions / name).write_text("".join(json.dumps(x) + "\n\n" for x in lines))
    monkeypatch.setenv(external_data.EXTERNAL_DATA_ROOT, str(root))
    return root


def _export(tmp_path) -> tuple:
    db = tmp_path / "site.sqlite"
    sqlite3.connect(db).close()
    data_root = tmp_path / "data"
    export_user_ledger.export(data_root, str(db))
    out = data_root / paths.USER_LEDGER_DIR
    return out, json.loads((out / SNAPSHOT_MANIFEST).read_text())


def test_the_occasion_files_are_exported_in_name_order_beside_the_site_events(
    tmp_path, monkeypatch
):
    a, b, c = _line("k|merge_authors|a"), _line("k|merge_authors|b"), _line("k|m|c")
    root = _ledger(
        tmp_path, monkeypatch, {"2026-10-07-y.jsonl": [c], "2026-09-29-x.jsonl": [a, b]}
    )
    pending = root / "ledger" / "pending"
    pending.mkdir()
    (pending / "2026-10-12-z.jsonl").write_text(json.dumps(_line("k|m|z")) + "\n")

    out, manifest = _export(tmp_path)

    lines = (out / CURATED_JSONL).read_text().splitlines()
    assert [json.loads(line) for line in lines] == [a, b, c]
    assert manifest["sources"] == {"site": 0, "curated": 3}
    assert manifest["curated_files"] == {
        "2026-09-29-x.jsonl": 2,
        "2026-10-07-y.jsonl": 1,
    }


def test_an_event_key_on_two_lines_stops_the_export(tmp_path, monkeypatch):
    twice = _line("k|merge_authors|a")
    _ledger(tmp_path, monkeypatch, {"a.jsonl": [twice], "b.jsonl": [twice]})

    with pytest.raises(SystemExit, match="a.jsonl', 'b.jsonl"):
        _export(tmp_path)


def test_without_a_curated_ledger_under_the_default_root_none_is_left(
    tmp_path, monkeypatch
):
    monkeypatch.delenv(external_data.EXTERNAL_DATA_ROOT, raising=False)
    monkeypatch.chdir(tmp_path)
    stale = tmp_path / "data" / paths.USER_LEDGER_DIR / CURATED_JSONL
    stale.parent.mkdir(parents=True)
    stale.write_text(json.dumps(_line("k|merge_authors|a")) + "\n")

    out, manifest = _export(tmp_path)

    assert not (out / CURATED_JSONL).exists()
    assert manifest["sources"] == {"site": 0}
    assert manifest["curated_files"] == {}
