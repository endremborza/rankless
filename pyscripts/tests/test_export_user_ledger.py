import json
import sqlite3

from pyscripts import export_user_ledger, external_data, paths
from wire.rankless_rs.user_ledger import CURATED_JSONL, SNAPSHOT_MANIFEST

CURATED_LINE = {
    "key": "0000-0002-9865-121X|merge_authors|h",
    "orcid": "0000-0002-9865-121X",
    "kind": "merge_authors",
    "source": "curated",
    "payload": {
        "kind": "merge_authors",
        "keep": {"oa_id": 1},
        "drop": {"oa_id": 2},
    },
}


def _export(tmp_path) -> tuple:
    db = tmp_path / "site.sqlite"
    sqlite3.connect(db).close()
    data_root = tmp_path / "data"
    export_user_ledger.export(data_root, str(db))
    out = data_root / paths.USER_LEDGER_DIR
    return out, json.loads((out / SNAPSHOT_MANIFEST).read_text())


def test_the_curated_ledger_is_exported_beside_the_site_events(tmp_path, monkeypatch):
    root = tmp_path / "external"
    (root / "ledger").mkdir(parents=True)
    (root / "ledger" / CURATED_JSONL).write_text(json.dumps(CURATED_LINE) + "\n\n")
    monkeypatch.setenv(external_data.EXTERNAL_DATA_ROOT, str(root))

    out, manifest = _export(tmp_path)

    lines = (out / CURATED_JSONL).read_text().splitlines()
    assert [json.loads(line) for line in lines] == [CURATED_LINE]
    assert manifest["sources"] == {"site": 0, "curated": 1}


def test_without_a_curated_ledger_under_the_default_root_none_is_left(
    tmp_path, monkeypatch
):
    monkeypatch.delenv(external_data.EXTERNAL_DATA_ROOT, raising=False)
    monkeypatch.chdir(tmp_path)
    stale = tmp_path / "data" / paths.USER_LEDGER_DIR / CURATED_JSONL
    stale.parent.mkdir(parents=True)
    stale.write_text(json.dumps(CURATED_LINE) + "\n")

    out, manifest = _export(tmp_path)

    assert not (out / CURATED_JSONL).exists()
    assert manifest["sources"] == {"site": 0}
