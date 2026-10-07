# Type generation (`wiretypes`)

Rust is the one language cross-language shapes and constants are written in. Every struct or enum that crosses a language boundary, and every constant another language needs, carries `#[wire]`, and `wiretypes` renders it as TypeScript and Python, one file per Rust module. The generated files are committed and never edited by hand.

```bash
make types        # rewrite src/lib/wire/ and wire/ from the Rust types (also part of make format)
make check-types  # fail when they are stale (part of make check)
```

## Marking a type

`#[wire]` goes above the type's `#[derive(..)]`:

```rust
use wiretypes::wire;

#[wire]
#[derive(Serialize)]
pub(crate) struct SearchResult {
    pub name: Arc<str>,
    #[serde(rename = "semanticId")]
    pub semantic_id: Arc<str>,
    #[serde(rename = "rawCites", skip_serializing_if = "Option::is_none")]
    pub raw_cites: Option<u32>,
}
```

It derives `schemars::JsonSchema`, so the schema follows every serde attribute (`rename`, `rename_all`, `flatten`, `skip`, enum tagging), and registers the type with its module path through `inventory`. A crate with wire types depends on `wiretypes` alone, which re-exports both.

- The serde derives pick the contract: with `Serialize` the type describes what Rust sends, with `Deserialize` alone what Rust accepts.
- A record that other languages write and Rust reads leniently derives both and marks the fields Rust can do without `#[serde(default)]`: the generated type is what a writer must produce (the ledger subjects).
- `skip_serializing_if = "Option::is_none"` makes a field absent rather than null (`field?: T`, `NotRequired[T]`); a plain `Option<T>` is a required, nullable field.
- Every type a registered type reaches needs `#[wire]` too; generation fails naming the one that lacks it.
- A generic struct carries `#[wire]` for the derive and is registered per instantiation through an alias: `#[wire] pub type CollapsedNodeJson = CollapsedNodeGen<Option<BigId>>;` emits `CollapsedNodeJson`.
- `HashMap`/`HashSet` fields from any crate (hashbrown here) are described as the std ones, automatically. A type alias over such a map hides it from that rewrite, so `#[wire]` on the alias also emits an `{Alias}Wire` twin, which a field of the alias type names: `#[schemars(with = "AttributeLabelsWire")]`.

## Marking a constant

`#[wire]` on a `const`, or an immutable `static`, whose type is `Serialize` exports its value into its module's file, ahead of the types: an `export const` in TypeScript and a `Final` in Python. The value is serialized when the targets are rendered, so it is whatever Rust evaluates: arithmetic over other constants, a struct literal, an `include!`. The name stays the Rust name, `///` docs become comments, and the item keeps its visibility.

```rust
/// Pinned entities one `/slice` request is answered for; the rest are dropped.
#[wire]
pub const MAX_PINS: usize = 24;
```

```ts
// Pinned entities one `/slice` request is answered for; the rest are dropped.
export const MAX_PINS = 24;
```

```python
# Pinned entities one `/slice` request is answered for; the rest are dropped.
MAX_PINS: Final = 24
```

- Arrays, slices and tuples become `[...] as const` in TypeScript and tuples in Python; a struct becomes an object literal (`as const`) or a dict, keys sorted.
- A value derived from `env_consts` differs per build environment, while the generated files are one committed set, so it is served rather than generated. So are the methodology values the site and the MCP server explain (`/v1/methodology`).

## Config

`wiretypes.toml` at the repo root names the targets, never a type:

```toml
regenerate = "make types"

[ts]
out = "src/lib/wire"

[python]
out = "wire"
style = "typeddict"
```

`style` is `typeddict` (the default) or `dataclass`; the dataclass style refuses a key Python cannot spell as a field, such as `paper-fields`.

## Output

| Rust module | TypeScript | Python |
| --- | --- | --- |
| `rankless_server::responses` | `src/lib/wire/rankless_server/responses.ts` | `wire/rankless_server/responses.py` |
| `rankless_server::consts` | `src/lib/wire/rankless_server/consts.ts` | `wire/rankless_server/consts.py` |
| `rankless_rs::user_ledger` | `src/lib/wire/rankless_rs/user_ledger.ts` | `wire/rankless_rs/user_ledger.py` |
| `rankless_expr` | `src/lib/wire/rankless_expr.ts` | `wire/rankless_expr.py` |

