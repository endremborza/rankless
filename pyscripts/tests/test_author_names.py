import pytest

from pyscripts.author_names import flags


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("ALBERTO E ARANEDA", ["caps"]),
        ("J. SAKATA", ["caps"]),
        ("Dr Sandhya Pundhir", ["title"]),
        ("Prof.Dr. Kemal Nas", ["title"]),
        ("DR KUMAR", ["caps"]),
        ("MR Grever", []),
        ("DR L Azoulay", []),
        ("J. K.", []),
        ("王伟", []),
        ("Ricardo O. Barra", []),
    ],
)
def test_capitals_and_titles_are_flagged_but_capital_blocks_are_initials(
    name: str, expected: list[str]
) -> None:
    assert flags(name) == expected
