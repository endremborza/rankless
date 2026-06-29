"""Shared evidence layer: the Playwright-collected entity-page snapshots."""

import json
import random
from pathlib import Path

DATA_PATH = Path("logs/sanity_check_data.json")
IDEAS_PATH = Path(".cril/ideas.md")


def sample_snapshots(snapshots: list[dict], n: int | None) -> list[dict]:
    """Random subset of size n (fresh each run); all of them if n is unset/too big."""
    if not n or n >= len(snapshots):
        return list(snapshots)
    return random.sample(snapshots, n)


def load_snapshots() -> list[dict]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"{DATA_PATH} not found. Run the Playwright collector first "
            "(`make explore` runs it before the paths)."
        )
    snapshots = json.loads(DATA_PATH.read_text())
    if not snapshots:
        raise ValueError(f"No entity snapshots in {DATA_PATH}.")
    return snapshots


def load_vision() -> str:
    return IDEAS_PATH.read_text() if IDEAS_PATH.exists() else ""


def render_snapshot(snap: dict) -> list[str]:
    lines = [
        f"URL: {snap['url']}",
        f"Root Type: {snap['rootType']}",
        f"Name: {snap['name']}",
        f"Stats: {snap['stats']}",
    ]
    if snap.get("expectedDomain"):
        lines.append(f"Expected Domain: {snap['expectedDomain']}")
    if snap.get("fields"):
        lines.append(f"Fields: {', '.join(snap['fields'])}")
    if snap.get("leaders"):
        for leader in snap["leaders"]:
            lines.append(f"  {leader['label']}: {', '.join(leader['items'])}")
    if snap.get("aboutText"):
        lines.append(f"About: {snap['aboutText'][:500]}")
    return lines


def build_evidence_prompt(snapshots: list[dict]) -> str:
    lines = ["Entity page snapshots:\n"]
    for i, snap in enumerate(snapshots, 1):
        lines.append(f"--- Entity {i} ---")
        lines.extend(render_snapshot(snap))
        lines.append("")
    return "\n".join(lines)
