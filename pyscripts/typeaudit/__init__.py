"""Cross-language type / API-shape coherence audit.

Rankless's serialized shapes are declared in three languages and drift apart:
Rust serde structs (the backend source of truth), their TypeScript mirrors, and
the generated-Rust entity types that the ccl-science-data Python reader parses.
This package statically parses each side's *serialized* shape and reports where
they diverge.

Families audited (`uv run -m pyscripts.typeaudit`, `make type-audit`):
- responses -> Rust `/v1` response structs (rankless_server responses.rs +
  rankless_trees io.rs) vs their TS mirrors (src/lib/tree-types.ts, ...).
- ledger    -> TS LedgerPayload (src/lib/types/ledger.ts) vs Rust EventPayload
  (rankless_rs user_ledger.rs).
- gen       -> the generated Rust in rankless_rs/src/gen/ vs the ccl-science-data
  regex reader that consumes it (reused, not reimplemented).

The Rust side is serde-aware: `rename` / `rename_all` / `flatten` are applied and
`skip` / `skip_serializing` fields are dropped, so keys are compared as the actual
JSON emits them, not as the Rust identifiers read.
"""

from dataclasses import dataclass, field


@dataclass
class FieldInfo:
    """One key of a serialized object shape."""

    optional: bool = False  # may be absent (skip_serializing_if / `?` / default)
    type_str: str = ""  # raw declared type, kept for flatten resolution


@dataclass
class Shape:
    """A named object shape: its JSON keys after all (de)serialization rules."""

    name: str
    keys: dict[str, FieldInfo] = field(default_factory=dict)
    source: str = ""  # "file:line" of the declaration
