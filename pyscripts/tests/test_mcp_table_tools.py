import asyncio

import httpx
import pytest

from mcp_server import tools

REGISTRY = {
    "metrics": [
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
}

CALLS: list[tuple[str, dict]] = []


async def fake_get_with_headers(path: str, params: dict | None = None):
    CALLS.append((path, {k: v for k, v in (params or {}).items() if v is not None}))
    rows = [
        {
            "name": "A",
            "semanticId": "a",
            "dmId": 5,
            "oaId": 1,
            "rank": 1,
            "papers": 3,
            "values": {"impact_score": 1.5, "field_score(oncology)": 2.5},
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
    ]
    return rows, httpx.Headers(
        {
            "x-cohort-total": "42",
            "x-screened-k": "2",
            "x-columns": "impact_score,field_score(oncology)",
        }
    )


async def fake_get_json(path: str, params: dict | None = None):
    CALLS.append((path, {k: v for k, v in (params or {}).items() if v is not None}))
    if path.startswith("/slice/"):
        return [
            {"name": "A", "semanticId": "a", "dmId": 5, "oaId": 1},
            {"name": "B", "semanticId": "b", "dmId": 9, "oaId": 2},
        ]
    return {"ids": [9], "values": {"field_score(oncology)": [1.5]}}


@pytest.fixture(autouse=True)
def _fake_backend(monkeypatch: pytest.MonkeyPatch):
    CALLS.clear()
    monkeypatch.setattr(tools, "get_with_headers", fake_get_with_headers)
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
    assert out["columns"] == ["impact_score", "field_score(oncology)"]
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
    assert "field_score(subfield) [score]: Citations from the field over size." in rank
    assert "global for institutions; per-entity for authors" in rank
    assert "window_papers(from, to) [count]" in rank
    assert (
        "cited_from(country) [share]: Share of citations from the country. A walk, for authors."
        in rank
    )
    assert "country [entities of countries]" in rank
    assert "`where` expression" in rank
    annotate = tools.annotate_entities.__doc__ or ""
    assert "cited_from(country)" in annotate and "For authors." in annotate
    assert "citations [count]" not in annotate
