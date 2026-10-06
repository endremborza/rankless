# Gen reader audit

The ccl-science-data Python reader loads dmove entity files by regex-parsing the generated Rust in `rankless_rs/src/gen/`. `pyscripts/typeaudit/` runs that parser and reports whether it still finds the entities. The JSON shapes Rust exchanges with TS and Python are generated rather than audited; see [type-generation.md](type-generation.md).

```bash
make type-audit                 # writes logs/type-audit.md + prints a summary
make type-audit ARGS="--strict" # also fail when the ccl parser cannot be imported
```

The check calls `libs/ccl-science-data/scripts/gen_reader.py:_parse_entities` directly (reused, not reimplemented) and compares its output against an independent, format-tolerant ground-truth regex over the gen files. The exit code is nonzero when the parser matches less than half of the array-shaped entities, the signature of a gen format change (the cargo-fmt `& str` → `&str` multiline reflow) its regexes no longer fit. After such a change, fix the regexes and regenerate the checked-in reader stub with `make gen-reader` in the ccl repo.

The reader only loads array-shaped entities (`type T = u{N}` or `Box<[u{N}]>`), so the ground truth is scoped to the same set. A small residue of unmatched entities is structural: an entity without a `NamespacedEntity` impl is unreachable and is reported as info.
