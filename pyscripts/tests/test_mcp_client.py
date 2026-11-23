import asyncio

import httpx
import pytest

from mcp_server import client


def test_an_unreachable_backend_fails_saying_so(monkeypatch: pytest.MonkeyPatch):
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("", request=request)

    down = httpx.AsyncClient(
        base_url="http://backend/v1", transport=httpx.MockTransport(refuse)
    )
    monkeypatch.setattr(client, "_client", down)
    with pytest.raises(
        ConnectionError,
        match="backend unreachable at http://backend/v1/views/authors/x",
    ):
        asyncio.run(client.get_json("/views/authors/x"))


def test_a_rate_limited_request_waits_and_tries_again(monkeypatch: pytest.MonkeyPatch):
    answers = iter([429, 429, 200])

    def limited(request: httpx.Request) -> httpx.Response:
        status = next(answers)
        return httpx.Response(status, json={} if status == 200 else None)

    async def no_wait(_: float) -> None:
        return None

    monkeypatch.setattr(
        client,
        "_client",
        httpx.AsyncClient(
            base_url="http://backend/v1", transport=httpx.MockTransport(limited)
        ),
    )
    monkeypatch.setattr(client.asyncio, "sleep", no_wait)
    assert asyncio.run(client.get_json("/ladder/authors")) == {}
