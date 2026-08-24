from pyscripts import object_store


def test_read_entries_tolerates_missing_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_OBJECTS_ROOT", str(tmp_path / "objects"))
    con = object_store.connect(str(tmp_path / "db.sqlite"))
    try:
        obj = {"kind": "game-card", "obj_key": "k1", "payload": {"cc": "HU"}}
        object_store.write_bundle(con, "run-a", [obj])
        object_store.write_bundle(con, "run-b", [{**obj, "obj_key": "k2"}])
        object_store.bundle_path("run-a").unlink()
        entries = object_store.read_entries(object_store.rows(con, "game-card"))
    finally:
        con.close()
    assert entries[0] is None
    assert entries[1] is not None and entries[1]["obj_key"] == "k2"
