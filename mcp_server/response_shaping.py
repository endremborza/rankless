"""Shape backend responses for agent consumption.

Trees are flattened with names resolved through the breakdown spec, long lists
are truncated, and entity refs get a `rankless_url` backlink.
"""

from typing import Any

from mcp_server import entity_url

TRUNCATE_N = 12


def add_url(ref: dict, entity_type: str) -> dict:
    if sem := ref.get("semanticId"):
        return {**ref, "rankless_url": entity_url(entity_type, sem)}
    return ref


def truncate_lists(obj: Any, n: int = TRUNCATE_N) -> Any:
    """Recursively cap list lengths; a dict marker replaces the dropped tail."""
    if isinstance(obj, dict):
        return {k: truncate_lists(v, n) for k, v in obj.items()}
    if isinstance(obj, list):
        head = [truncate_lists(v, n) for v in obj[:n]]
        if len(obj) > n:
            head.append({"truncated": len(obj) - n})
        return head
    return obj


def flatten_tree(
    resp: dict, breakdowns: list[dict], top_n: int, depth: int
) -> list[dict]:
    """Nested id-keyed tree -> named top-N rows per level.

    `linkCount` = citation links into the node, `sourceCount` = distinct works.
    Level i's ids resolve through `resp["atts"][breakdowns[i]["attributeType"]]`.
    """
    atts = resp.get("atts", {})

    def walk(node: dict, level: int) -> list[dict]:
        if level >= depth or "children" not in node:
            return []
        etype = breakdowns[level]["attributeType"] if level < len(breakdowns) else None
        named = atts.get(etype, {})
        ranked = sorted(
            node["children"].items(),
            key=lambda kv: kv[1].get("linkCount", 0),
            reverse=True,
        )
        rows = []
        for node_id, child in ranked[:top_n]:
            att = named.get(str(node_id), {})
            row = {
                "entityType": etype,
                "name": att.get("name", f"#{node_id}"),
                "citationLinks": child.get("linkCount", 0),
                "sourceWorks": child.get("sourceCount", 0),
            }
            if sem := att.get("semanticId"):
                row["semanticId"] = sem
                row["rankless_url"] = entity_url(etype, sem)
            if sub := walk(child, level + 1):
                row["children"] = sub
            rows.append(row)
        return rows

    return walk(resp.get("tree", {}), 0)
