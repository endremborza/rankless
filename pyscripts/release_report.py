"""Release report: pure derivation from release records (docs/deploy.md).

`build_report(record, previous)` turns `releases/<run_id>.json` into the public
report — filtering cardinalities, ledger aggregates, deltas vs the previous
release. The site asset (`src/lib/assets/data/release-report.json`), the
promote gate and the promo digest all derive from its output; nothing here
reads live state. Aggregates only: ledger feed names never leave this module.
"""

import json
import os
from pathlib import Path

ASSET_PATH = Path("src/lib/assets/data/release-report.json")

ENTITY_ORDER = ("works", "authors", "sources", "institutions")
# (filter step id, entity) → public phrasing of what survives it; the ids and
# semantics are rankless_rs/src/filter.rs `main`.
STEP_LABELS = {
    (
        "10",
        "works",
    ): "research publications — articles, conference papers, books, chapters and reviews "
    "(or restored by their authors); not retracted; in covered years",
    ("11", "works"): "cited at least once by an indexed work, or restored",
    ("12", "sources"): "venues with enough indexed works",
    ("13", "institutions"): "institutions with enough indexed works",
    ("14", "works"): "authorship resolved, user corrections applied",
    ("14", "authors"): "credited on an indexed work",
    ("20", "authors"): "above the activity threshold, or a registered owner",
    ("21", "institutions"): "affiliated with indexed works after all screens",
}


def build_report(record: dict, previous: dict | None = None) -> dict:
    report = {
        "run_id": record["run_id"],
        "stamp": record["stamp"],
        "git_commit": record["git_commit"],
        "snapshot": record["snapshot"],
        "entities": _entity_chains(record["filter_counts"]),
        "ledger": _ledger_aggregates(record),
        "restored": record.get("forced_works"),
        "claims": record.get("claims_review"),
        "previous": None,
        "deltas": None,
    }
    if previous is not None:
        prev_report = build_report(previous)
        report["previous"] = {
            "run_id": previous["run_id"],
            "snapshot": previous["snapshot"],
        }
        report["deltas"] = _deltas(report, prev_report)
    return report


def load_records(root: Path | None = None) -> tuple[dict, dict | None]:
    """Current release record + the latest one before it, from $OA_ROOT/releases."""
    rdir = (root or Path(os.environ["OA_ROOT"])) / "releases"
    current = json.loads((rdir / "release.json").read_text())
    older = sorted(
        p
        for p in rdir.glob("*.json")
        if p.name != "release.json" and p.stem < current["run_id"]
    )
    previous = json.loads(older[-1].read_text()) if older else None
    return current, previous


def write_report_asset(
    root: Path | None = None, *, warn_missing: bool = False
) -> Path | None:
    """Bake the site asset (warn_missing: warn-only while the root predates
    release manifests — the composite build paths pass it)."""
    rdir = (root or Path(os.environ["OA_ROOT"])) / "releases"
    if warn_missing and not (rdir / "release.json").exists():
        print(
            "WARNING — no release manifest for this root, report asset kept as-is; "
            "run `uv run -m pyscripts recalc manifest`"
        )
        return None
    current, previous = load_records(root)
    report = build_report(current, previous)
    ASSET_PATH.write_text(json.dumps(report, indent=1))
    print(f"release report: {ASSET_PATH} ({report['run_id']})")
    return ASSET_PATH


def assert_report_documents(version: str, path: Path = ASSET_PATH) -> dict:
    """The committed report asset documents the served version (promote gate)."""
    if not path.exists():
        raise SystemExit(
            f"no release report asset at {path} — run `make lib_data_generation`"
        )
    report = json.loads(path.read_text())
    run_id = report["run_id"]
    if not version.rsplit("|", 1)[-1].startswith(run_id):
        raise SystemExit(
            f"served version {version!r} is not the reported release "
            f"{run_id!r} ({path})"
        )
    print(f"release report documents served release {run_id}")
    return report


