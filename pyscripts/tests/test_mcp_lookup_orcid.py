import asyncio

import pytest

from mcp_server import tools


def test_an_orcid_no_author_carries_is_refused_naming_it(
    monkeypatch: pytest.MonkeyPatch,
):
    async def unknown(path: str, params: dict | None = None) -> None:
        return None

    monkeypatch.setattr(tools, "get_json", unknown)
    with pytest.raises(ValueError, match="0000-0001-0000-0001"):
        asyncio.run(tools.lookup_orcid("0000-0001-0000-0001"))
