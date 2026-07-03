# Type-system coherence audit

Rankless declares the same serialized shapes in three languages, which drift apart:
the Rust serde structs are the source of truth, the TypeScript frontend mirrors them
by hand, and the generated-Rust entity types are re-parsed by the ccl-science-data
Python reader. `pyscripts/typeaudit/` statically parses each side's **serialized**
shape and reports where they diverge.

```bash
make type-audit                 # writes logs/type-audit.md + prints a summary
make type-audit ARGS="--strict" # also fail (nonzero) on warnings, for CI
```

Exit code is nonzero when an ERROR-level divergence exists (or on any warning under
`--strict`), so it can gate CI; otherwise it is an informational report.

## What it parses

The Rust side is **serde-aware** (`pyscripts/typeaudit/rustparse.py`): it applies
`rename` / `rename_all` / `flatten` and drops `skip` / `skip_serializing` fields, so it
compares the actual JSON keys, not the Rust identifiers. The TS side
(`tsparse.py`) handles `export`/local `type` and `interface` declarations and
`kind`-discriminated unions. Both are targeted at the codebase's rustfmt/prettier
style (one field per line), not general grammars.

## Families

Each family has a producer → consumer direction; an **ERROR** means the consumer
expects a field the producer never sends.

| Family      | Producer → consumer                                                                                                                   | Source of truth | Hard errors on                                                                                              |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------- | --------------- | ----------------------------------------------------------------------------------------------------------- |
| `responses` | Rust `/v1` structs (`rankless_server/responses.rs` + `rankless_trees/io.rs`) → TS mirrors (`src/lib/tree-types.ts`, `id_resolver.ts`) | Rust            | — (TS legitimately augments server data with client-derived fields, so all response drift is a **warning**) |
| `ledger`    | TS `LedgerPayload` (`src/lib/types/ledger.ts`) → Rust `EventPayload` (`rankless_rs/user_ledger.rs`)                                   | TS writer       | a field Rust deserializes that TS no longer sends                                                           |
| `gen`       | generated Rust (`rankless_rs/src/gen/`) → ccl-science-data reader                                                                     | Rust            | the ccl regex parser silently matching almost nothing (the cargo-fmt `& str`→`&str` reflow drift)           |

The Rust-struct ↔ TS-type pairing (`RESPONSE_PAIRS` in `__main__.py`) is the one
hand-maintained mapping — there is no way to infer that Rust `ViewResult` is the TS
`View`. Add a pair when a new response type gains a TS mirror.

## The gen family reuses the ccl parser

The `gen` check calls `libs/ccl-science-data/scripts/gen_reader.py:_parse_entities`
directly (reused, not reimplemented) and compares its output against an independent,
format-tolerant ground-truth regex over the gen files. Its brittle regexes (which
hard-coded `& str` and single-line impl blocks) were fixed to match the current
`&str` multiline output — after a format change, regenerate the checked-in reader
stub with `make gen-reader` in the ccl repo.

## Known standing divergences (as of the current audit)

These are surfaced as warnings, not bugs to auto-fix — review before acting:

- `View.instRels` and `SearchResult.rootType` are typed on the TS side but not sent by
  `/v1/views` / plain `/v1/names` responses (client-augmented / union-only).
- TS `TreeSpec` omits `allowSpec` and `defaultYear`, which the backend sends and
  `mcp_server` relies on.
- `StatsResp` / `StatsSubfield` have no TS mirror (consumed only by `mcp_server`).
