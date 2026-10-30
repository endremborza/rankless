from pathlib import Path

import httpx
import pytest

import mcp_server
from pyscripts import outreach
from pyscripts.outreach import (
    PLACEHOLDER,
    SITE,
    SOURCE_SENTENCES,
    Content,
    Recipient,
    SendLog,
)

ROW = Recipient("a-b", "a@b.org", "corresponding")


def content(**over) -> Content:
    base = dict(
        name="A B",
        profile=f"{SITE}/authors/a-b",
        login=f"{SITE}/login",
        tree_card=f"{SITE}/card/authors/a-b/tree.png",
        countries=["Chile"],
        map_card=f"{SITE}/card/authors/a-b/map.png",
        peers=["C D"],
        peers_card=f"{SITE}/card/authors/a-b/peers.png",
        coauthors=["E F"],
        network_card=None,
    )
    return Content(**{**base, **over})


def batch(tmp_path, *lines: str):
    path = tmp_path / "b1.tsv"
    path.write_text("\n".join(["semantic_id\temail\tsource", *lines]) + "\n")
    return path


def sendable(tmp_path, monkeypatch) -> tuple[str, Path]:
    monkeypatch.setattr(
        outreach, "fetch_contents", lambda rows, *_: [content() for _ in rows]
    )

    async def none_broken(urls: list[str]) -> list[str]:
        return []

    monkeypatch.setattr(outreach, "_broken_cards", none_broken)
    monkeypatch.setattr(outreach.time, "sleep", lambda _: None)
    return str(batch(tmp_path, "a-b\ta@b.org\tcorresponding")), tmp_path / "sent.sqlite"


def test_a_message_that_never_left_keeps_no_claim(tmp_path, monkeypatch):
    path, log = sendable(tmp_path, monkeypatch)

    def signed_out(self) -> str:
        raise SystemExit("no sign-in kept")

    monkeypatch.setattr(outreach.GraphToken, "bearer", signed_out)
    with pytest.raises(SystemExit, match="no sign-in"):
        outreach.send(path, log=str(log))
    assert not SendLog(log).has(ROW)

    def unreachable(*_, **__) -> httpx.Response:
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(outreach.GraphToken, "bearer", lambda self: "token")
    monkeypatch.setattr(outreach.httpx, "post", unreachable)
    with pytest.raises(SystemExit, match="unreachable"):
        outreach.send(path, log=str(log))
    assert not SendLog(log).has(ROW)


def test_the_send_log_claims_a_pair_once(tmp_path):
    log = SendLog(tmp_path / "sent.sqlite")
    assert log.claim(ROW, "b1")
    assert not log.claim(ROW, "b2")
    assert log.has(ROW) and log.sent_within(outreach.DAY_HOURS) == 1
    log.release(ROW)
    assert log.claim(ROW, "b2")


def test_a_dry_run_leaves_no_log(tmp_path):
    path = tmp_path / "sent.sqlite"
    assert not SendLog(path, dry_run=True).has(ROW)
    assert not path.exists()


def test_the_footer_names_each_source():
    for source, sentence in SOURCE_SENTENCES.items():
        msg = outreach.message(content(), Recipient("a-b", "a@b.org", source))
        text = msg.get_body(("plain",)).get_content()
        assert sentence in text
        assert sentence in msg.get_body(("html",)).get_content()
    assert PLACEHOLDER not in SOURCE_SENTENCES["corresponding"]


def test_a_missing_card_drops_its_section():
    text = outreach.to_text(outreach.letter(content(map_card=None), "corresponding"))
    assert "Chile" not in text and "C D" in text and "E F" not in text


def test_send_refuses_an_unworded_source_before_any_fetch(tmp_path, monkeypatch):
    unworded = [s for s, t in SOURCE_SENTENCES.items() if PLACEHOLDER in t]
    if not unworded:
        pytest.skip("every source is worded")
    monkeypatch.setattr(outreach, "fetch_contents", lambda *_: pytest.fail("fetched"))
    path = batch(tmp_path, f"a-b\ta@b.org\t{unworded[0]}")
    with pytest.raises(SystemExit, match="still"):
        outreach.send(str(path), log=str(tmp_path / "sent.sqlite"))


def test_read_batch_normalizes_and_rejects(tmp_path):
    assert outreach.read_batch(batch(tmp_path, "a-b\t A@B.org \tcorresponding")) == [
        ROW
    ]
    with pytest.raises(SystemExit, match="source"):
        outreach.read_batch(batch(tmp_path, "a-b\ta@b.org\tscraped"))
    with pytest.raises(SystemExit, match="repeats"):
        outreach.read_batch(
            batch(tmp_path, "a-b\ta@b.org\tcorresponding", "a-b\tA@b.org\torcid")
        )


def test_links_move_to_the_canonical_host_with_the_batch():
    url = f"{mcp_server.SITE_URL}/card/authors/a-b/map.png?hl=1"
    assert outreach.emailed(url, "b1") == f"{SITE}/card/authors/a-b/map.png?hl=1&ref=b1"
    assert outreach.emailed(url) == f"{SITE}/card/authors/a-b/map.png?hl=1"
