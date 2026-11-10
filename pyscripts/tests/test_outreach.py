from pathlib import Path

import httpx
import pytest

import mcp_server
from pyscripts import outreach
from pyscripts.outreach import (
    SITE,
    SOURCE_SENTENCES,
    Bold,
    Content,
    Evidence,
    Fact,
    Recipient,
    SendLog,
)
from wire.rankless_server.responses import METHODOLOGY

ROW = Recipient("a-b", "a@b.org", "corresponding")


def content(**over) -> Content:
    base = dict(
        name="A B",
        profile=f"{SITE}/authors/a-b",
        login=f"{SITE}/login",
        facts=[Fact(("A fact.",), f"{SITE}/card/authors/a-b/map.png", "A map")],
    )
    return Content(**{**base, **over})


def evidence(**over) -> Evidence:
    base = dict(
        semantic_id="a-b",
        name="A B",
        partners=[],
        papers=[],
        peers={"hero": {}, "peers": [], "topSubfields": [], "refSubfields": []},
        ladder={"ladder": [], "pctBands": []},
        countries={"tree": {}, "atts": {}},
        impact={"citingHits": []},
    )
    return Evidence(**{**base, **over})


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


def test_excess_countries_leave_out_partner_nations_and_thin_ones():
    links = {"1": 300, "2": 100, "3": outreach.EXCESS_MIN_LINKS - 1}
    countries = {
        "tree": {
            "linkCount": 1000,
            "children": {nid: {"linkCount": n} for nid, n in links.items()},
        },
        "atts": {
            "countries": {
                nid: {"name": name, "specBaseline": 0.001}
                for nid, name in [("1", "Home"), ("2", "Far"), ("3", "Thin")]
            }
        },
    }
    fact = outreach._excess_fact(evidence(partners=["Home"], countries=countries))
    assert fact and Bold("Far") in fact.parts
    assert "Thin" not in outreach.to_text([outreach.Para(fact.parts)])


def test_momentum_needs_its_lead_over_the_peers():
    first, last = METHODOLOGY["yearlyCounts"]
    years = last - first + 1
    before = outreach.MOMENTUM_MIN_CITES * outreach.MOMENTUM_YEARS
    span = 2 * outreach.MOMENTUM_YEARS

    def yearly(after: float) -> list[float]:
        per = outreach.MOMENTUM_YEARS
        return ([before / per] * per + [after / per] * per + [0] * years)[:years]

    peer = {"yearlyCites": yearly(2 * before)}
    assert years > span

    def fact(after: float) -> Fact | None:
        peers = {"hero": {"yearlyCites": yearly(after)}, "peers": [peer]}
        return outreach._momentum_fact(evidence(peers=peers))

    lead = 2 * before * outreach.MOMENTUM_MIN_LEAD
    assert fact(lead) and not fact(lead * 0.99)


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


def test_links_move_to_the_canonical_host_untagged():
    url = f"{mcp_server.SITE_URL}/card/authors/a-b/map.png?hl=1"
    assert outreach.emailed(url) == f"{SITE}/card/authors/a-b/map.png?hl=1"
