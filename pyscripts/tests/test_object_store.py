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


def test_export_ingest_roundtrip_keeps_review_status(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_OBJECTS_ROOT", str(tmp_path / "objects"))
    src_db, dst_db = str(tmp_path / "src.sqlite"), str(tmp_path / "dst.sqlite")
    con = object_store.connect(src_db)
    try:
        object_store.write_bundle(
            con,
            "run-a",
            [
                {"kind": "game-card", "obj_key": "k1", "payload": {"cc": "HU"}},
                {"kind": "game-card", "obj_key": "k2", "payload": {"cc": "SK"}},
            ],
        )
        ids = [r["id"] for r in object_store.rows(con, "game-card")]
    finally:
        con.close()
    object_store.set_status(ids=str(ids[1]), status="rejected", note="dup", db=src_db)

    dump = str(tmp_path / "dump.jsonl")
    object_store.export(path=dump, db=src_db)
    object_store.ingest(path=dump, run="run-a", db=dst_db)

    con = object_store.connect(dst_db)
    try:
        got = {
            r["obj_key"]: (r["status"], r["status_note"])
            for r in object_store.rows(con, "game-card")
        }
    finally:
        con.close()
    assert got == {"k1": ("new", None), "k2": ("rejected", "dup")}
