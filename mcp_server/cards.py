"""Share cards: the contract a card URL follows, the cards a profile proves, and a
tool that renders one variant.

A card is `/card/<type>/<semantic_id>/<kind>.png` (the site's own share-card
route, rendered server-side from the same data the page shows). A data tool
links a card only when its own response proves the entity has it; `make_card`
builds a variant and fetches it once, so a wrong parameter fails in the session,
not in a post.
"""

import json
from pathlib import Path

import httpx

from mcp_server import VIEW_TYPES, card_url, render_url

# The contract the site's card loaders (src/lib/server/cards/) parse by: every kind with the
# entity types it exists for and its variant parameters, each with its default and limit.
KINDS: dict[str, dict] = json.loads(
    (Path(__file__).parents[1] / "src/lib/assets/data/card-kinds.json").read_text()
)
RENDER_TIMEOUT_S = 180.0


class CardError(ValueError):
    """The site refused to render a card."""


def profile_cards(entity_type: str, semantic_id: str, view: dict) -> dict[str, str]:
    """The default card of every kind an entity's `/views` profile proves it has,
    keyed by kind; the kinds resting on other data come with the tools reading it."""
    coauthors = view.get("relations", {}).get("paper-authors", [])
    shared = KINDS["timeline"]["params"]["min"]["default"]
    proven = {
        "yearly": True,
        "map": True,
        "fields": True,
        "network": len(coauthors) >= 2,
        "timeline": any(c.get("count", 0) >= shared for c in coauthors),
    }
    return {
        kind: card_url(kind, entity_type, semantic_id)
        for kind, has in proven.items()
        if has and entity_type in KINDS[kind]["types"]
    }


async def fetch_card(url: str) -> bytes:
    """The card's PNG from the host that renders the cards."""
    async with httpx.AsyncClient(timeout=RENDER_TIMEOUT_S) as client:
        resp = await client.get(render_url(url))
    if resp.status_code != 200:
        raise CardError(f"{resp.status_code} for {url}: {resp.text[:300]}")
    return resp.content


async def make_card(
    kind: str,
    entity_type: str,
    semantic_id: str = "",
    params: dict[str, str | int] | None = None,
) -> dict:
    """A share card of one kind with a chosen variant: a highlighted country or
    field, an opened branch, a pinned peer, a filtered table. Rendered once here,
    so a wrong parameter fails now rather than in a post; the returned
    `image_url` is the picture to carry. `semantic_id` is empty for a `table`
    of a whole type. Kinds (in brackets the entity types of one not every type
    has) and their parameters, a list parameter comma-separated:
    KINDS
    Node ids for `paths`/`hl` come from get_citation_tree rows (`nodeId`); a
    `table` takes the same `sort`/`where` as rank_entities.
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {list(KINDS)}, got {kind!r}")
    if entity_type not in KINDS[kind]["types"]:
        raise ValueError(f"no {kind} card for {entity_type!r}")
    url = card_url(kind, entity_type, semantic_id, params)
    return {"image_url": url, "bytes": len(await fetch_card(url))}


def _param(name: str, spec: dict) -> str:
    notes = [spec["is"]]
    if "options" in spec:
        notes.append("|".join(spec["options"]))
    if "default" in spec:
        notes.append(f"default {spec['default']}")
    if spec.get("max", 1) > 1:
        notes.append(f"max {spec['max']}")
    return f"{name} ({', '.join(notes)})"


def _kind(kind: str, spec: dict) -> str:
    types = spec["types"]
    only = "" if set(types) == set(VIEW_TYPES) else f" [{', '.join(types)}]"
    params = ", ".join(_param(name, p) for name, p in spec["params"].items())
    return f"- {kind}{only}: {params}"


make_card.__doc__ = (make_card.__doc__ or "").replace(
    "KINDS", "\n    ".join(_kind(kind, spec) for kind, spec in KINDS.items())
)
