# Type generation (`wiretypes`)

Rust is the one language cross-language shapes and constants are written in. Every struct or enum that crosses a language boundary, and every constant another language needs, carries `#[wire]`, and [`wiretypes`](https://github.com/endremborza/wiretypes) (from crates.io) renders it as TypeScript and Python, one file per Rust module. The generated files are committed and never edited by hand. How to mark a type or a constant, the config, and how each Rust shape is spelled in each language: the crate's README.

```bash
make types        # rewrite src/lib/wire/ and wire/ from the Rust types (also part of make format)
make check-types  # fail when they are stale (part of make check)
```

The export runs as the `generated_types_are_current` test in `rankless_server`, the one binary that links every crate with wire types; `make types` runs it with `WIRETYPES=write`. A change to the library is made and released in its own repository; rankless takes it by bumping the version in the root `Cargo.toml` and running `make types`.

## Here

`wiretypes.toml` at the repo root renders TypeScript into `src/lib/wire` and Python TypedDicts into `wire`, both excluded from prettier, eslint and ruff and still checked by svelte-check and pyright.

| Rust module | TypeScript | Python |
| --- | --- | --- |
| `rankless_server::responses` | `src/lib/wire/rankless_server/responses.ts` | `wire/rankless_server/responses.py` |
| `rankless_server::consts` | `src/lib/wire/rankless_server/consts.ts` | `wire/rankless_server/consts.py` |
| `rankless_rs::user_ledger` | `src/lib/wire/rankless_rs/user_ledger.ts` | `wire/rankless_rs/user_ledger.py` |
| `rankless_expr` | `src/lib/wire/rankless_expr.ts` | `wire/rankless_expr.py` |

- The ledger subjects are records the site writes and Rust reads leniently: they derive both serde sides, and the fields Rust can do without carry `#[serde(default)]`, so the generated type is what a writer must produce.
- The maps are hashbrown's, which `#[wire]` describes as the std ones. `AttributeLabels`, an alias over one, is named in its fields as `#[schemars(with = "AttributeLabelsWire")]`.
- `CollapsedNodeJson = CollapsedNodeGen<Option<BigId>>` registers the generic node per instantiation.
- `METHODOLOGY` (it fills its texts) and `TREE_SPECS` (it collects every tree's spec) are `LazyLock` statics, exported as the values they build.
- The site and the MCP server read what Rust defines from these files, never from an endpoint, so a value is fixed when the frontend is built.
- The env's pipeline thresholds (`env_consts`, written by `rankless_rs/build.rs` from `RANKLESS_ENV`) are the one module whose generated files differ per env. They are committed with the `full` env's values, the ones the served data is filtered with: `refresh-data` runs `make types` on the primary data box and `commit-artifacts` commits them with the rest of a release. A dev box skip-worktrees them like `env_consts.rs`, and its `make types` rewrites them for its own env, so `make check-types` compares like with like. Between a threshold change and the next recalc, `make check-types` on the primary data box fails; the committed values are still the ones the served data was built with.

## Frontend types over the wire types

The frontend's own types derive from the generated ones rather than restating them: `ResponseNode = TreeGen<CollapsedNodeJson>`, `RelTypes = keyof RelationGroups`, `NamedEntity`, `RootedResult` (a search result with the root type a single-type list leaves implicit) in `lib/tree-types.ts`, and `LedgerKind = EventPayload['kind']` in `lib/types/ledger.ts`. The backend names entity types with plain strings; `isRootType` / `isEntityType` in `lib/constants.ts` narrow one to the site's `RootType` / `EntityType`.

## Covered boundaries

| Boundary | Rust source | Consumers |
| --- | --- | --- |
| `/v1` responses | `rankless_server/src/responses.rs`, `rankless_trees/src/{io,metrics}.rs`, `rankless_rs/src/{metrics,biblo_var_att}.rs`, `rankless_expr` | frontend, `mcp_server` |
| the methodology and the tree specs (`METHODOLOGY`, `TREE_SPECS`) | `rankless_server/src/responses.rs` | frontend, `mcp_server`, `pyscripts` |
| the env's pipeline thresholds | `rankless_rs/src/env_consts.rs` (from `rankless_rs/build.rs`) | frontend, `mcp_server` |
| ledger events (DB payloads, `ACTIVE_JSONL`) | `rankless_rs/src/user_ledger.rs` `EventPayload`, `WorkSubject`, `AuthorSubject` | the site's writers and readers, `pyscripts/ledger_ids.py` |
| `APPLIED_MANIFEST` | `rankless_rs/src/user_ledger.rs` `AppliedManifest` | the site |
| server limits, port, commit-hash length | `rankless_server/src/consts.rs` | frontend, `mcp_server`, `pyscripts` |
| the `/v1` routes (`API_ROUTES`) | `rankless_server/src/routes.rs` | the access-log report (`ramore.toml`) |
| `user-ledger/` file names, the external data root | `rankless_rs/src/{user_ledger,derived_ledger}.rs` | `pyscripts`, the site |

dmove's binary entity files are a separate concern: ccl-science-data reads them, and [type-audit.md](type-audit.md) checks that reader. Shapes no Rust code touches (the review lane's enrichment records and verdicts in `lib/types/review.ts`) are still mirrored by hand.
