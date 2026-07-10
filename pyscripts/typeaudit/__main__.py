"""Run the cross-language type-coherence audit.

    uv run -m pyscripts.typeaudit [--strict]   # make type-audit

Parses each side's serialized shape, diffs the declared pairs directionally
(producer → consumer), writes logs/type-audit.md, and prints a summary. Exits
nonzero when an ERROR-level divergence exists (a consumer expects a field its
producer does not send), so it can gate CI; `--strict` also fails on warnings.
"""

import argparse
import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from pyscripts.typeaudit import FieldInfo, rustparse, tsparse
from pyscripts.typeaudit.rustparse import serialized_keys, variant_tag

REPORT_PATH = Path("logs/type-audit.md")

RUST_RESPONSE_FILES = ("rankless_server/src/responses.rs", "rankless_trees/src/io.rs")
TS_RESPONSE_FILES = ("src/lib/tree-types.ts", "src/lib/server/id_resolver.ts")
LEDGER_RUST = "rankless_rs/src/user_ledger.rs"
LEDGER_TS = "src/lib/types/ledger.ts"
GEN_DIR = "rankless_rs/src/gen"
GEN_READER = "libs/ccl-science-data/scripts/gen_reader.py"

# The one hand-maintained mapping: there is no way to infer that Rust `ViewResult`
# is the TS `View`. Rust struct (producer) -> TS type (consumer).
RESPONSE_PAIRS = (
    ("SearchResult", "SearchResult"),
    ("ViewResult", "View"),
    ("PostAttRelatedEntity", "RelatedEntity"),
    ("EntityPeersResp", "EntityPeersResp"),
    ("PeerSubfieldInfo", "PeerSubfield"),
    ("PeerEntry", "PeerEntry"),
    ("RefSubfieldInfo", "RefSubfield"),
    ("LadderResp", "LadderData"),
    ("PaperOut", "Paper"),
    ("PaperAuthorship", "PaperAuthorship"),
    ("PaperAuthorMeta", "AuthorMeta"),
    ("PaperSetResp", "PaperSetResp"),
    ("PaginatedPaperSetResp", "PaginatedPaperSetResp"),
    ("PaperProfileResp", "PaperProfileResp"),
    ("TreeResponse", "TreeResponse"),
    ("TreeSpec", "TreeSpec"),
    ("BreakdownSpec", "BreakdownSpec"),
    ("AttributeLabelOut", "AttributeLabel"),
    ("ResolveWorkResp", "WorkResolveResp"),
    ("ResolveAuthorResp", "AuthorResolveResp"),
    ("CountsResponse", "CountsResponse"),
    ("StatsResp", "StatsResp"),
    ("StatsSubfield", "StatsSubfield"),
)
# Rust response structs with deliberately no TS mirror (only mcp_server reads them).
NO_MIRROR_OK = {"StatsResp", "StatsSubfield"}

# Ledger subject structs (Rust consumes; direction is reversed vs responses).
LEDGER_SUBJECTS = (("WorkSubject", "WorkSubject"), ("AuthorSubject", "AuthorSubject"))

# The ccl reader only loads array-shaped entities (`type T = u{N}` or
# `Box<[u{N}]>`); complex-T entities are intentionally not loadable, so the
# ground truth is scoped to the same set the parser targets.
_ENTITY_NAME_RE = re.compile(
    r"impl Entity for \w+\s*\{\s*type T = (?:u\d+|Box<\[u\d+\]>);"
    r'[^}]*?const NAME: &\s?str = "([^"]+)";',
    re.DOTALL,
)


@dataclass
class Divergence:
    family: str
    pair: str
    severity: str  # error | warn | info
    message: str


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-language type-coherence audit.")
    ap.add_argument("--strict", action="store_true", help="also fail on warnings.")
    args = ap.parse_args()

    divs = _audit_responses() + _audit_ledger() + _audit_gen()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(_render(divs))

    n_err = sum(d.severity == "error" for d in divs)
    n_warn = sum(d.severity == "warn" for d in divs)
    n_info = sum(d.severity == "info" for d in divs)
    print(f"[type-audit] {n_err} error, {n_warn} warn, {n_info} info -> {REPORT_PATH}")
    for d in divs:
        if d.severity == "error":
            print(f"  ERROR [{d.family}] {d.pair}: {d.message}")
    return 1 if n_err or (args.strict and n_warn) else 0


def _load(files) -> dict:
    reg: dict = {}
    for f in files:
        reg |= rustparse.parse_rust(Path(f).read_text(), f.split("/")[-1])
    return reg


def _load_ts(files) -> dict:
    reg: dict = {}
    for f in files:
        reg |= tsparse.parse_ts(Path(f).read_text(), f.split("/")[-1])
    return reg


def _audit_responses() -> list[Divergence]:
    rust = _load(RUST_RESPONSE_FILES)
    ts = _load_ts(TS_RESPONSE_FILES)
    out: list[Divergence] = []
    for rust_name, ts_name in RESPONSE_PAIRS:
        produced = serialized_keys(rust_name, rust)
        if produced is None:
            out.append(
                Divergence("responses", rust_name, "warn", "Rust struct not found")
            )
            continue
        tt = ts.get(ts_name)
        pair = f"{rust_name} → {ts_name}"
        if tt is None or (not tt.keys and tt.variants is None):
            sev = "info" if rust_name in NO_MIRROR_OK else "warn"
            why = " (mcp_server-only)" if rust_name in NO_MIRROR_OK else ""
            out.append(Divergence("responses", pair, sev, f"no TS mirror{why}"))
            continue
        out += _diff_pair("responses", pair, produced, tt.keys, consumer="TS")
    return out


