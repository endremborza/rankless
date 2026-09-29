import pytest

from pyscripts import external_data


def test_a_download_lands_in_raw_and_stays_behind_in_a_sync(tmp_path, monkeypatch):
    local, far = tmp_path / "local", tmp_path / "far"
    monkeypatch.setenv(external_data.ROOT_VAR, str(local))
    origin = tmp_path / "origin.csv"
    origin.write_text("a\n1\n")
    got = external_data.fetched("src", "t.csv", origin.as_uri())
    assert got == local / "src" / external_data.RAW / "t.csv"
    (external_data.source_dir("src") / "table.tsv").write_text("made here\n")

    external_data.sync("push", str(far))

    assert (far / "src" / "table.tsv").read_text() == "made here\n"
    assert not (far / "src" / external_data.RAW).exists()


def test_a_named_root_requires_its_tables(tmp_path, monkeypatch):
    monkeypatch.setenv(external_data.ROOT_VAR, str(tmp_path))
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "t.csv").write_text("x\n")
    assert external_data.table("src", "t.csv") == tmp_path / "src" / "t.csv"
    with pytest.raises(FileNotFoundError):
        external_data.table("src", "missing.csv")
    monkeypatch.delenv(external_data.ROOT_VAR)
    monkeypatch.chdir(tmp_path)
    assert external_data.table("src", "missing.csv") is None
