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
