from pathlib import Path

import pytest

from pyscripts import country_authors as ca

FILE = f"""# header kept verbatim
5000000001 Someone Who Asked

# the country block
{ca.MARKER}
5000000002 Hungary
5000000003 Palau
# cleared 5000000004 Monaco — Italian gastroenterology
"""


def _write(tmp_path: Path) -> Path:
    path = tmp_path / "author_blacklist.txt"
    path.write_text(FILE)
    return path


def test_round_trip_leaves_the_file_untouched(tmp_path: Path) -> None:
    path = _write(tmp_path)
    listed, cleared, head = ca._parse(path)
    assert listed == {5000000002: "Hungary", 5000000003: "Palau"}
    assert cleared == {5000000004: "Monaco — Italian gastroenterology"}
    assert head[0] == "# header kept verbatim"
    assert head[1] == "5000000001 Someone Who Asked"
    ca._write(path, listed, cleared)
    assert path.read_text() == FILE


def test_verdicts_land_sorted_by_name(tmp_path: Path) -> None:
    path = _write(tmp_path)
    listed, cleared, _ = ca._parse(path)
    listed[5000000005] = "Kenya"
    cleared[5000000006] = "Hong Kong — Korean animal genetics"
    ca._write(path, listed, cleared)
    lines = path.read_text().splitlines()
    assert lines[lines.index(ca.MARKER) + 1 :] == [
        "5000000002 Hungary",
        "5000000005 Kenya",
        "5000000003 Palau",
        "# cleared 5000000006 Hong Kong — Korean animal genetics",
        "# cleared 5000000004 Monaco — Italian gastroenterology",
    ]
    # the head ids stay out of both verdict sets, so they are never re-proposed
    assert 5000000001 not in ca._parse(path)[0]


def test_a_file_without_the_marker_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "author_blacklist.txt"
    path.write_text("5000000001 Someone Who Asked\n")
    with pytest.raises(SystemExit):
        ca._parse(path)


def test_scan_separates_absent_renamed_and_undecided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    path = _write(tmp_path)
    rows = {
        5000000003: ca.Record("Palau Jr", "", 5, 50),
        5000000007: ca.Record("Kenya", "0000-0001", 9, 90),
    }
    monkeypatch.setattr(ca, "_country_names", lambda: {"hungary", "palau", "kenya"})
    monkeypatch.setattr(ca, "_match", lambda names, watch: rows)
    monkeypatch.setattr(ca, "_in_app", lambda matched: matched)
    with pytest.raises(SystemExit):
        ca.scan(blacklist=str(path))
    out = capsys.readouterr().out
    assert "absent from this snapshot: 5000000002 Hungary" in out
    assert "no longer a country name: 5000000003" in out
    assert "5000000007 Kenya (works 9, cites 90) 0000-0001" in out
    assert "in the snapshot, 1 in the app" in out
