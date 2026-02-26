# Metaprogramming & Make Pipeline

## What it does

Each pipeline step in `rankless_rs/src/steps/` is **both** a data processor and a code emitter.
When run, a step processes OpenAlex CSV data and writes a corresponding `.rs` file into `rankless_rs/src/gen/`.
That generated file contains entity/attribute/link definitions (impl blocks, type aliases, trait impls) that are
dataset-specific and required by subsequent steps and the server.

Steps must run in order: `a1_entity_mapping → a2_init_atts → derive_links1 → … → derive_links5`.
Each step's generated file becomes a compile-time dependency for the next step.

---

## `dmove_macro` — two distinct roles

The crate has two independent parts:

**`src/lib.rs` — proc-macro library**
Provides procedural macros used in the steps themselves:
- `#[derive_meta_trait]` — generates a companion `*TraitMeta` struct with a `meta()` method that returns a `MetaElem` (the Rust source string for a trait impl, emitted into gen/)
- `def_me_struct!` / `def_srecs!` / `impl_subs!` / `impl_fbarrs!` / `impl_stack_basees!` — generate boilerplate for tree folding, byte serialization, and stack-basis impls
- `#[derive_tree_getter]` — derives `TreeGetter` for entity modules

**`src/main.rs` — orchestration binary (`dmove-macro`)**
Drives the build pipeline; knows nothing about entity definitions.
Built with `cargo build --release -p dmove-macro` → `./target/release/dmove-macro`.

---

## Orchestration commands

### `make-setup [--fast]`

Reads `steps/` to discover step names, then writes a `Makefile` (or `Makefile.fast` with `--fast`).
Each Makefile target is a gen file, with the previous gen file as a dependency, giving correct incremental ordering.

```
./target/release/dmove-macro -p rankless_rs make-setup
./target/release/dmove-macro -p rankless_rs make-setup --fast
```

### `pre-build -s <step>`

Called at the start of each Makefile target. Modifies source files so the crate compiles as if only steps up to (and including) `<step>` exist:
- Rewrites `lib.rs`: replaces `mods_as_comms!(...)` with only the steps up to the current one
- Rewrites `steps/mod.rs`: `pub mod` declarations up to `<step>`
- Rewrites `gen/mod.rs`: `pub mod` declarations for all *previously completed* gen files (not the current one yet)

### `post-run -s <step>`

Called after a step finishes running. Adds the newly generated file to `gen/mod.rs`.

---

## Makefile structure

Each step target looks like:

```makefile
rankless_rs/src/gen/derive_links3.rs: rankless_rs/src/steps/derive_links3.rs rankless_rs/src/gen/derive_links2.rs
	./target/release/dmove-macro -p rankless_rs pre-build -s derive_links3
	cargo build -p rankless-rs --release
	cargo run -p rankless-rs --release -- derive_links3
	./target/release/dmove-macro -p rankless_rs post-run -s derive_links3
```

Make's dependency tracking means touching a step file (or its gen dependency) re-triggers only that step and all downstream ones.

---

## Fast (debug) pipeline

The release profile (`codegen-units=1`, `lto=true`, `opt-level=3`) makes each compile step slow.
For iterating on step logic — where you only care about generating the `.rs` files, not runtime speed — use the fast pipeline.

**Profile** (`Cargo.toml`):
```toml
[profile.gen-debug]
inherits = "dev"   # opt-level=0, codegen-units=256, no LTO, incremental=true
```

**Generate `Makefile.fast`:**
```sh
./target/release/dmove-macro -p rankless_rs make-setup --fast
```

Each fast target uses:
```makefile
	RUSTFLAGS="" cargo build -p rankless-rs --profile gen-debug
	RUSTFLAGS="" cargo run -p rankless-rs --profile gen-debug -- derive_links3
```

`RUSTFLAGS=""` overrides any env-level rustflags (highest precedence in Cargo's lookup order).

**Run a single step:**
```sh
make -f rankless_rs/Makefile.fast rankless_rs/src/gen/derive_links3.rs
```

**Run the full pipeline:**
```sh
make -f rankless_rs/Makefile.fast
```
