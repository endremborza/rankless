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

---

## Untapped parallelism opportunities

Identified spots where additional parallelism could reduce pipeline step wall time.

### `derive_links1`: parallel `InvertedMultiLink` construction

`main` builds three inverted link structures sequentially:

```rust
InvertedMultiLink::<WorkReferences>::from_stowage(&stowage).stow_as_work_link(...)
InvertedMultiLink::<WorkTopics>::from_stowage(&stowage).stow_as_work_link(...)
InvertedMultiLink::<WorkSources>::from_stowage(&stowage).stow_as_work_link(...)
```

Each `from_stowage` call is read-only on stowage (`&stowage`) and produces an independent
in-memory `Box<[Box<[…]>]>` via a full `multi_inverter` pass over a different entity
attribute.  The three *build* phases can run concurrently with `std::thread::scope`; the
subsequent `stow_as_work_link` writes remain sequential.

Pattern:
```rust
let (wr, wt, ws) = std::thread::scope(|s| {
    let h1 = s.spawn(|| InvertedMultiLink::<WorkReferences>::from_stowage(&stowage));
    let h2 = s.spawn(|| InvertedMultiLink::<WorkTopics>::from_stowage(&stowage));
    let h3 = s.spawn(|| InvertedMultiLink::<WorkSources>::from_stowage(&stowage));
    (h1.join().unwrap(), h2.join().unwrap(), h3.join().unwrap())
});
wr.stow_as_work_link(&stowage, "works-citing");
...
```

The existing `par_join!` macro does not return values, so `std::thread::scope` is the right
primitive here.  Expected gain: ~3× for this phase (concurrent reads from three separate
files).

---

### `derive_links3`: parallel benchmark computations

After the `para_multi_gen_run!(work_count, …)` phase, three benchmark maps are computed
sequentially:

```rust
let year_bms = compute_year_bms(&w_years, &cc_interface);
let sf_bms   = compute_sf_bms(&w_sfs.0, &cc_interface);
let sf_year_bms = compute_sf_year_bms(&w_sfs.0, &w_years, &cc_interface, &year_bms);
```

`compute_year_bms` and `compute_sf_bms` are fully independent (read-only over the same
input slices).  `compute_sf_year_bms` depends on `year_bms` but not `sf_bms`.  Two-phase
approach:

1. `std::thread::scope`: `compute_year_bms` ∥ `compute_sf_bms`
2. `compute_sf_year_bms`

Each benchmark function iterates all works once; parallelising the first two halves the
wall time of this preparatory phase.

---

### `derive_links3`: parallel `entity_coords_filter!` calls

Five coord-filter macro invocations run sequentially after hit-paper selection:

```rust
entity_coords_filter!(starc, Institutions, |..| true);
entity_coords_filter!(starc, Subfields, |..| true);
entity_coords_filter!(starc, Countries, |..| true);
entity_coords_filter!(starc, Sources, |i, c, p| { p > 10 && … });
let (author_coords, author_filter) = entity_coords_filter!(starc, Authors, |..| …);
compute_author_peers(&starc, &author_coords, &author_filter);
```

Each call reads entity-specific data from stowage (different entity types, no contention)
and writes two attributes via `ditf` (to disjoint entity namespaces).  The first four are
completely independent and can be moved into a `par_join!` block.  Authors must remain
separate because its result feeds `compute_author_peers`.

**Constraint**: `ditf` calls `declare_iter`, which writes to stowage via internal locking.
If `Stowage` write methods are mutex-protected (as they appear to be from the `Arc` usage
in other steps), parallelisation is safe.

---

### `derive_links5`: parallel `write_all_sem_ids`

`write_all_sem_ids` calls five sequential writes:

```rust
self.write_semantic_id::<Authors>();
self.write_semantic_id::<Institutions>();
self.write_semantic_id::<Sources>();
self.write_semantic_id::<Subfields>();
// countries — inline special case
```

Each call reads a separate entity's CSV files from disk (IO-bound) and writes a disjoint
semantic-id attribute.  The four typed calls are perfect candidates for
`para_multi_gen_run!`; the Countries special case runs after.  This step is likely the
most impactful to parallelize because CSV reading dominates and the four entities' files
don't overlap.

---

### `derive_links4`: sharded author hit-paper accumulation

The O(H × R × A) loop filling `direct[author]` and `once_removed[author]` is single-threaded.
The write target is indexed by `aid_u` (author id), so a **shard-by-author** strategy is
lock-free:

- Partition the author ID space into T equally-sized ranges.
- Each thread gets its own slice of `direct` and `once_removed` and iterates *all* hit
  papers, writing only to authors in its range.
- All reads (`wor_refs`, `w2a`, `parc`) are already immutable slices.
- No merge step: each author is owned by exactly one thread; the thread outputs can be
  concatenated trivially.

The final `.zip().map().unzip()` is also per-author with no cross-author deps, so it can
be split across threads by the same author-range partition.
