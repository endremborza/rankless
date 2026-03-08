# Parallelization in Rankless

## Overview

The codebase uses custom parallelization built on `std::thread`, `crossbeam-channel`, and
`std::sync` primitives. There is no rayon or other parallel iterator library. Tokio appears
only in the HTTP server for async I/O, not for CPU work.

All core parallel helpers live in **`dmove/src/para.rs`** and are re-exported from the `dmove`
crate. Steps and the server import them from there.

---

## Core Primitives (`dmove/src/para.rs`)

### `Worker<T>` trait

The primary abstraction for parallel batch processing.

```rust
pub trait Worker<T: Send>: Sized + Sync {
    fn proc(&self, input: T);          // called once per item
    fn post(self) -> Self { self }     // called after all items processed
    fn para<I: Iterator<Item = T>>(self, in_v: I) -> Self;   // uses available_parallelism()
    fn para_n<I: Iterator<Item = T>>(self, in_v: I, n: usize) -> Self;
}
```

`para` / `para_n` call `para_run`, which:
1. Creates a `crossbeam_channel::bounded` channel (capacity = `n_threads * 100`).
2. Spawns N scoped threads, each running a receive-loop (`subf`).
3. Sends all items then sends N `None` sentinels for shutdown.
4. Joins all threads.

**Used in**: `a2_init_atts.rs` for `WorkAttWriter`, `WorkBiblioWriter`, `ShipRelWriter`,
`GenObjAttWorker` — batch CSV row processing.

### `para_multi_gen_run!` macro

Spawns one thread per concrete type parameter, all running the same generic function.

```rust
para_multi_gen_run!(fn_name, TypeA, TypeB, TypeC; arc_arg)
// expands to: spawn thread for fn_name::<TypeA>(&arc_arg), same for B, C; join all
```

**Used in**: `derive_links3::main` (work_count for 6 entity types), `main.rs` (server
initialization for entity state and node updates).

### `AcTuple<T>` and condvar helpers

`type AcTuple<T> = Arc<(Mutex<T>, Condvar)>` — used for one-shot result notification between
threads.

- `set_and_notify(cvp, val)` — set value and wake waiters
- `wait_for_data(cvp)` — block until `Option<T>` is `Some`, then take the value
- `wait_for_data_copy(cvp)` — same but for `Copy` types

**Used in**: `rankless_trees/src/io.rs` for the per-request response channel in
`TreeRunManager`.

---

## Usage by Module

### `rankless_rs/src/steps/a2_init_atts.rs`

Implements multiple `Worker<T>` structs for parallel CSV ingestion.  Each worker holds a
`Mutex<Box<[T]>>` (or similar) for accumulating results, then `post()` extracts them.  Thread
count = `available_parallelism()`.

### `rankless_rs/src/steps/a1_entity_mapping.rs`

Ad-hoc fork-join: spawns `std::thread::spawn` closures into a `Vec<JoinHandle>` for
independent entity-mapping tasks (field/subfield/domain IDs, work/institution/source/topic
IDs, author filter creation), then joins all at the end.

### `rankless_rs/src/steps/derive_links2.rs`

`CdManager` struct: holds `Arc<CiteDeriver>` + `Vec<JoinHandle>`.  `send(f, arg)` clones
the Arc and spawns a thread; `join()` drains the handle vec.  Used to fire off 5 independent
`CiteDeriver` methods (author_paths, cite_count for Institutions/Countries/Subfields/Topics)
simultaneously.

> There is a `//TODO: this could be replaced with the parallel macro` comment on this struct.

### `rankless_rs/src/steps/derive_links3.rs`

Uses `para_multi_gen_run!` for `work_count` across 6 entity types.  The main
`compute_author_peers` loop is **serial** — see parallelization suggestion below.

### `rankless_rs/src/common.rs` and `rankless_trees/src/interfacing.rs`

Both contain macros (`make_interface_struct!` / `make_interfaces!`) that spawn one thread per
interface field, each cloning `Arc<Stowage>`, loading its data independently, then joining in
struct initialization order.  These two macros are nearly identical (there is even a
`//TODO: wet with interfacing` comment in `common.rs`).

### `rankless_trees/src/io.rs` — `TreeRunManager`

Persistent thread pool for serving tree queries.  `N_THREADS = 16` long-lived workers share
a `BasisCvp = Arc<(Mutex<VecDeque<BasisQuElem>>, Condvar)>` work queue.  Each request gets
its own `ResCvp` (response condvar); the worker notifies it when the tree is computed.
Shutdown via `None` sentinel, then join.

### `rankless_server/src/main.rs`

- Tokio runtime with 16 async worker threads (for HTTP concurrency, not CPU work).
- `TreeRunManager` with `N_THREADS = 16` for parallel tree queries.
- `para_multi_gen_run!` during startup for entity state initialization.

---

## Cleanup and Unification Suggestions

### 1. Remove `CdManager`, use `para_multi_gen_run!`

`CdManager` in `derive_links2.rs` is a weaker version of `para_multi_gen_run!`.  The TODO
comment already flags this.  The five `CiteDeriver` methods each take a different argument
type, so they need individual `Arc::clone` + spawn calls, but `para_multi_gen_run!` handles
that pattern exactly.  Replace `CdManager::send` + `join` with a single macro call.

### 2. Deduplicate `make_interface_struct!` / `make_interfaces!`

The two macros share the same structure: spawn one thread per field, join in a struct
literal.  The only differences are field-category syntax (`>` vs `=>` etc.) and the fact
that `make_interfaces!` has a fifth category (locators).  A single macro in `dmove` (or a
shared `common` crate) with an optional fifth arm would eliminate the duplication.