def render_md(report: dict) -> str:
    """The same report as a copy-paste promo digest."""
    lines = [
        f"## Rankless data release {report['run_id'][:10]}",
        "",
        f"Built from OpenAlex snapshot {report['snapshot']['date']} "
        f"(`{report['stamp']}`).",
        "",
    ]
    for name, chain in report["entities"].items():
        arrow = " → ".join(
            f"{_fmt(s['kept'])} {s['label']}" for s in chain["steps"] if s["kept"]
        )
        lines.append(f"- **{name}**: {arrow}")
    ledger = report["ledger"]
    kinds = ", ".join(
        f"{n} {k.replace('_', ' ')}" for k, n in ledger["applied"].items()
    )
    lines += [
        "",
        f"User ledger: {ledger['applied_total']} correction(s) integrated"
        + (f" ({kinds})" if kinds else "")
        + f", {ledger['skipped_total']} skipped.",
    ]
    restored = report.get("restored")
    if restored and restored["outside_standard"]:
        lines += [
            "",
            f"Papers restored by their authors: {restored['outside_standard']} "
            f"(from {restored['cohort']} signed-in researcher(s)) served beyond the "
            "standard screens.",
        ]
    claims = report.get("claims")
    if claims and claims["submitted"]:
        lines += [
            "",
            f"Paper claims: {claims['applied']} of {claims['submitted']} resolved.",
        ]
        if claims["unresolved_by_cause"]:
            causes = "; ".join(
                f"{n} {c}" for c, n in claims["unresolved_by_cause"].items()
            )
            lines.append(f"The rest could not be: {causes}.")
    deltas = report["deltas"]
    if deltas:
        ent_bits = ", ".join(
            f"{name} {d['change']:+,}" for name, d in deltas["entities"].items()
        )
        lines += [
            "",
            f"Vs {report['previous']['run_id'][:10]}: {ent_bits}; "
            f"{deltas['applied_total']['new']:+} newly integrated correction(s).",
        ]
    return "\n".join(lines) + "\n"


def main(*, md: bool = False) -> None:
    """Regenerate the site report asset from $OA_ROOT/releases
    (--md also prints the promo digest)."""
    path = write_report_asset()
    if md and path is not None:
        print(render_md(json.loads(path.read_text())))


def _entity_chains(filter_counts: dict) -> dict:
    chains: dict[str, dict] = {}
    for step in sorted(filter_counts, key=int):
        for ent, counts in filter_counts[step].items():
            steps = chains.setdefault(ent, {"steps": []})["steps"]
            steps.append(
                {
                    "label": STEP_LABELS.get((step, ent), f"filter step {step}"),
                    "in": counts["in"],
                    "kept": counts["kept"],
                }
            )
    ordered = {e: chains.pop(e) for e in ENTITY_ORDER if e in chains} | chains
    for chain in ordered.values():
        chain["final"] = chain["steps"][-1]["kept"]
    return ordered


def _ledger_aggregates(record: dict) -> dict:
    applied, skipped = record["applied"], record["skipped"]
    return {
        "sources": len(record["ledger"]),
        "events": sum(record["ledger"].values()),
        "applied": applied,
        "applied_total": sum(applied.values()),
        "skipped": skipped,
        "skipped_total": sum(skipped.values()),
    }


def _deltas(cur: dict, prev: dict) -> dict:
    entities = {
        name: {
            "previous": prev["entities"][name]["final"],
            "current": chain["final"],
            "change": chain["final"] - prev["entities"][name]["final"],
        }
        for name, chain in cur["entities"].items()
        if name in prev["entities"]
    }
    applied = {}
    for kind in {**prev["ledger"]["applied"], **cur["ledger"]["applied"]}:
        p = prev["ledger"]["applied"].get(kind, 0)
        c = cur["ledger"]["applied"].get(kind, 0)
        applied[kind] = {"previous": p, "current": c, "new": c - p}
    return {
        "entities": entities,
        "applied": applied,
        "applied_total": {
            "previous": prev["ledger"]["applied_total"],
            "current": cur["ledger"]["applied_total"],
            "new": cur["ledger"]["applied_total"] - prev["ledger"]["applied_total"],
        },
    }


def _fmt(n: int) -> str:
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if n >= div:
            return f"{n / div:.4g}{suffix}"
    return str(n)
