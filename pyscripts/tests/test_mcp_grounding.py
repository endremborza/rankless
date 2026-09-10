import asyncio
import json
from pathlib import Path

import pytest

from mcp_server import receipts, verify
from mcp_server.grounding import Claim, verify_claims
from mcp_server.response_shaping import coauthor_edges
from mcp_server.server import transport_security

CALLS: list[dict] = []


async def fake_stats(entity_type: str, semantic_id: str, year_from: int = 2016) -> dict:
    CALLS.append({"entity_type": entity_type, "semantic_id": semantic_id})
    return {"windowPapers": 42, "topSubfields": [{"citations": 7}]}


@pytest.fixture(autouse=True)
def _fresh_session(monkeypatch: pytest.MonkeyPatch):
    receipts._logs.clear()
    CALLS.clear()
    monkeypatch.setitem(verify.TOOL_FNS, "fake_stats", fake_stats)


def test_with_receipt_wraps_and_records() -> None:
    wrapped = receipts.with_receipt(fake_stats)
    out = asyncio.run(wrapped("authors", "x", ctx=None))
    assert out["data"]["windowPapers"] == 42
    assert out["receipt"] == {
        "id": "r1",
        "tool": "fake_stats",
        "args": {"entity_type": "authors", "semantic_id": "x"},
    }
    assert receipts.session_log("stdio").resolve("r1") == out["receipt"]
    assert "ctx" not in receipts.session_log("stdio").resolve("r1")["args"]


def test_with_receipt_logs_a_failing_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(receipts, "LOG_DIR", str(tmp_path))

    async def boom(x: int) -> dict:
        raise ValueError("nope")

    with pytest.raises(ValueError):
        asyncio.run(receipts.with_receipt(boom)(1, ctx=None))
    (line,) = [
        json.loads(ln)
        for p in tmp_path.glob("*.jsonl")
        for ln in p.read_text().splitlines()
    ]
    assert (line["kind"], line["tool"], line["error"]) == (
        "call",
        "boom",
        "ValueError: nope",
    )


def test_verify_claims_by_receipt_and_by_call() -> None:
    receipts.session_log("stdio").record(
        "fake_stats", {"entity_type": "a", "semantic_id": "x"}
    )
    claims = [
        Claim(label="papers", claimed=42, path="data.windowPapers", receipt="r1"),
        Claim(label="cites", claimed=8, path="topSubfields[0].citations", receipt="r1"),
        Claim(label="missing", claimed=1, path="windowPapers", receipt="r9"),
        Claim(
            label="direct",
            claimed=42,
            path="windowPapers",
            tool="fake_stats",
            args={"entity_type": "a", "semantic_id": "x"},
        ),
        Claim(label="unsourced", claimed=1, path="windowPapers"),
        Claim(label="valueless", claimed=None, path="windowPapers", receipt="r1"),
    ]
    res = asyncio.run(verify_claims(claims, None))
    by_label = {c["label"]: c for c in res["claims"]}
    assert by_label["papers"]["ok"] and by_label["papers"]["reproduced"] == 42
    assert not by_label["cites"]["ok"] and by_label["cites"]["reproduced"] == 7
    assert "no receipt 'r9'" in by_label["missing"]["error"]
    assert by_label["direct"]["ok"]
    assert "names a receipt or a tool" in by_label["unsourced"]["error"]
    assert "states the value" in by_label["valueless"]["error"]
    assert (res["verified"], res["failed"]) == (2, 4)
    assert CALLS == [{"entity_type": "a", "semantic_id": "x"}]


def test_data_path_strips_envelope_prefix() -> None:
    assert verify.data_path("data.windowPapers") == "windowPapers"
    assert verify.data_path("data[0].papers") == "[0].papers"
    assert verify.data_path("data") == ""
    assert verify.data_path("database.x") == "database.x"
    assert verify.walk([{"papers": 3}], "[0].papers") == 3


def test_transport_security_hosts() -> None:
    assert transport_security("") is None
    settings = transport_security("api.example.org, alpha-api.example.org")
    assert settings is not None
    assert settings.allowed_hosts[:2] == ["api.example.org", "alpha-api.example.org"]
    assert "https://api.example.org" in settings.allowed_origins
    assert "127.0.0.1:*" in settings.allowed_hosts


def test_coauthor_edges_upper_triangle() -> None:
    view = {
        "relations": {
            "paper-authors": [
                {"name": "A", "semanticId": "a"},
                {"name": "B", "semanticId": "b"},
                {"name": "C", "semanticId": "c"},
            ]
        },
        "authorNetwork": [5, 0, 2],
    }
    assert coauthor_edges(view) == [
        {"pair": ["A", "B"], "ids": ["a", "b"], "sharedPapers": 5},
        {"pair": ["B", "C"], "ids": ["b", "c"], "sharedPapers": 2},
    ]
