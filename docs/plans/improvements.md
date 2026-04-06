# Untapped Parallelism Opportunities

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
