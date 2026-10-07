from datetime import date
from pathlib import Path

import pytest

from pyscripts.explore import story

CARD = "https://rankless.org/card/authors/a-b/map.png?hl=1"
FINDINGS = [
    {
        "_verified": True,
        "title": "Reach",
        "description": "Cited from 41 countries.",
        "metrics": [
            {"key": "countries", "reproduced": 41, "ok": True},
            {"key": "cites", "reproduced": 6897, "ok": True},
        ],
        "entities": ["https://rankless.org/authors/a-b?since=1950"],
        "images": [CARD],
    },
    {"_verified": False, "title": "Unreproduced", "metrics": []},
]


def test_a_run_ends_with_its_story_and_the_cards_it_shows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    reply = {
        "title": "Where the work went",
        "markdown": f"Since 1950, 6.9k citations from 41 countries, 7 of them new.\n\n![map]({CARD})",
    }
    seen = {}

    def model(system: str, user: str, model: str, **_: object) -> str:
        seen["user"] = user
        return story.json.dumps(reply)

    async def png(url: str) -> bytes:
        return b"png:" + url.encode()

    monkeypatch.setattr(story.cli, "query_claude_cli", model)
    monkeypatch.setattr(story, "fetch_card", png)
    path = story.write(tmp_path, FINDINGS, "2026 Nobel Prize", "m", "abc|full|run-1")
    assert path == tmp_path / "story.md"
    assert "Unreproduced" not in seen["user"]
    assert seen["user"].startswith("Occasion: 2026 Nobel Prize\n")
    [card] = (tmp_path / "cards").iterdir()
    assert card.read_bytes() == b"png:" + CARD.encode()
    assert path.read_text() == (
        "---\n"
        'title: "Where the work went"\n'
        f"date: {date.today().isoformat()}\n"
        'occasion: "2026 Nobel Prize"\n'
        f'run: "{tmp_path.name}"\n'
        'data_version: "abc|full|run-1"\n'
        f'image: "cards/{card.name}"\n'
        'unverified: ["7"]\n'
        "---\n\n"
        "Since 1950, 6.9k citations from 41 countries, 7 of them new.\n\n"
        f"![map](cards/{card.name})\n"
    )


def test_no_story_without_a_reproduced_finding(tmp_path: Path):
    assert story.write(tmp_path, FINDINGS[1:], "", "m", "v") is None
    assert not (tmp_path / "story.md").exists()


def test_empty_front_matter_values_are_left_out():
    meta = {"title": "T", "occasion": "", "unverified": []}
    assert story.render(meta, "Body.\n") == '---\ntitle: "T"\n---\n\nBody.\n'


def test_a_card_whose_url_extends_another_keeps_its_own_file():
    base = "https://rankless.org/card/authors/a-b/tree.png?tree=1&since=2010&isSpec=0"
    branch = f"{base}&paths=5"
    cards = {base: "cards/base.png", branch: "cards/branch.png"}
    assert story._localize(f"![a]({base}) ![b]({branch})", cards) == (
        "![a](cards/base.png) ![b](cards/branch.png)"
    )


def test_a_card_url_with_parentheses_in_its_path_is_taken_whole():
    doi = "https://rankless.org/card/hit-papers/10.1175/1520-0469(1963)020%3C0130/tree.png"
    md = f"![c]({doi}) and (see {doi})."
    assert story.card_urls(md) == [doi]
    assert story._localize(md, {doi: "cards/c.png"}) == (
        "![c](cards/c.png) and (see cards/c.png)."
    )


def test_a_digit_in_a_name_or_a_list_marker_is_not_a_number():
    text = "1. anti-CTLA-4 therapy and IL-2 in 2001-2003, 4 trials"
    assert story.unverified(text, [2001.0]) == ["2003", "4"]


def test_a_link_target_is_not_prose_even_with_brackets_in_it():
    text = (
        "The [1995 review](https://rankless.org/hit-papers/10.1016/0370-1573(95)00058-5), "
        "![card 2 of 3](cards/a-1b2c3d.png) and 7 more."
    )
    assert story.unverified(text, [1995.0]) == ["7"]


def test_unverified_allows_rounding_and_shares_but_not_new_numbers():
    known = [6897, 71800, 3.727, 0.1247, 2003]
    text = (
        "The 2003 paper has 6,897 citations (6.9k), a score of 3.7, "
        "12.5% of links, 72k in total and 13 laureates "
        "https://rankless.org/authors/x2025"
    )
    assert story.unverified(text, known) == ["13"]
