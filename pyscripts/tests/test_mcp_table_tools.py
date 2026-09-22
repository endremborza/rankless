import asyncio

import pytest

from mcp_server import tools

DECLS = [
    {
        "id": "citations",
        "label": "Citations",
        "meaning": "Citations received.",
        "value": {"type": "count"},
        "cost": "read",
        "kinds": {"authors": "global", "institutions": "global"},
    },
    {
        "id": "field_score",
        "label": "Field score",
        "header": "{subfield} score",
        "meaning": "Citations from the field over size.",
        "value": {"type": "score"},
        "param": "subfield",
        "cost": "read",
        "kinds": {"authors": "intricate", "institutions": "global"},
    },
    {
        "id": "window_papers",
        "label": "Papers in a year window",
        "header": "Papers {window}",
        "meaning": "Papers in the window.",
        "value": {"type": "count"},
        "param": "window",
        "cost": "read",
        "kinds": {"authors": "global"},
    },
    {
        "id": "cited_from",
        "label": "Share cited from a country",
        "header": "Cited from {country}",
        "meaning": "Share of citations from the country.",
        "value": {"type": "share"},
        "param": "country",
        "cost": "walk",
        "kinds": {"authors": "intricate"},
    },
    {
        "id": "country",
        "label": "Country",
        "meaning": "The country.",
        "value": {"type": "entities", "entity": "countries"},
        "cost": "read",
        "kinds": {"authors": "global", "institutions": "global"},
    },
]
DEFAULT_SORTS = {"authors": "weighted_paper_score", "institutions": "citations"}


def root_registry(root: str) -> dict:
    metrics = [
        {**{k: v for k, v in d.items() if k != "kinds"}, "kind": d["kinds"][root]}
        for d in DECLS
        if root in d["kinds"]
    ]
    return {"defaultSort": DEFAULT_SORTS[root], "metrics": metrics}


REGISTRY = {"roots": {root: root_registry(root) for root in DEFAULT_SORTS}}

CALLS: list[tuple[str, dict]] = []


async def fake_get_json(path: str, params: dict | None = None):
    CALLS.append((path, {k: v for k, v in (params or {}).items() if v is not None}))
    if not path.startswith("/slice/"):
        return {"ids": [9], "values": {"field_score(oncology)": [1.5]}}
    return {
        "rows": [
            {
                "name": "A",
                "semanticId": "a",
                "dmId": 5,
                "oaId": 1,
                "rank": 1,
                "papers": 3,
                "values": {"top_mean": 1.5, "field_score(oncology)": 2.5},
            },
            {
                "name": "B",
                "semanticId": "b",
                "dmId": 9,
                "oaId": 2,
                "rank": 2,
                "papers": 2,
                "values": {},
            },
        ],
        "meta": {
            "total": 42,
            "screened": 2,
            "columns": ["top_mean", "field_score(oncology)"],
        },
    }


@pytest.fixture(autouse=True)
def _fake_backend(monkeypatch: pytest.MonkeyPatch):
    CALLS.clear()
    monkeypatch.setattr(tools, "get_json", fake_get_json)


def test_rank_entities_passes_the_expressions_and_reads_the_counts() -> None:
    where = "country = hun and papers >= 100"
    out = asyncio.run(
        tools.rank_entities(
            "institutions", sort="field_score(oncology)", where=where, limit=500
        )
    )
    path, params = CALLS[0]
    assert path == "/slice/institutions/0/100"
    assert params == {"sort": "field_score(oncology)", "where": where}
    assert (out["total"], out["screened"], out["sort"]) == (
        42,
        2,
        "field_score(oncology)",
    )
    assert out["columns"] == ["top_mean", "field_score(oncology)"]
    assert [r["semanticId"] for r in out["rows"]] == ["a", "b"]
    row = out["rows"][0]
    assert (
        row["field_score(oncology)"] == 2.5
        and "values" not in row
        and "dmId" not in row
    )
    # The site's table reads the very keys the backend took: one query vocabulary.
    assert out["rankless_url"] == (
        "https://rankless.org/institutions/table"
        "?sort=field_score%28oncology%29&where=country+%3D+hun+and+papers+%3E%3D+100"
    )


def test_rank_entities_without_a_sort_takes_the_types_default() -> None:
    tools.describe(REGISTRY)
    out = asyncio.run(tools.rank_entities("authors"))
    assert CALLS[0][1] == {"sort": "weighted_paper_score"}
    assert out["sort"] == "weighted_paper_score"


def test_annotate_entities_resolves_names_then_aligns_values() -> None:
    out = asyncio.run(
        tools.annotate_entities("authors", ["a", "b"], ["field_score(oncology)"])
    )
    assert CALLS[0] == ("/slice/authors/0/0", {"pin": "a,b"})
    assert CALLS[1] == (
        "/metrics/authors",
        {"ids": "5,9", "metrics": "field_score(oncology)"},
    )
    by_id = {e["semanticId"]: e for e in out["entities"]}
    assert by_id["b"]["field_score(oncology)"] == 1.5
    assert by_id["a"]["field_score(oncology)"] is None
    assert out["metrics"] == ["field_score(oncology)"]
    with pytest.raises(ValueError):
        asyncio.run(tools.annotate_entities("authors", [], ["field_score(oncology)"]))


def test_descriptions_are_built_from_the_registry() -> None:
    tools.describe(REGISTRY)
    rank = tools.rank_entities.__doc__ or ""
    authors, institutions = rank.split("\ninstitutions:\n")
    field = "field_score(subfield) [score]: Citations from the field over size."
    assert f"{field} Per-entity." in authors and f"{field} Global." in institutions
    assert "window_papers(from, to) [count]" in authors
    assert "window_papers" not in institutions
    assert (
        "cited_from(country) [share]: Share of citations from the country. A walk."
        in authors
    )
    assert "authors by weighted_paper_score, institutions by citations" in rank
    assert "country [entities of countries]" in rank
    assert "`where` expression" in rank
    annotate = tools.annotate_entities.__doc__ or ""
    assert "cited_from(country)" in annotate
    assert "citations [count]" not in annotate