### 3. Consolidate ad-hoc thread spawning in `a1_entity_mapping.rs`

The fork-join over independent mapping tasks is conceptually `para_multi_gen_run!` with
different function signatures.  Where the functions have uniform `fn(&Arc<Stowage>)` signatures
they can be expressed as a macro call.  For the heterogeneous closures, consider a small
`par_join!(expr1, expr2, ...)` helper in `dmove::para` that spawns each expression in a
scoped thread and joins them.

### 4. `par_join!` helper (new)

A lightweight macro that matches the fork-join pattern used in both `a1_entity_mapping.rs`
and the interface-loading macros:

```rust
// proposed addition to dmove/src/para.rs
macro_rules! par_join {
    ($($expr:expr),+ $(,)?) => {{
        std::thread::scope(|s| {
            let handles = [$( s.spawn(|| $expr) ),+];
            handles.map(|h| h.join().expect("thread panicked"))
        })
    }};
}
```

This replaces the `Vec<JoinHandle>` pattern in `a1_entity_mapping.rs` and could be used
inside the interface-loading macros instead of repeating `Arc::clone` + `thread::spawn` by
hand.

### 5. Keep `Worker<T>` as the default for batch work

The `Worker<T>` + `para_run` pattern (bounded channel, scoped threads, sentinel shutdown) is
the right model for all batch-processing loops.  New parallel work that processes an iterator
of items should prefer implementing `Worker<T>` rather than rolling another ad-hoc
`Vec<JoinHandle>`.

---

## Parallelizing Peer Selection in `derive_links3`

### Current code (`compute_author_peers`)

```
for &(dm_id, ref_coord) in &entries {  // O(n) heroes
    compute window [lo, hi] by rank
    for i in lo..hi {                  // O(n * CANDIDATE_PCTILE) candidates per hero
        compute peer_sq_dist(...)
    }
    write peers[dm_id]
}
```

With ~6M filtered authors and a 10% window (CANDIDATE_PCTILE_LOW + HIGH), each hero scans
~600k candidates.  This is the most expensive serial loop in the step.

### Why it parallelizes cleanly

- Each hero reads from `entries`, `cit_sfs`, `dm_to_rank` (all immutable after setup).
- Each hero writes to `peers[dm_id]`; `dm_id` values are unique across heroes, so no
  write conflicts.
- Per-item work is large (inner scan + distance computation), so channel overhead is
  negligible.

### Suggested implementation using `Worker<T>`

```rust
struct PeerWorker {
    entries:    Arc<Vec<(usize, [f64; 2])>>,
    cit_sfs:    Arc<Box<[AuthorCitSfArr]>>,
    dm_to_rank: Arc<Vec<usize>>,
    sf_weights: [f64; N_PEER_SF_DIMS],
    n:          usize,
    peers:      Arc<Mutex<Vec<[AuthorId; N_PEERS]>>>,
}

impl Worker<(usize, [f64; 2])> for PeerWorker {
    fn proc(&self, (dm_id, ref_coord): (usize, [f64; 2])) {
        let rank = self.dm_to_rank[dm_id];
        let lo = ((rank as f64 - self.n as f64 * CANDIDATE_PCTILE_LOW) as isize).max(0) as usize;
        let hi = ((rank as f64 + self.n as f64 * CANDIDATE_PCTILE_HIGH + 1.0) as usize).min(self.n);
        let hero_arr = &self.cit_sfs[dm_id];
        let top_sfs = top_k_sf_indices(hero_arr);
        let mut heap: BinaryHeap<PeerCandidate> = BinaryHeap::new();
        for i in lo..hi {
            let (cand_dm_id, cand_coord) = self.entries[i];
            if cand_dm_id == dm_id { continue; }
            let dist_sq = peer_sq_dist(
                ref_coord, cand_coord, hero_arr,
                &self.cit_sfs[cand_dm_id], &top_sfs, &self.sf_weights,
            );
            if heap.len() < N_PEERS || dist_sq < heap.peek().unwrap().dist_sq {
                if heap.len() >= N_PEERS { heap.pop(); }
                heap.push(PeerCandidate { dist_sq, dm_id: cand_dm_id as AuthorId });
            }
        }
        let mut out = [AuthorId::default(); N_PEERS];
        for (i, pc) in heap.into_sorted_vec().into_iter().enumerate() {
            out[i] = pc.dm_id;
        }
        self.peers.lock().unwrap()[dm_id] = out;
    }
}
```

Then in `compute_author_peers`, replace the serial loop with:

```rust
let peers_out = Arc::new(Mutex::new(vec![[AuthorId::default(); N_PEERS]; coords.len()]));
PeerWorker {
    entries:    Arc::new(entries.clone()),
    cit_sfs:    Arc::new(cit_sfs),
    dm_to_rank: Arc::new(dm_to_rank),
    sf_weights,
    n,
    peers:      peers_out.clone(),
}.para(entries.into_iter());
let peers = Arc::try_unwrap(peers_out).unwrap().into_inner().unwrap();
```

### Notes on the mutex

Lock contention is minimal: each `proc` call holds the lock only for a single array-slot
write after completing the full inner scan + heap construction.  If profiling shows
contention is a real bottleneck, the alternative is to have each thread accumulate its own
`Vec<(usize, [AuthorId; N_PEERS])>` and merge after `para()` completes via `post()` —
but that optimization is likely unnecessary.

### Complexity

Serial: O(n × window).  Parallel with K threads: O(n × window / K).  With K =
`available_parallelism()` (typically 8–32), expect 8–32× speedup on this step.
