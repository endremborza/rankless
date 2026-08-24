"""Shared engine for object-store generator workflows (game cards, impact
stories, ...).

A generator run is one `mcp_sessions` row (self-registered when CLI-started,
worker-claimed when queued from `/mcp`) that picks target entities from the
backend's citation-ordered slice, mines each with one agentic session over the
MCP tools, verifies every cited number through `verify.reissue`, and lands the
accepted objects as one immutable bundle in the object store. A workflow
supplies only its prompts and its accept policy via `GeneratorSpec`; naming,
session lifecycle, target picking, concurrency, bundling, and reporting live
here. Reruns are idempotent per entity: already-stored keys are skipped
(`--refresh` re-mines them) and the per-country cap keeps packs diverse — the
spec's payloads must carry the target's `semId` and `cc` for that bookkeeping.
Batch-prompted workflows (country_cards) skip the per-target mining but share
the run lifecycle via `run_bundle` and the selection helpers.
"""

import asyncio
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Iterable

import mcp_server
from mcp_server import client as be_client
from pyscripts import object_store
from pyscripts.explore import cli, runner, runs
from pyscripts import paths


@dataclass(frozen=True)
class GeneratorSpec:
    workflow: str  # session type = CLI command = run-name prefix
    kind: str  # object-store kind written
    title: str  # session/report title prefix
    max_turns: int
    timeout_s: int
    require_coords: bool
    system_prompt: Callable[[str], str]  # etype -> system prompt
    user_prompt: Callable[[dict], str]  # target -> user prompt
    # (target, parsed_json, log) -> {"title", "payload"} or None when dropped;
    # runs on an event loop so it can re-issue facts through the backend.
    build_object: Callable[[dict, dict, list[str]], Awaitable[dict | None]]


BREAK_AFTER = 5


@dataclass(frozen=True)
class GenConfig:
    backend_url: str
    backend_label: str
    etype: str
    count: int
    pool: int
    per_country: int
    sem_ids: str
    model: str
    engine: str
    concurrency: int
    refresh: bool


