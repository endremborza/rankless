import re

from mcp_server import SITE_URL, card_url, composite_url, entity_url
from mcp_server.tools import _impact_highlights, get_impact_highlights


def _paper(
    wid: int, year: int, citations: int, score: float, authors: list[str]
) -> dict:
    return {
        "wid": wid,
        "oaId": wid * 10,
        "year": year,
        "name": f"paper {wid}",
        "doi": "",
        "citations": citations,
        "score": score,
        "isHit": True,
        "hitSemId": f"10.1/{wid}",
        "source": 7,
        "authorships": [{"author": a, "insts": []} for a in authors],
    }


PROFILE = {
    "highlights": [
        {
            "wid": 2,
            "cites": [10],
            "badges": [
                {"kind": "hit", "multiple": 9.0, "rarity": 0.01},
                {"kind": "apex", "source": 7, "rank": 2, "rarity": 0.05},
                {
                    "kind": "institution",
                    "institution": 3,
                    "country": 2,
                    "papers": 12,
                    "rank": 1,
                    "rarity": 0.2,
                },
            ],
        },
        {
            "wid": 1,
            "cites": [10, 11],
            "badges": [
                {"kind": "laureate", "author": 5, "rarity": 0.06},
                {"kind": "star", "author": 6, "field": 8, "ratio": 1.5, "rarity": 0.1},
            ],
        },
    ],
    "totals": {
        "citingPapers": 40,
        "independent": 30,
        "hits": 2,
        "apex": 1,
        "laureates": 1,
        "stars": 1,
        "institutions": 1,
    },
    "papers": {
        "papers": [
            _paper(1, 2012, 900, 2.0, ["F5", "F6", "D9"]),
            _paper(2, 2015, 400, 3.0, ["F6"]),
            _paper(10, 2003, 700, 1.5, ["F4"]),
            {**_paper(11, 1995, 50, 0.4, ["F4"]), "isHit": False, "hitSemId": None},
        ],
        "entityAtts": {
            "authors": {
                "4": {"name": "Subject", "semantic_id": "subject"},
                "5": {"name": "Laureate", "semantic_id": "laureate"},
                "6": {"name": "Star", "semantic_id": "star"},
            },
            "sources": {"7": {"name": "Journal"}},
            "institutions": {"3": {"name": "Institute", "semantic_id": "inst"}},
            "countries": {"2": {"name": "Country", "semantic_id": "country"}},
            "subfields": {"8": {"name": "Field", "semantic_id": "field"}},
        },
        "discAuthorNames": {"D9": "Gone"},
        "authorsMeta": {
            "4": {"prize": 0, "year": 0},
            "5": {"prize": 3, "year": 2018},
            "6": {"prize": 0, "year": 0},
        },
    },
}


def test_highlights_keep_their_order_and_name_every_id():
    out = _impact_highlights(PROFILE, "subject")
    hit, laureate = out["highlights"]
    assert hit["name"] == "paper 2"
    assert hit["journal"] == "Journal"
    assert hit["rankless_url"] == entity_url("hit-papers", "10.1/2")
    assert hit["badges"][1] == {
        "kind": "apex",
        "journal": "Journal",
        "rank": 2,
        "rarity": 0.05,
    }
    assert hit["badges"][2] == {
        "kind": "institution",
        "name": "Institute",
        "rankless_url": entity_url("institutions", "inst"),
        "country": "Country",
        "papers": 12,
        "rank": 1,
        "rarity": 0.2,
    }
    assert [c["name"] for c in laureate["cites"]] == ["paper 10", "paper 11"]
    assert laureate["cites"][1]["openalex_url"] == "https://openalex.org/W110"
    assert laureate["badges"] == [
        {
            "kind": "laureate",
            "name": "Laureate",
            "prize": "Physiology or Medicine",
            "year": 2018,
            "rankless_url": entity_url("authors", "laureate"),
            "rarity": 0.06,
        },
        {
            "kind": "star",
            "name": "Star",
            "rankless_url": entity_url("authors", "star"),
            "field": "Field",
            "ratio": 1.5,
            "rarity": 0.1,
        },
    ]
    assert out["totals"] == PROFILE["totals"]


def test_a_hit_paper_highlight_links_its_own_card():
    hit, _ = _impact_highlights(PROFILE, "subject")["highlights"]
    assert hit["image_url"] == card_url(
        "impact", "authors", "subject", {"hits": "10.1/2"}
    )


def test_a_page_and_its_card_carry_the_same_view():
    view = {"tree": 2, "since": 2010}
    assert entity_url("hit-papers", "10.1/2", view).endswith(
        "/hit-papers/10.1/2?tree=2&since=2010"
    )
    assert card_url("tree", "hit-papers", "10.1/2", view).endswith(
        "/card/hit-papers/10.1/2/tree.png?tree=2&since=2010"
    )
    assert card_url(
        "table", "authors", "", {"sort": "h_index", "where": None}
    ).endswith("/card/authors/table.png?sort=h_index")


def test_a_composite_names_each_card_by_its_path_and_variant():
    cards = [
        f"{SITE_URL}/card/authors/a-b/map.png?hl=1",
        f"{SITE_URL}/card/authors/a-b/tree.png",
    ]
    assert composite_url(cards) == (
        f"{SITE_URL}/card/composite.png"
        "?p=authors%2Fa-b%2Fmap%3Fhl%3D1&p=authors%2Fa-b%2Ftree"
    )


def test_impact_highlights_description_names_only_what_its_rows_carry():
    out = _impact_highlights(PROFILE, "subject")
    rows = [
        *out["highlights"],
        *(b for h in out["highlights"] for b in h["badges"]),
    ]
    keys = set(out) | set(out["totals"]) | {k for row in rows for k in row}
    tags = {row.get("kind") for row in rows}
    named = set(re.findall(r"`(\w+)`", get_impact_highlights.__doc__ or ""))
    assert named <= keys | tags, named - keys - tags
    assert "{" not in (get_impact_highlights.__doc__ or "")
