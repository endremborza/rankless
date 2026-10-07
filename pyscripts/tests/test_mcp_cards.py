import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

import mcp_server
from mcp_server import card_url, cards, tools
from pyscripts.tests.test_mcp_impact_dag import PROFILE
from pyscripts.tests.test_mcp_table_tools import REGISTRY, fake_get_json
from wire.rankless_server.responses import METHODOLOGY

COAUTHORS = [{"semanticId": "c-d", "count": 1}, {"semanticId": "e-f", "count": 3}]


def test_make_card_describes_every_kind_and_parameter_of_the_contract() -> None:
    doc = cards.make_card.__doc__ or ""
    for kind, spec in cards.KINDS.items():
        line = next(ln for ln in doc.splitlines() if ln.strip().startswith(f"- {kind}"))
        assert all(f"{name} (" in line for name in spec["params"])
    timeline = next(ln for ln in doc.splitlines() if "- timeline" in ln)
    assert "[authors]" in timeline and "first|recent|count" in timeline
    assert f"max {cards.KINDS['timeline']['params']['n']['max']}" in timeline


def test_make_card_refuses_a_kind_the_type_lacks_before_fetching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_fetch(*_args, **_kwargs):
        raise AssertionError("fetched")

    monkeypatch.setattr(httpx, "AsyncClient", no_fetch)
    with pytest.raises(ValueError, match="no papers card for 'institutions'"):
        asyncio.run(cards.make_card("papers", "institutions", "mit"))
    with pytest.raises(ValueError, match="kind must be one of"):
        asyncio.run(cards.make_card("constructor", "authors", "a-b"))


def test_a_profile_links_only_the_cards_its_own_data_proves() -> None:
    view = {"relations": {"paper-authors": COAUTHORS}}
    proven = cards.profile_cards("authors", "a-b", view)
    assert list(proven) == ["yearly", "map", "fields", "network", "timeline"]
    assert proven["map"] == card_url("map", "authors", "a-b")
    one_paper_each = {"relations": {"paper-authors": [COAUTHORS[0], COAUTHORS[0]]}}
    assert list(cards.profile_cards("authors", "a-b", one_paper_each)) == [
        "yearly",
        "map",
        "fields",
        "network",
    ]
    assert list(cards.profile_cards("authors", "a-b", {"relations": {}})) == [
        "yearly",
        "map",
        "fields",
    ]
    assert list(cards.profile_cards("institutions", "mit", view)) == [
        "yearly",
        "map",
        "fields",
    ]


def test_impact_links_its_card_only_with_a_citing_hit() -> None:
    assert tools._impact_dag(PROFILE, "subject")["image_url"] == card_url(
        "impact", "authors", "subject"
    )
    uncited = {**PROFILE, "dag": {"Node": {}}}
    assert "image_url" not in tools._impact_dag(uncited, "subject")


def _works(papers: list[dict]):
    async def get_json(_path: str, _params: dict | None = None):
        return {"resp": {"papers": papers}}

    return get_json


def test_papers_link_the_hit_paper_card_from_an_author_hit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hit, plain = PROFILE["papers"]["papers"][2:]
    monkeypatch.setattr(tools, "get_json", _works([hit, plain]))
    out = asyncio.run(tools.get_papers("authors", "subject"))
    assert out["image_url"] == card_url("papers", "authors", "subject")
    assert out["papers"][0]["image_url"] == card_url(
        "papers", "authors", "subject", {"hl": hit["hitSemId"]}
    )
    assert "image_url" not in out["papers"][1]
    assert "image_url" not in asyncio.run(tools.get_papers("institutions", "mit"))
    monkeypatch.setattr(tools, "get_json", _works([plain]))
    assert "image_url" not in asyncio.run(tools.get_papers("authors", "subject"))


def test_peers_link_their_card_only_with_a_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_peers(_path: str, _params: dict | None = None):
        return {"peers": []}

    monkeypatch.setattr(tools, "get_json", no_peers)
    assert "image_url" not in asyncio.run(tools.get_peers("authors", "a-b"))


def test_a_ranking_card_starts_at_the_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tools, "get_json", fake_get_json)
    out = asyncio.run(tools.rank_entities("authors", sort="citations", offset=50))
    assert out["image_url"] == card_url(
        "table", "authors", "", {"sort": "citations", "from": 50}
    )
    first = asyncio.run(tools.rank_entities("authors", sort="citations"))
    assert first["image_url"] == card_url("table", "authors", "", {"sort": "citations"})


def test_annotations_link_a_table_card_only_when_it_holds_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tools, "get_json", fake_get_json)
    tools.describe(REGISTRY)
    call = "field_score(oncology)"
    out = asyncio.run(tools.annotate_entities("authors", ["a", "b"], [call]))
    assert out["image_url"] == card_url(
        "table", "authors", "", {"pin": "a,b", "cols": call}
    )
    pins = cards.KINDS["table"]["params"]["pin"]["max"]
    crowded = [f"a-{i}" for i in range(pins + 1)]
    assert "image_url" not in asyncio.run(
        tools.annotate_entities("authors", crowded, [call])
    )
    assert "image_url" not in asyncio.run(
        tools.annotate_entities("authors", ["a"], ["country"])
    )


def test_the_mcp_page_describes_the_tools_from_the_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pyscripts import build_mcp_manifest

    served = {"/columns": REGISTRY}
    monkeypatch.setattr(build_mcp_manifest, "fetch", served.__getitem__)
    monkeypatch.setattr(build_mcp_manifest, "OUT_PATH", tmp_path / "manifest.json")
    monkeypatch.setattr(mcp_server, "BE_URL", mcp_server.BE_URL)
    monkeypatch.setattr(sys, "argv", ["build_mcp_manifest"])
    assert build_mcp_manifest.main() == 0
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    docs = {t["name"]: t["description"] for t in manifest["tools"]}
    assert docs["make_card"] and docs["rank_entities"] and docs["annotate_entities"]
    era = "{}..{}".format(*METHODOLOGY["yearlyCounts"])
    assert era in docs["get_entity_profile"]
    assert any(era in r["text"] for r in manifest["resources"])


def test_papers_clamp_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict = {}

    async def get_json(_path: str, params: dict) -> dict:
        sent.update(params)
        return {"resp": {"papers": []}}

    monkeypatch.setattr(tools, "get_json", get_json)
    asyncio.run(tools.get_papers("authors", "subject", limit=400))
    assert sent["n"] == tools.MAX_PAPERS_LIMIT