class _MineBreaker:
    """Trips after BREAK_AFTER consecutive mining failures — a dead auth or
    exhausted usage window fails every session instantly, so plowing on burns
    the whole target list. Skipped targets stay unstored and an idempotent
    rerun picks them up once the window clears."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._consecutive = 0
        self.skipped = 0
        self.open = False

    def record(self, failed: bool) -> None:
        with self._lock:
            self._consecutive = self._consecutive + 1 if failed else 0
            if self._consecutive >= BREAK_AFTER:
                self.open = True

    def skip(self) -> bool:
        with self._lock:
            if self.open:
                self.skipped += 1
            return self.open


class CcCap:
    """Per-country diversity cap. Only real country buckets count: entities
    whose distinctText carries no flag marker (authors, countries) fold to
    cc = '' and are never capped."""

    def __init__(self, have_ccs: Iterable[str], limit: int) -> None:
        self._counts: dict[str, int] = {}
        self._limit = limit
        for cc in have_ccs:
            self.add(cc)

    def full(self, cc: str) -> bool:
        return bool(cc) and self._counts.get(cc, 0) >= self._limit

    def add(self, cc: str) -> None:
        if cc:
            self._counts[cc] = self._counts.get(cc, 0) + 1


def log_note(log: list[str], workflow: str, message: str) -> None:
    log.append(message)
    print(f"[{workflow}] {message}")


def default_report_line(o: dict) -> str:
    return f"- `{o['sem_id']}` — {o['title']}"


def run_bundle(
    *,
    workflow: str,
    title: str,
    etype: str,
    backend: str,
    backend_label: str,
    model: str,
    count: int,
    kind: str,
    session: str,
    generate: Callable[[sqlite3.Connection], tuple[list[dict], int, list[str]]],
    report_line: Callable[[dict], str] = default_report_line,
) -> None:
    """Shared run lifecycle: session row, bundle write, meta/report, summary.
    `generate` returns (accepted objects, target/candidate count, log)."""
    name = session or runs.run_name(workflow, etype)
    con = object_store.connect()
    params = {
        "type": workflow,
        "backend": backend,
        "etype": etype,
        "count": count,
        "model": model,
    }
    runs.open_run(con, name, f"{title}: {etype}", params)
    try:
        objects, n_targets, log = generate(con)
        object_store.write_bundle(con, name, objects)
        n_current = len(
            [r for r in object_store.current(con, kind) if r["etype"] == etype]
        )
        meta = {
            "type": workflow,
            "backend": backend_label,
            "model": model,
            "generated": runs.utc_now_iso(),
            "counts": {
                "accepted": len(objects),
                "targets": n_targets,
                "stored": n_current,
            },
        }
        _write_report(name, title, objects, log, meta, report_line)
        runs.close_run(con, name, "done", meta=meta)
    except BaseException as exc:
        runs.close_run(con, name, "failed", error=repr(exc))
        raise
    finally:
        con.close()
    print(
        f"[{workflow}] {len(objects)}/{n_targets} accepted into bundle "
        f"{name!r}; {n_current} current {etype} object(s) in store"
    )


def run(
    spec: GeneratorSpec,
    *,
    backend: str,
    etype: str,
    count: int,
    pool: int,
    per_country: int,
    sem_ids: str,
    model: str,
    engine: str,
    concurrency: int,
    refresh: bool,
    session: str,
) -> None:
    backend_url, backend_label = runner.resolve_backend(backend)
    mcp_server.set_backend(backend_url)
    cfg = GenConfig(
        backend_url=backend_url,
        backend_label=backend_label,
        etype=etype,
        count=count,
        pool=pool,
        per_country=per_country,
        sem_ids=sem_ids,
        model=cli.resolve_model(model),
        engine=engine,
        concurrency=concurrency,
        refresh=refresh,
    )

    def generate(con: sqlite3.Connection) -> tuple[list[dict], int, list[str]]:
        objects, targets, log = _generate(con, spec, cfg)
        return objects, len(targets), log

    run_bundle(
        workflow=spec.workflow,
        title=spec.title,
        etype=etype,
        backend=backend,
        backend_label=backend_label,
        model=cfg.model,
        count=count,
        kind=spec.kind,
        session=session,
        generate=generate,
    )


def _generate(
    con: sqlite3.Connection, spec: GeneratorSpec, cfg: GenConfig
) -> tuple[list[dict], list[dict], list[str]]:
    have = {} if cfg.refresh else stored_ccs(con, spec.kind, cfg.etype)
    targets = asyncio.run(_pick_targets(spec, cfg, have))
    print(
        f"[{spec.workflow}] {len(targets)} target(s); model={cfg.model}; "
        f"{len(have)} already stored"
    )
    mine = runner.get_runner(cfg.engine)
    breaker = _MineBreaker()
    with ThreadPoolExecutor(max_workers=cfg.concurrency) as pex:
        raws = list(pex.map(lambda t: _mine_one(spec, cfg, mine, t, breaker), targets))
    log: list[str] = []
    if breaker.open:
        log_note(
            log,
            spec.workflow,
            f"mining breaker tripped after {BREAK_AFTER} consecutive failures; "
            f"{breaker.skipped} target(s) skipped",
        )
    objects = asyncio.run(_build_all(spec, cfg.etype, targets, raws, log))
    return objects, targets, log


def stored_ccs(con: sqlite3.Connection, kind: str, etype: str) -> dict[str, str]:
    # current() skips rejected versions, so a rejected card frees its entity
    # for re-mining and stops counting toward the per-country cap
    row_list = [r for r in object_store.current(con, kind) if r["etype"] == etype]
    return {
        r["sem_id"]: entry["payload"].get("cc", "")
        for r, entry in zip(row_list, object_store.read_entries(row_list))
        if entry is not None
    }


async def _pick_targets(
    spec: GeneratorSpec, cfg: GenConfig, have: dict[str, str]
) -> list[dict]:
    try:
        ranked = await be_client.get_json(f"/slice/{cfg.etype}/0/{cfg.pool}")
        if cfg.sem_ids:
            wanted = [s.strip() for s in cfg.sem_ids.split(",") if s.strip()]
            by_sem = {e["semanticId"]: e for e in ranked}
            ranked = [by_sem[s] for s in wanted if s in by_sem]
            if missing := [s for s in wanted if s not in by_sem]:
                raise SystemExit(f"--sem-ids not in top-{cfg.pool} slice: {missing}")
        targets: list[dict] = []
        if cfg.count <= 0:
            return targets
        cap = CcCap(have.values(), cfg.per_country)
        for ent in ranked:
            cc = flag_cc(ent.get("distinctText", ""))
            if ent["semanticId"] in have:
                continue
            if not cfg.sem_ids and cap.full(cc):
                continue
            view = await be_client.get_json(f"/views/{cfg.etype}/{ent['semanticId']}")
            lat = float(view.get("meta", {}).get("lat", 0) or 0)
            lon = float(view.get("meta", {}).get("lon", 0) or 0)
            if spec.require_coords and lat == 0 and lon == 0:
                continue
            cap.add(cc)
            targets.append(
                {
                    "semId": ent["semanticId"],
                    "name": ent["name"],
                    "distinctText": ent.get("distinctText", ""),
                    "cc": cc,
                    "lat": lat,
                    "lon": lon,
                    "papers": ent.get("papers", 0),
                    "citations": ent.get("citations", 0),
                }
            )
            if len(targets) >= cfg.count:
                break
        return targets
    finally:
        await be_client.aclose()


def flag_cc(distinct_text: str) -> str:
    # country flag emoji = two regional-indicator codepoints (ISO2)
    ris = [c for c in distinct_text if 0x1F1E6 <= ord(c) <= 0x1F1FF]
    return "".join(chr(ord(c) - 0x1F1E6 + ord("A")) for c in ris[:2])


async def fetch_slice(etype: str, lo: int, hi: int) -> list[dict]:
    """One-shot ranked-slice fetch for workflows that need no per-target views."""
    try:
        return await be_client.get_json(f"/slice/{etype}/{lo}/{hi}")
    finally:
        await be_client.aclose()


def _mine_one(
    spec: GeneratorSpec, cfg: GenConfig, mine, target: dict, breaker: _MineBreaker
) -> str | None:
    if breaker.skip():
        return None
    job = runner.MineJob(
        system=spec.system_prompt(cfg.etype),
        user=spec.user_prompt(target),
        model=cfg.model,
        backend_url=cfg.backend_url,
        max_turns=spec.max_turns,
        timeout_s=spec.timeout_s,
    )
    try:
        raw = mine(job)
    except RuntimeError as exc:
        print(f"[{spec.workflow}] {target['semId']}: mining failed: {exc}")
        breaker.record(failed=True)
        return None
    breaker.record(failed=False)
    return raw


async def _build_all(
    spec: GeneratorSpec,
    etype: str,
    targets: list[dict],
    raws: list[str | None],
    log: list[str],
) -> list[dict]:
    objects = []
    try:
        for target, raw in zip(targets, raws):
            sem = target["semId"]
            if raw is None:
                log_note(log, spec.workflow, f"{sem}: mining produced no response")
                continue
            try:
                parsed = cli.parse_json(raw)
            except (ValueError, json.JSONDecodeError) as exc:
                log_note(log, spec.workflow, f"{sem}: unparseable response ({exc})")
                continue
            obj = await spec.build_object(target, parsed, log)
            if obj is not None:
                objects.append(
                    {
                        "kind": spec.kind,
                        "obj_key": f"{etype}|{sem}",
                        "etype": etype,
                        "sem_id": sem,
                        "title": obj["title"],
                        "payload": obj["payload"],
                    }
                )
    finally:
        await be_client.aclose()
    return objects


def _write_report(
    name: str,
    title: str,
    objects: list[dict],
    log: list[str],
    meta: dict,
    report_line: Callable[[dict], str],
) -> None:
    root = Path(paths.sessions_root())
    run_dir = root / name
    run_dir.mkdir(parents=True, exist_ok=True)
    c = meta["counts"]
    lines = [
        f"# {title} — {meta['backend']}",
        "",
        f"_Model `{meta['model']}` · {meta['generated']} · "
        f"{c['accepted']}/{c['targets']} accepted._",
        "",
        "## Accepted",
        "",
    ]
    lines += [report_line(o) for o in objects]
    if log:
        lines += ["", "## Verification log", ""]
        lines += [f"- {entry}" for entry in log]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n")