def _audit_ledger() -> list[Divergence]:
    rust = _load([LEDGER_RUST])
    ts = _load_ts([LEDGER_TS])
    out: list[Divergence] = []

    ep = rust.get("EventPayload")
    lp = ts.get("LedgerPayload")
    if ep and lp and lp.variants is not None:
        rust_variants = {
            variant_tag(v, ep.rename_all): {f.ident: FieldInfo(f.optional) for f in fs}
            for v, fs in ep.variants.items()
        }
        for tag in sorted(set(rust_variants) | set(lp.variants)):
            r = rust_variants.get(tag)
            t = lp.variants.get(tag)
            pair = f"kind={tag}"
            if r is None or t is None:
                out.append(Divergence("ledger", pair, "error", "kind on only one side"))
                continue
            # TS produces (writes active.jsonl), Rust consumes (reads it).
            out += _diff_pair(
                "ledger", pair, produced=t, consumed=r, consumer="Rust", hard=True
            )

    for rust_name, ts_name in LEDGER_SUBJECTS:
        r = serialized_keys(rust_name, rust)  # Rust reads these fields
        t = ts.get(ts_name)
        if r is None or t is None:
            continue
        out += _diff_pair(
            "ledger",
            f"{ts_name} → {rust_name}",
            produced=t.keys,
            consumed=r,
            consumer="Rust",
            hard=True,
        )
    return out


def _audit_gen() -> list[Divergence]:
    gen_txt = "\n\n".join(
        p.read_text() for p in sorted(Path(GEN_DIR).iterdir()) if p.suffix == ".rs"
    )
    ground = set(_ENTITY_NAME_RE.findall(gen_txt))
    parse_entities = _import_ccl_parser()
    if parse_entities is None:
        return [Divergence("gen", GEN_READER, "warn", "could not import ccl parser")]
    numents, arrents, _ = parse_entities(gen_txt)
    ccl_names = {en for _, en, _ in [*numents, *arrents]}
    missing = ground - ccl_names
    pair, base = (
        "gen → ccl _parse_entities",
        f"ccl parses {len(ccl_names)}/{len(ground)}",
    )
    # A large drop is the drift signature (cargo-fmt reflows `& str` -> `&str`
    # multiline and a brittle regex silently matches nothing). A small residue
    # is structural: entities without a NamespacedEntity impl are unreachable.
    if not ground or len(ccl_names) < len(ground) // 2:
        return [
            Divergence(
                "gen",
                pair,
                "error",
                f"{base} array entities — the regexes no longer match the gen "
                "format. Fix scripts/gen_reader.py (`&str` / multiline).",
            )
        ]
    if missing:
        return [
            Divergence(
                "gen",
                pair,
                "info",
                f"{base}; {len(missing)} lack a NamespacedEntity impl and aren't "
                f"loadable ({', '.join(sorted(missing))}).",
            )
        ]
    return [Divergence("gen", pair, "info", f"{base} array entities: all loadable.")]


def _diff_pair(
    family: str,
    pair: str,
    produced: dict[str, FieldInfo],
    consumed: dict[str, FieldInfo],
    consumer: str,
    hard: bool = False,
) -> list[Divergence]:
    # `hard` = a consumer-missing field is a real contract break (ledger: Rust
    # must deserialize it). For responses it is only a warning, since TS types
    # legitimately augment server data with client-derived fields.
    out: list[Divergence] = []
    for key in sorted(k for k in consumed if k not in produced):
        # Consumer expects a field the producer never sends.
        optional = consumed[key].optional
        sev = "info" if optional else ("error" if hard else "warn")
        opt = " (optional)" if optional else ""
        out.append(
            Divergence(family, pair, sev, f"{consumer} expects `{key}`{opt}, not sent")
        )
    for key in sorted(k for k in produced if k not in consumed):
        # Producer sends a field the consumer does not model.
        optional = produced[key].optional
        sev = "info" if optional else "warn"
        opt = " (optional)" if optional else ""
        out.append(
            Divergence(
                family, pair, sev, f"`{key}`{opt} sent but not modeled in {consumer}"
            )
        )
    return out


def _import_ccl_parser():
    spec = importlib.util.spec_from_file_location("ccl_gen_reader", GEN_READER)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._parse_entities


def _render(divs: list[Divergence]) -> str:
    order = {"error": 0, "warn": 1, "info": 2}
    n = {s: sum(d.severity == s for d in divs) for s in order}
    out = [
        "# Type-system coherence audit",
        "",
        f"_{n['error']} error · {n['warn']} warn · {n['info']} info. "
        "Producer → consumer; ERROR = consumer expects a field the producer never "
        "sends. Generated by `make type-audit`._",
        "",
    ]
    for family in ("responses", "ledger", "gen"):
        fam = [d for d in divs if d.family == family]
        if not fam:
            continue
        out += [f"## {family} ({len(fam)})", ""]
        for d in sorted(fam, key=lambda d: (order[d.severity], d.pair)):
            mark = {"error": "🔴", "warn": "🟡", "info": "⚪"}[d.severity]
            out.append(f"- {mark} **{d.pair}** — {d.message}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


if __name__ == "__main__":
    sys.exit(main())
