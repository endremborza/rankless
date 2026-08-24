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
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

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


def log_note(log: list[str], workflow: str, message: str) -> None:
    log.append(message)
    print(f"[{workflow}] {message}")


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
    name = session or runs.run_name(spec.workflow, etype)
    con = object_store.connect()
    params = {
        "type": spec.workflow,
        "backend": backend,
        "etype": etype,
        "count": count,
        "model": cfg.model,
    }
    runs.open_run(con, name, f"{spec.title}: {etype}", params)
    try:
        objects, targets, log = _generate(con, spec, cfg)
        object_store.write_bundle(con, name, objects)
        n_current = len(
            [r for r in object_store.current(con, spec.kind) if r["etype"] == etype]
        )
        meta = {
            "type": spec.workflow,
            "backend": backend_label,
            "model": cfg.model,
            "generated": runs.utc_now_iso(),
            "counts": {
                "accepted": len(objects),
                "targets": len(targets),
                "stored": n_current,
            },
        }
        _write_report(name, spec, objects, log, meta)
        runs.close_run(con, name, "done", meta=meta)
    except BaseException as exc:
        runs.close_run(con, name, "failed", error=repr(exc))
        raise
    finally:
        con.close()
    print(
        f"[{spec.workflow}] {len(objects)}/{len(targets)} accepted into bundle "
        f"{name!r}; {n_current} current {etype} object(s) in store"
    )


def _generate(
    con, spec: GeneratorSpec, cfg: GenConfig
) -> tuple[list[dict], list[dict], list[str]]:
    have = {} if cfg.refresh else _stored_ccs(con, spec.kind, cfg.etype)
    targets = asyncio.run(_pick_targets(spec, cfg, have))
    print(
        f"[{spec.workflow}] {len(targets)} target(s); model={cfg.model}; "
        f"{len(have)} already stored"
    )
    mine = runner.get_runner(cfg.engine)
    with ThreadPoolExecutor(max_workers=cfg.concurrency) as pex:
        raws = list(pex.map(lambda t: _mine_one(spec, cfg, mine, t), targets))
    log: list[str] = []
    objects = asyncio.run(_build_all(spec, cfg.etype, targets, raws, log))
    return objects, targets, log


def _stored_ccs(con, kind: str, etype: str) -> dict[str, str]:
    row_list = [r for r in object_store.rows(con, kind) if r["etype"] == etype]
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
        cc_counts: dict[str, int] = {}
        for cc in have.values():
            cc_counts[cc] = cc_counts.get(cc, 0) + 1
        for ent in ranked:
            cc = _flag_cc(ent.get("distinctText", ""))
            if ent["semanticId"] in have:
                continue
            # cap only real country buckets: etypes without flag markers
            # (authors, countries) all fold to cc = ''
            if not cfg.sem_ids and cc and cc_counts.get(cc, 0) >= cfg.per_country:
                continue
            view = await be_client.get_json(f"/views/{cfg.etype}/{ent['semanticId']}")
            lat = float(view.get("meta", {}).get("lat", 0) or 0)
            lon = float(view.get("meta", {}).get("lon", 0) or 0)
            if spec.require_coords and lat == 0 and lon == 0:
                continue
            cc_counts[cc] = cc_counts.get(cc, 0) + 1
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


def _flag_cc(distinct_text: str) -> str:
    # country flag emoji = two regional-indicator codepoints (ISO2)
    ris = [c for c in distinct_text if 0x1F1E6 <= ord(c) <= 0x1F1FF]
    return "".join(chr(ord(c) - 0x1F1E6 + ord("A")) for c in ris[:2])


def _mine_one(spec: GeneratorSpec, cfg: GenConfig, mine, target: dict) -> str | None:
    job = runner.MineJob(
        system=spec.system_prompt(cfg.etype),
        user=spec.user_prompt(target),
        model=cfg.model,
        backend_url=cfg.backend_url,
        max_turns=spec.max_turns,
        timeout_s=spec.timeout_s,
    )
    try:
        return mine(job)
    except RuntimeError as exc:
        print(f"[{spec.workflow}] {target['semId']}: mining failed: {exc}")
        return None


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
    name: str, spec: GeneratorSpec, objects: list[dict], log: list[str], meta: dict
) -> None:
    root = Path(paths.sessions_root())
    run_dir = root / name
    run_dir.mkdir(parents=True, exist_ok=True)
    c = meta["counts"]
    lines = [
        f"# {spec.title} — {meta['backend']}",
        "",
        f"_Model `{meta['model']}` · {meta['generated']} · "
        f"{c['accepted']}/{c['targets']} accepted._",
        "",
        "## Accepted",
        "",
    ]
    lines += [f"- `{o['sem_id']}` — {o['title']}" for o in objects]
    if log:
        lines += ["", "## Verification log", ""]
        lines += [f"- {entry}" for entry in log]
    (run_dir / "report.md").write_text("\n".join(lines) + "\n")