A module with submodules becomes a Python package (`__init__.py`), and every package directory gets an `__init__.py`. Imports between modules are relative.

Names are the Rust names in every language; there are no renames. Modules keep same-named types apart, and a file that would import two types of one name fails generation. Fields are ordered by key, with a union's discriminator first, and `///` docs become comments (TS) or docstrings (Python).

| Rust / serde | TypeScript | Python |
| --- | --- | --- |
| integers, floats | `number` | `int`, `float` |
| `Option<T>` | `T \| null` | `T \| None` |
| `Vec<T>`, `[T; N]`, `Box<[T]>` | `T[]` | `list[T]` |
| tuples | `[A, B]` | `tuple[A, B]` |
| maps | `Record<string, V>` | `dict[str, V]` |
| unit-variant enum | union of string literals | `Literal[...]` |
| tagged enum | discriminated union | one TypedDict per variant (`{Enum}{Variant}`), joined in a `type` alias |
| `serde_json::Value` | `unknown` | `Any` |

The generated directories are excluded from prettier, eslint and ruff; svelte-check and pyright still check them.

## Frontend types over the wire types

The frontend's own types derive from the generated ones rather than restating them: `ResponseNode = TreeGen<CollapsedNodeJson>`, `RelTypes = keyof RelationGroups`, `NamedEntity`, `RootedResult` (a search result with the root type a single-type list leaves implicit) in `lib/tree-types.ts`, and `LedgerKind = EventPayload['kind']` in `lib/types/ledger.ts`. The backend names entity types with plain strings; `isRootType` / `isEntityType` in `lib/constants.ts` narrow one to the site's `RootType` / `EntityType`.

## Covered boundaries

| Boundary | Rust source | Consumers |
| --- | --- | --- |
| `/v1` responses | `rankless_server/src/responses.rs`, `rankless_trees/src/{io,metrics,path_finder}.rs`, `rankless_rs/src/{metrics,biblo_var_att}.rs`, `rankless_expr` | frontend, `mcp_server` |
| ledger events (DB payloads, `ACTIVE_JSONL`) | `rankless_rs/src/user_ledger.rs` `EventPayload`, `WorkSubject`, `AuthorSubject` | the site's writers and readers, `pyscripts/ledger_ids.py` |
| `APPLIED_MANIFEST` | `rankless_rs/src/user_ledger.rs` `AppliedManifest` | the site |
| server limits, port, commit-hash length | `rankless_server/src/consts.rs` | frontend, `mcp_server`, `pyscripts` |
| `user-ledger/` file names, the external data root, the tree-parts root | `rankless_rs/src/{user_ledger,derived_ledger}.rs`, `rankless_trees/src/part_iterator.rs` | `pyscripts`, the site |

dmove's binary entity files are a separate concern: ccl-science-data reads them, and [type-audit.md](type-audit.md) checks that reader. Shapes no Rust code touches (the review lane's enrichment records and verdicts in `lib/types/review.ts`) are still mirrored by hand.

## The library

`wiretypes` and `wiretypes_macro` know nothing about rankless.

| File | Role |
| --- | --- |
| `wiretypes_macro/src/lib.rs` | `#[wire]`: the `JsonSchema` derive, the std-map rewrite, the null-dropping transform for `skip_serializing_if`, the `Wire` impl and the `inventory` registration; on a const or static, the value's registration |
| `wiretypes/src/lib.rs` | `WireType` and `WireConst` registries, `Wire` contract trait, `sync` (render, then write or check) |
| `wiretypes/src/model.rs` | Registry → one schema generator per contract → one `Shape` per registered type, one JSON value per registered constant, grouped by module |
| `wiretypes/src/shape.rs` | JSON Schema → `Shape`, the form the emitters read |
| `wiretypes/src/ts.rs`, `python.rs` | The emitters |
| `wiretypes/src/config.rs`, `output.rs` | `wiretypes.toml`; write and check over the output directories, which only ever touch files carrying the generated header |

The export runs as the `generated_types_are_current` test in `rankless_server`, the one binary that links every crate with wire types; `WIRETYPES=write` switches it from checking to writing. Another target language is one emitter module over `Shape` plus a config section.
