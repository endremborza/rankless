import json

import pytest

from pyscripts import disclaimers


@pytest.fixture
def box(tmp_path, monkeypatch):
    """A box serving run `r1` whose backend knows one author."""
    ledger = tmp_path / "user-ledger"
    ledger.mkdir()
    manifest = ledger / "applied_manifest.json"
    manifest.write_text(json.dumps({"run_id": "r1"}))
    monkeypatch.setenv("OA_ROOT", str(tmp_path))

    def name(root_type, semantic_id):
        if (root_type, semantic_id) != ("authors", "a-b"):
            raise SystemExit("no such profile")
        return "A B"

    monkeypatch.setattr(disclaimers, "profile_name", name)
    return str(tmp_path / "db.sqlite"), manifest


def test_add_stamps_the_served_run_and_replaces(box):
    db, _ = box
    disclaimers.add(root_type="authors", semantic_id="a-b", text=" first ", db=db)
    disclaimers.add(root_type="authors", semantic_id="a-b", text="second", db=db)
    assert disclaimers.rows(db) == [("authors", "a-b", "r1", "second")]


def test_a_new_run_leaves_the_row_lapsed(box, capsys):
    db, manifest = box
    disclaimers.add(root_type="authors", semantic_id="a-b", text="note", db=db)
    manifest.write_text(json.dumps({"run_id": "r2"}))
    capsys.readouterr()
    disclaimers._list_cmd(db=db)
    assert capsys.readouterr().out.startswith("lapsed authors/a-b [r1]")


def test_add_refuses_what_would_never_show(box):
    db, _ = box
    with pytest.raises(SystemExit):
        disclaimers.add(root_type="papers", semantic_id="a-b", text="note", db=db)
    with pytest.raises(SystemExit):
        disclaimers.add(root_type="authors", semantic_id="a-c", text="note", db=db)
    with pytest.raises(SystemExit):
        disclaimers.add(root_type="authors", semantic_id="a-b", text="  ", db=db)
    assert disclaimers.rows(db) == []


def test_remove_fails_on_a_profile_without_a_note(box):
    db, _ = box
    disclaimers.add(root_type="authors", semantic_id="a-b", text="note", db=db)
    disclaimers.remove(root_type="authors", semantic_id="a-b", db=db)
    with pytest.raises(SystemExit):
        disclaimers.remove(root_type="authors", semantic_id="a-b", db=db)
