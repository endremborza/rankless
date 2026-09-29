from mcp_server import card_url, entity_url
from mcp_server.tools import _impact_dag
from pyscripts.explore.posts import unverified


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
    assert card_url("hit-papers", "10.1/2", view).endswith(
        "/pic/hit-papers/10.1/2/breakdown.png?tree=2&since=2010"
    )


def test_unverified_allows_rounding_and_shares_but_not_new_numbers():
    known = [6897, 71800, 3.727, 0.1247, 2003]
    text = (
        "The 2003 paper has 6,897 citations (6.9k), a score of 3.7, "
        "12.5% of links, 72k in total and 13 laureates; 1/5 "
        "https://rankless.org/authors/x2025"
    )
    assert unverified(text, known) == ["13"]
