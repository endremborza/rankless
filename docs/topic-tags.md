# Topic tags

Two tags derived in `derive_links3` (`steps/derive_links3/topic_tags.rs`) that mark papers and
entities by their relationship to a **topic** (the finest discipline level, 4516 of them).

- **Topic creator** — a _paper_ tag: the earliest impactful paper of a topic. Forces the paper into
  the hit-paper set and renders a badge.
- **Topic dominator** — an _entity_ tag (authors / institutions / countries / sources): the entity
  captures a large share of a topic's incoming citations. Renders a "Topic Leadership" section.

## MVP scope (implemented)

### Topic creator

For each topic, the earliest-published paper **assigned that topic** (tiebroken by citations) that
clears an impact floor, restricted to topics whose first paper is published in
`CREATOR_CUTOFF_YEAR` or later. Such a paper qualifies as a hit paper even if its citations alone
would not.

- Topic membership uses **any** assignment (not the primary topic — see [extensions](#future-extensions)).
- Stored as the `HitPapersCreatedTopic` attribute next to the other `hit-papers-*` data; surfaced on
  the hit-paper payload as `PaperOut.createdTopic` → badge in `PaperRainbow.svelte`.

### Topic dominator (impact only)

Per entity type E ∈ {Authors, Institutions, Countries, Sources} and topic T:

```
share(E, T) = citation edges from T-papers landing on E's works
            / all citation edges from T-papers          (edge-weighted)
```

E dominates T when `share(E, T) >= DOM_PCT_<TYPE>` and T has at least `MIN_DOM_TOPIC_PAPERS` papers.
A country naturally captures a far larger share than a single author, so the threshold is **per
entity type**. Subfields and topics-as-entity are excluded.

- The denominator is computed once over all citing-works' topics; numerators accumulate per entity
  in a single pass over each type's works (`emit_dominators`).
- Stored per entity via `TopicDominatorMarker` (variable-length list of `(topic, share-in-basis-points)`).
- Loaded into `PeerAux` for the four types; surfaced as `ViewResult.dominatedTopics` →
  `DominatedTopics.svelte`.

## Tuning constants

All in `topic_tags.rs` (env-independent for now):

| Constant                | Value | Meaning                                            |
| ----------------------- | ----- | -------------------------------------------------- |
| `CREATOR_CUTOFF_YEAR`   | 2000  | Min first-paper year for a topic to be eligible    |
| `MIN_CREATOR_CITATIONS` | 50    | Impact floor for a creator paper (≥ `MIN_NEEDED`)  |
| `MIN_DOM_TOPIC_PAPERS`  | 50    | Skip topics too small for a share to be meaningful |
| `DOM_PCT_AUTHORS`       | 0.02  | Cited-share threshold, authors                     |
| `DOM_PCT_INSTITUTIONS`  | 0.10  | Cited-share threshold, institutions                |
| `DOM_PCT_SOURCES`       | 0.20  | Cited-share threshold, sources                     |
| `DOM_PCT_COUNTRIES`     | 0.35  | Cited-share threshold, countries                   |

After tuning, re-run the pipeline from `derive_links3` and restart the server.

## Future extensions

- **Primary topic.** Add a `WorkPrimaryTopic` attribute in `a2_init_atts` and key the creator off
  the paper's single highest-score topic, so "creator" means originator of the paper's _main_ topic.
- **Producer dominance.** Second dominator mechanism: share of a topic's _papers_ produced by E
  (vs. the current citation share). Tag both with a `kind` discriminator.
- **Threshold calibration.** Set `DOM_PCT_*` / `MIN_DOM_TOPIC_PAPERS` from inspected data; consider
  `RANKLESS_ENV`-relative floors for smaller datasets.
- **Topic-centric views.** Reverse maps (topic → creator paper, topic → dominators) for a topic page.
- **Performance.** Fold the dominator numerators into `derive_links2`'s existing per-entity citer
  walk to avoid the extra passes; parallelize the per-type emission.
- **Naming.** Settle user-facing wording (currently "originated …" / "Topic Leadership").
