import json
import os
from pathlib import Path

from pyscripts.fleet import manifest
from pyscripts.fleet.remote import Host

LOCAL = Host("t", None)


def _fill(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


BASE = {"a1/names": "abc", "derive_links1/x/sizes": "123", "top.bin": "zz"}


def test_digest_stable_and_metadata_only(tmp_path: Path) -> None:
    r1, r2 = tmp_path / "r1", tmp_path / "r2"
    _fill(r1, BASE)
    _fill(r2, BASE)
    os.utime(r2 / "top.bin", (0, 0))  # mtimes deliberately not part of it
    d1, d2 = manifest.digest(LOCAL, str(r1)), manifest.digest(LOCAL, str(r2))
    assert d1 == d2 and len(d1) == 64


def test_digest_sees_size_and_set_changes(tmp_path: Path) -> None:
    r1, r2, r3 = tmp_path / "r1", tmp_path / "r2", tmp_path / "r3"
    _fill(r1, BASE)
    _fill(r2, {**BASE, "top.bin": "zzzz"})  # size change = torn transfer
    _fill(r3, {**BASE, "derive_links1/extra": "?"})  # leftover stale file
    base = manifest.digest(LOCAL, str(r1))
    assert manifest.digest(LOCAL, str(r2)) != base
    assert manifest.digest(LOCAL, str(r3)) != base


def test_digest_ignores_per_box_state(tmp_path: Path) -> None:
    r1, r2 = tmp_path / "r1", tmp_path / "r2"
    _fill(r1, BASE)
    _fill(r2, {**BASE, "cache/authors/1/0/f": "resp", "search-cache/q": "x"})
    (r2 / manifest.STAMP_NAME).write_text("run:abc\n")
    assert manifest.digest(LOCAL, str(r1)) == manifest.digest(LOCAL, str(r2))


def test_stamp_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / "r"
    _fill(root, BASE)
    line = manifest.write_stamp(str(root), "run-7")
    assert manifest.read_stamp(LOCAL, str(root)) == line
    assert line.startswith("run-7:")
    dig = manifest.stamp_digest(line)
    assert manifest.digest(LOCAL, str(root)).startswith(dig)
    # stamping again over identical data is a no-op line
    assert manifest.write_stamp(str(root), "run-7") == line
    assert manifest.read_stamp(LOCAL, str(tmp_path / "absent")) == ""


def test_run_id(tmp_path: Path) -> None:
    assert manifest.run_id(None).count("-") == 2  # date fallback
    led = tmp_path / "user-ledger"
    led.mkdir()
    (led / "snapshot_manifest.json").write_text(json.dumps({"run_id": "r42"}))
    assert manifest.run_id(str(tmp_path)) == "r42"
