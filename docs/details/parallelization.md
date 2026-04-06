# Parallelization in Rankless

## Core primitives (`dmove/src/para.rs`)

All parallel helpers live here and are re-exported from the `dmove` crate.

### `Worker<T>` — batch work queue

```rust
pub trait Worker<T: Send>: Sized + Sync {
    fn proc(&self, input: T);
    fn para<I: Iterator<Item = T>>(self, in_v: I) -> Self;   // uses available_parallelism()
    fn para_n<I: Iterator<Item = T>>(self, in_v: I, n: usize) -> Self;
}
```

`para` / `para_n` create a `crossbeam_channel::bounded` work queue, spawn N scoped threads
(each running a receive loop), stream items in, send `None` sentinels for shutdown, join.

**Used in**: `a2_init_atts.rs` for parallel CSV ingestion workers; `derive_links3.rs` for
parallel peer selection (`PeerWorker`).

### `par_join!` — fork-join for heterogeneous closures

```rust
par_join!(
    { let x = shared.clone(); move || work_a(x) },
    { let y = shared.clone(); move || work_b(y) },
    ...
)
```

Spawns each expression as a scoped thread, joins all.  Used in `derive_links2.rs` to run the
five `CiteDeriver` methods concurrently.

### `para_multi_gen_run!` — one thread per type parameter

```rust
para_multi_gen_run!(fn_name, TypeA, TypeB, TypeC; arc_arg)
```

Spawns `fn_name::<T>(&arc_arg.clone())` for each `T`, joins all.  Used in
`derive_links3::main` (work_count for 6 entity types) and server startup.

### `AcTuple<T>` + condvar helpers

`type AcTuple<T> = Arc<(Mutex<T>, Condvar)>` — one-shot result notification.

- `set_and_notify` / `wait_for_data` / `wait_for_data_copy`

Used in `rankless_trees/src/io.rs` for per-request response signalling in `TreeRunManager`.

---

## Interface loading (`make_interface_struct!` in `rankless_rs/src/common.rs`)

A single `#[macro_export]` macro generates a struct whose fields are loaded in parallel
threads at construction time.  Two call forms:

- **4-category** `(IT, e...; f...; v...; m...)` — backward-compatible, delegates to 5-cat
- **5-category** `(IT, e...; f...; v...; loc...; m...)` — also loads `Arc<Locators<E>>` fields
  via `rankless_rs::common::get_locator`

`rankless_trees/src/interfacing.rs` calls the 5-category form via `make_interfaces!`, which
uses `rankless_rs::make_interface_struct!(Interfaces, ...)` for struct generation and then
adds `impl Getters` accessor methods and trait impls.  No duplicated loading code.

---

## Usage by module

| File | Mechanism | What is parallelized |
|---|---|---|
| `rankless_rs/steps/a2_init_atts.rs` | `Worker<T>::para()` | CSV row processing for works, biblios, authorship |
| `rankless_rs/steps/a1_entity_mapping.rs` | `std::thread::spawn` + `Vec<JoinHandle>` | Independent entity ID mapping tasks |
| `rankless_rs/steps/derive_links2.rs` | `par_join!` | 5 `CiteDeriver` methods (author paths, cite counts by entity type) |
| `rankless_rs/steps/derive_links3.rs` | `para_multi_gen_run!` + `Worker<T>::para()` | Work counts per entity type; author peer selection |
| `rankless_rs/src/common.rs` | `make_interface_struct!` | Parallel data loading at server startup |
| `rankless_trees/src/io.rs` | Persistent pool (`VecDeque` + `Condvar`) | Tree query serving; 16 threads |
| `rankless_server/src/main.rs` | `para_multi_gen_run!` + Tokio (16 workers) | Entity state init; HTTP request handling |

---

## Notes

- No rayon; custom threading for precise control.
- `a1_entity_mapping.rs` still uses ad-hoc `Vec<JoinHandle>` — fits `par_join!` if
  refactored, but the work is simple enough that the current form is fine.
- `TreeRunManager` in `io.rs` is intentionally a persistent pool (long-lived workers share
  memory-mapped data); it does not use `Worker<T>` which is for one-shot batch tasks.
