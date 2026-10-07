from mcp_server import SITE_URL, card_url, composite_url, entity_url
from mcp_server.tools import _impact_dag


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
    "dag": {
        "Node": {
            "1": {"Node": {"10": "Leaf", "11": "Leaf"}},
            "2": {"Node": {"10": "Leaf"}},
        }
    },
    "papers": {
        "papers": [
            _paper(1, 2012, 900, 2.0, ["F5", "D9"]),
            _paper(2, 2015, 400, 3.0, ["F6"]),
            _paper(10, 2003, 700, 1.5, ["F4"]),
            {**_paper(11, 1995, 50, 0.4, ["F4"]), "isHit": False, "hitSemId": None},
        ],
        "entityAtts": {
            "authors": {
                "4": {"name": "Subject", "semantic_id": "subject"},
                "5": {"name": "Laureate", "semantic_id": "laureate"},
                "6": {"name": "Other", "semantic_id": "other"},
            },
            "sources": {"7": {"name": "Journal"}},
        },
        "discAuthorNames": {"D9": "Gone"},
        "authorsMeta": {
            "4": {"prize": 0, "year": 0},
            "5": {"prize": 3, "year": 2018},
            "6": {"prize": 0, "year": 0},
        },
    },
}


def test_impact_dag_lists_each_citing_hit_with_its_laureates_and_cited_papers():
    out = _impact_dag(PROFILE, "subject")
    hits, cited = out["citingHits"], out["authorPapers"]
    assert [h["name"] for h in hits] == ["paper 2", "paper 1"]
    assert [c["name"] for c in cited] == ["paper 10", "paper 11"]
    assert hits[1]["laureates"] == [
        {
            "name": "Laureate",
            "prize": "Physiology or Medicine",
            "year": 2018,
            "rankless_url": entity_url("authors", "laureate"),
        }
    ]
    assert hits[0]["laureates"] == []
    assert [[cited[i]["name"] for i in h["cites"]] for h in hits] == [
        ["paper 10"],
        ["paper 10", "paper 11"],
    ]
    assert [c["citedByHits"] for c in cited] == [2, 1]
    assert hits[0]["rankless_url"] == entity_url("hit-papers", "10.1/2")
    assert cited[1]["openalex_url"] == "https://openalex.org/W110"


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
