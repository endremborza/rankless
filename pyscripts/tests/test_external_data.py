import pytest

from pyscripts import external_data


def test_a_download_lands_in_raw_and_stays_behind_in_a_sync(tmp_path, monkeypatch):
    local, far = tmp_path / "local", tmp_path / "far"
    monkeypatch.setenv(external_data.EXTERNAL_REGEN_ROOT, str(local))
    origin = tmp_path / "origin.csv"
    origin.write_text("a\n1\n")
    got = external_data.fetched("src", "t.csv", origin.as_uri())
    assert got == local / "src" / external_data.RAW / "t.csv"
    (external_data.REGEN.source_dir("src") / "table.tsv").write_text("made here\n")

    external_data.sync("push", external_data.REGEN, str(far))

    assert (far / "src" / "table.tsv").read_text() == "made here\n"
    assert not (far / "src" / external_data.RAW).exists()


def test_a_named_root_requires_its_tables(tmp_path, monkeypatch):
    kept = external_data.KEPT
    monkeypatch.setenv(kept.var, str(tmp_path))
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "t.csv").write_text("x\n")
    assert kept.table("src", "t.csv") == tmp_path / "src" / "t.csv"
    with pytest.raises(FileNotFoundError):
        kept.table("src", "missing.csv")
    monkeypatch.delenv(kept.var)
    monkeypatch.chdir(tmp_path)
    assert kept.table("src", "missing.csv") is None


def test_a_sync_refuses_before_touching_either_root(tmp_path, monkeypatch):
    for root in external_data.ROOTS:
        monkeypatch.setenv(root.var, str(tmp_path / root.var))
        monkeypatch.setenv(root.remote_var, str(tmp_path / "far" / root.var))
    monkeypatch.delenv(external_data.REGEN.remote_var)
    monkeypatch.setattr("sys.argv", ["external_data", "push"])
    with pytest.raises(SystemExit, match=external_data.REGEN.remote_var):
        external_data.main()
    assert not (tmp_path / "far").exists()
