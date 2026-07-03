"""Seed the browsable MCP sessions store from existing exploration writeups.

Copies each writeup dir into `$MCP_SESSIONS_ROOT/<name>/` and upserts a public,
done `mcp_sessions` row (params + meta reconstructed from findings.json). Used to
give the public gallery initial content.

    uv run -m pyscripts.mcp_seed [<writeup-dir> ...]     # make mcp-seed
"""

import json
import shutil
import sys
from pathlib import Path

from pyscripts.mcp_worker import SESSIONS_ROOT, _connect

DEFAULTS = (
    ".cril/writeups/explorations/live-demo",
    ".cril/writeups/explorations/subject-lengyel",
)


def main() -> int:
    dirs = [a for a in sys.argv[1:] if not a.startswith("-")] or list(DEFAULTS)
    root = Path(SESSIONS_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    seeded = 0
    for d in dirs:
        src = Path(d)
        findings = src / "findings.json"
        if not findings.exists():
            print(f"[mcp-seed] skip {src} (no findings.json)")
            continue
        meta = json.loads(findings.read_text()).get("meta", {})
        name = src.name
        dst = root / name
        if src.resolve() != dst.resolve():
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        conn.execute(
            "INSERT INTO mcp_sessions "
            "(name, orcid, status, visibility, title, params, meta) "
            "VALUES (?, NULL, 'done', 'public', ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET status='done', visibility='public', "
            "title=excluded.title, params=excluded.params, meta=excluded.meta, "
            "updated_at=datetime('now')",
            (name, _title(meta), json.dumps(_params(meta)), json.dumps(meta)),
        )
        conn.commit()
        seeded += 1
        print(f"[mcp-seed] seeded {name}")
    conn.close()
    print(f"[mcp-seed] {seeded} session(s) -> {root}")
    return 0


def _params(meta: dict) -> dict:
    return {
        "backend": meta.get("backend", "live"),
        "foci": meta.get("foci", []),
        "subject": meta.get("subject"),
        "question": meta.get("question"),
        "investigate": meta.get("investigate"),
        "model": meta.get("model"),
    }


def _title(meta: dict) -> str:
    if meta.get("investigate"):
        return f"Deepening {meta['investigate']}"
    if meta.get("subject"):
        return meta["subject"]
    if meta.get("question"):
        return meta["question"]
    return f"{', '.join(meta.get('foci', []))} on {meta.get('backend')}"


if __name__ == "__main__":
    raise SystemExit(main())
