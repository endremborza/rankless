# Peers

How the pipeline picks an entity's peers, and how institution peers are checked against hand-labelled sets. Code: `rankless_rs/src/peers.rs` (the search and the distance primitives), `rankless_rs/src/steps/derive_links3/peer_ctx.rs` (one `PeerCalculator` per root type; hit papers have theirs in `derive_links4.rs`), `rankless_rs/src/peer_sets.rs` and `rankless_trees/src/bin/peer_report.rs` (the check).

## The search

`compute_peers` runs the same four stages for every root type and stores the `N_PEERS` nearest entities per entity (`<root>-peers`, read by `/v1/peers`):

1. **Embedding.** `get_embedding_basis` gives every entity a point; the entities that pass the page filter go into KD-trees.
2. **Candidates.** The `N_CANDIDATES` points nearest to the query. With `N_PARTITIONS` above one, the filtered entities, ordered by work count, are cut into that many equal partitions by position, each with its own tree, and a query reads its own partition and the one on either side: size decides who can be a candidate at all. Cutting by position keeps the partitions equal where many entities share a work count.
3. **Re-rank.** `final_distances` scores the query's whole candidate set at once. By default it is `pair_distance` per candidate; institutions add the terms they put on one scale over the set.
4. **Group discount.** Candidates that share the query's `group_key` have `group_discount(rank)` taken off their distance, `rank` being their place among the same-group candidates. Only institutions have a group, their country.

| Root | Embedding | Partitions | Distance |
| --- | --- | --- | --- |
| Institutions | PCA of the square roots of the citing-subfield shares (`compute_pca` with `RowScale::SqrtShare`) | by work count | `W_PEER_SF` x standardized `sf_log_dist` + `W_PEER_RATE` x standardized `sf_rate_dist` + `W_PEER_GEO` x `geo_dist`, then the same-country discount `W_PEER_COUNTRY` x `W_PEER_COUNTRY_DECAY`^rank |
| Sources | PCA of the log citing-subfield counts (`compute_pca` with `RowScale::LogCount`) | by work count | `W_PEER_SF` x `sf_log_dist` + `W_PEER_RATE` x `sf_rate_dist` |
| Authors | log-count PCA | none | `W_PEER_SF` x `sf_log_dist` + `W_PEER_TEMPORAL` x the squared difference of the career centroids, standardized over the filtered authors |
| Subfields, countries | log-count PCA | none | `W_PEER_SF` x `sf_log_dist` |
| Hit papers | the citation count | none | the squared difference of the log citation counts |

The one signal behind every profile is `CitSubfieldsArrayMarker` (`derive_links2`): per entity, the subfields of the works that cite it.

## The pieces

- **Log-count embedding** (`RowScale::LogCount`). PCA over the log of each count, every component scaled to unit variance. Its first component is size.
- **Share embedding** (`RowScale::SqrtShare`). PCA over the square root of each count's share of the row, the Hellinger transform: it carries no size, a zero needs no pseudo-count, and the components keep their variance, so the distance between two points approximates the Hellinger distance between the two profiles. For institutions size is left to the partitions.
- **`sf_log_dist`.** Over the query's top `N_PEER_SF_DIMS` subfields by specialization (`compute_top_sfs`: citing count over field size to the `SPEC_BETA`), the weighted squared difference of the two entities' log citing counts: similar volume in the fields the query stands for. It reads only the query's top subfields, so it is not symmetric.
- **`sf_rate_dist`.** Over the same subfields, the squared difference of their shares of all citing counts.
- **`geo_dist`.** The great-circle distance in km, squashed by `1 - exp(-km / PEER_GEO_SCALE_KM)`: 0 at the same place, close to 1 from a few `PEER_GEO_SCALE_KM` on, so two far candidates differ little however far apart they are. An institution without coordinates is at 1 from every place, so for a query without them geography ranks no candidate above another.
- **`standardize`.** The z-scores of the values present, an absent one scoring 0. `sf_log_dist` and `sf_rate_dist` have no scale of their own (one runs to tens, the other stays under a tenth), so for institutions each is standardized over the query's candidates before it is weighted, and `W_PEER_*` say how much a term counts. `geo_dist` is bounded already and is not standardized: over a candidate set that is far away but for a few, the few would sit many deviations out and decide the ranking alone.

## Checking institution peers

`rankless_rs/static/peer-sets.csv` (`set,openalex_id,name`) holds hand-labelled sets of institutions of one type each: business schools, technical universities, medical universities, liberal arts colleges, physics laboratories, pharmaceutical and technology companies, central banks and so on. A member's peers are expected among the other members.

```sh
make peer-report                              # the table over $OA_ROOT
make peer-report ARGS=business-schools        # that set's members, each with its peers, members marked *
```

The report reads the stored peers of a built root and writes nothing, so it scores the root as it is, before and after a pipeline change. Its binary has to be built from the generated types of the root it reads, like every reader of a root. Per set and in total:

- **scored/labelled**: the members the root holds with peers, of those labelled. Only they are scored.
- **P@`N_PEERS`**: the share of the scored members' peer slots that hold another scored member of the set.
- **ceiling**: what a ranking that fills every slot it can with scored members would reach, so never below the precision; below 1 only for a set of at most `N_PEERS` scored members.
- **same country**: the share of the scored members' peers in the member's own country, the measure of how far geography decides.

Two limits on reading it:

- No set lists its whole type, so a precision is a lower bound and reads against another run's over the same sets, not against 1.
- A test-set root (`make_test_dataset.py`) is built from the works of a few seed institutions. Every other institution is in it only through the papers it shares with a seed, about a hundredth of its works: its work count is its collaboration with the seeds and its profile is that slice. The table there shows gross effects (geography against field), never whether a weight is right; that takes a full root.
