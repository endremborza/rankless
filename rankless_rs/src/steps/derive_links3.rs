use std::{
    cmp::Ordering,
    collections::BinaryHeap,
    ops::AddAssign,
    sync::{Arc, Mutex},
};

use kd_tree::{KdPoint, KdTree};
use nalgebra::{DMatrix, SymmetricEigen};

use crate::{
    common::{
        init_empty_slice, reverse_id, CitSubfieldsArrayMarker, CoordinateMarker, MainWorkMarker,
        NameMarker, PageFilterMarker, PeerAuthorMarker, YearlyPapersMarker,
    },
    env_consts::FINAL_YEAR,
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{AuthorNobels, WorkDois, WorkTopics, WorkYears, WorksNames},
        derive_links1::{WorkFilteredAuthors, WorkSubfields},
        derive_links2::{AuthorWorks, SourceStats},
    },
    steps::a1_entity_mapping::{YearInterface, Years},
    CiteCountMarker, QuickestBox, QuickestVBox, ReadIter, Stowage, WorkCountMarker,
};
use dmove::{
    para::Worker, para_multi_gen_run, BigId, Data64MappedEntityBuilder, DowncastingBuilder, Entity,
    MarkedAttribute, NamespacedEntity, UnsignedNumber, VarAttBuilder, VariableSizeAttribute, ET,
    MAA,
};
use hashbrown::{HashMap, HashSet};

const MIN_UNIVERSAL: usize = 500;
const MIN_NEEDED: usize = 10;
const TOP_TOPIC: usize = 3;
const TOP_PCTILE: f64 = 0.01;
const SF_YEAR_MIN_PAPERS: usize = 400;
const W_SF: f64 = 0.005;
const W_YEAR: f64 = 0.12;
const W_SF_YEAR: f64 = 1.0 - W_SF - W_YEAR;
const SCORE_THRESHOLD: f64 = 1.5;
const NOBEL_MULTIPLIER: f64 = 2.0;
pub const COORD_MIN_CITES: f64 = 1.0;
pub const COORD_MIN_PAPERS: f64 = 3.0;
const N_PEERS: usize = 10;
// Top subfield dimensions used in the weighted distance metric (Phase 3).
const N_PEER_SF_DIMS: usize = 10;

// PCA + KD-tree peer selection parameters.
// N_PCA_DIMS: number of PCA components from the 253-SF log-citation space.
// N_EMBED_DIMS: total KD-tree embedding dims (PCA + ln_cites_norm + ln_papers_norm).
// EmbedDim must be kept in sync with N_EMBED_DIMS.
const N_PCA_DIMS: usize = 10;
const N_EMBED_DIMS: usize = N_PCA_DIMS + 2;
type EmbedDim = typenum::U12;
const _: () = assert!(
    N_EMBED_DIMS == 12,
    "EmbedDim typenum alias must match N_EMBED_DIMS"
);
// Number of citation-rank deciles; each decile gets its own KD-tree.
const N_DECILES: usize = 20;
// KNN candidates requested per decile tree in Phase 2.
const K_TREE: usize = 500;

pub const AUTHOR_BLACKLIST: [u64; 3] = [
    5030786976, //Lynnette Nathalie Lyzwinski
    5036138197, //David S. Gokhin
    5034807195, //Shadi Yarandi
];

type CCUI = ET<MAA<Works, CiteCountMarker>>;
type AuthorId = ET<Authors>;
type AuthorCitSfArr = ET<MAA<Authors, CitSubfieldsArrayMarker>>;

// PCA output — public so derive_links2 can own + store this later.
pub struct PcaComponents {
    pub means: Vec<f64>,           // per-SF log-mean over filtered authors
    pub components: Vec<Vec<f64>>, // [N_PCA_DIMS][n_sf] unit eigenvectors
    pub scales: Vec<f64>,          // [N_PCA_DIMS] sqrt(eigenvalue) for whitening
}

pub struct PcaResult {
    /// Whitened PCA projections per author, indexed by dm_id (zero for excluded authors).
    pub projections: Vec<[f32; N_PCA_DIMS]>,
    pub components: PcaComponents,
}

struct PeerKdPoint {
    point: [f32; N_EMBED_DIMS],
    dm_id: AuthorId,
}

impl KdPoint for PeerKdPoint {
    type Scalar = f32;
    type Dim = EmbedDim;
    fn at(&self, k: usize) -> f32 {
        self.point[k]
    }
}

// dist_sq stored as the "key": max-heap keeps the worst (largest dist) at the top,
// so we can efficiently evict the furthest candidate when the heap is full.
struct PeerCandidate {
    dist_sq: f64,
    dm_id: AuthorId,
}

impl PartialEq for PeerCandidate {
    fn eq(&self, other: &Self) -> bool {
        self.dist_sq == other.dist_sq
    }
}
impl Eq for PeerCandidate {}
impl PartialOrd for PeerCandidate {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
impl Ord for PeerCandidate {
    fn cmp(&self, other: &Self) -> Ordering {
        self.dist_sq
            .partial_cmp(&other.dist_sq)
            .unwrap_or(Ordering::Equal)
    }
}

struct PeerWorker {
    entries: Arc<Vec<(usize, [f64; 2])>>,
    cit_sfs: Arc<Box<[AuthorCitSfArr]>>,
    pca_projs: Arc<Vec<[f32; N_PCA_DIMS]>>,
    decile_trees: Arc<Vec<KdTree<PeerKdPoint>>>,
    decile_starts: Arc<Vec<usize>>,
    dm_to_rank: Arc<Vec<usize>>,
    sf_weights: [f64; N_PEER_SF_DIMS],
    peers: Arc<Mutex<Vec<[AuthorId; N_PEERS]>>>,
}

impl Worker<(usize, [f64; 2])> for PeerWorker {
    fn proc(&self, (dm_id, ref_coord): (usize, [f64; 2])) {
        // Phase 1: locate hero's decile from its citation rank.
        let rank = self.dm_to_rank[dm_id];
        let decile = self
            .decile_starts
            .partition_point(|&s| s <= rank)
            .saturating_sub(1);
        let d_lo = decile.saturating_sub(1);
        let d_hi = (decile + 1).min(self.decile_trees.len() - 1);

        // Phase 2: KNN from adjacent decile trees → candidate set.
        let query_pt = PeerKdPoint {
            point: make_peer_embed(ref_coord, &self.pca_projs[dm_id]),
            dm_id: 0,
        };
        let mut candidates: Vec<(AuthorId, [f64; 2])> =
            Vec::with_capacity(K_TREE * (d_hi - d_lo + 1));
        for d in d_lo..=d_hi {
            for hit in self.decile_trees[d].nearests(&query_pt, K_TREE) {
                let cid = hit.item.dm_id;
                if cid as usize != dm_id {
                    candidates.push((cid, self.entries[self.dm_to_rank[cid as usize]].1));
                }
            }
        }

        // Phase 3: exact weighted distance on candidates → top N_PEERS.
        let hero_arr = &self.cit_sfs[dm_id];
        let top_sfs = top_k_sf_indices(hero_arr);
        let mut heap: BinaryHeap<PeerCandidate> = BinaryHeap::new();
        for (cand_dm_id, cand_coord) in &candidates {
            let dist_sq = peer_sq_dist(
                ref_coord,
                *cand_coord,
                hero_arr,
                &self.cit_sfs[cand_dm_id.to_usize()],
                &top_sfs,
                &self.sf_weights,
            );
            if heap.len() < N_PEERS || dist_sq < heap.peek().unwrap().dist_sq {
                if heap.len() >= N_PEERS {
                    heap.pop();
                }
                heap.push(PeerCandidate {
                    dist_sq,
                    dm_id: *cand_dm_id,
                });
            }
        }
        let mut out = [AuthorId::default(); N_PEERS];
        for (i, pc) in heap.into_sorted_vec().into_iter().enumerate() {
            out[i] = pc.dm_id;
        }
        self.peers.lock().unwrap()[dm_id] = out;
    }
}

macro_rules! entity_coords_filter {
    ($stowage:expr, $E:ty, |$i:ident, $c:ident, $p:ident| $extra:expr) => {{
        let cites = $stowage.get_marked_interface::<$E, CiteCountMarker, QuickestBox>();
        let wcounts: Vec<usize> = $stowage
            .get_entity_interface::<MAA<$E, MainWorkMarker>, ReadIter>()
            .map(|works| works.len())
            .collect();
        let n = cites.len();
        let mut coords = Vec::with_capacity(n);
        let mut filter = Vec::with_capacity(n);
        for ($i, name) in $stowage
            .get_entity_interface::<MAA<$E, NameMarker>, ReadIter>()
            .enumerate()
        {
            let $c = cites[$i].to_usize();
            let $p = wcounts[$i];
            let cf = $c as f64;
            coords.push([
                f64::max(cf, COORD_MIN_CITES).ln(),
                f64::max($p as f64, COORD_MIN_PAPERS).ln(),
            ]);
            let base = name.trim().len() > 0 && $p > 1 && $c > 2;
            filter.push(if base && { $extra } { 1u8 } else { 0u8 });
        }
        // Normalize in-place over the page-filtered subset so the server and peer
        // computation can use stored coords directly without recomputing statistics.
        {
            let pf_n = filter.iter().filter(|&&f| f > 0).count() as f64;
            let mut means = [0.0f64; 2];
            for (i, &f) in filter.iter().enumerate() {
                if f > 0 {
                    means[0] += coords[i][0] / pf_n;
                    means[1] += coords[i][1] / pf_n;
                }
            }
            let mut vars = [0.0f64; 2];
            for (i, &f) in filter.iter().enumerate() {
                if f > 0 {
                    vars[0] += (coords[i][0] - means[0]).powi(2) / pf_n;
                    vars[1] += (coords[i][1] - means[1]).powi(2) / pf_n;
                }
            }
            let stds = [vars[0].sqrt().max(1e-10), vars[1].sqrt().max(1e-10)];
            for c in coords.iter_mut() {
                c[0] = (c[0] - means[0]) / stds[0];
                c[1] = (c[1] - means[1]) / stds[1];
            }
        }
        $stowage.ditf::<CoordinateMarker, $E, _>(coords.clone(), "coordinates");
        $stowage.ditf::<PageFilterMarker, $E, _>(filter.clone(), "page-filter");
        (coords, filter)
    }};
}

// Returns indices of the top-N_PEER_SF_DIMS subfields by citation count, sorted descending.
// Weight index 0 (highest weight) corresponds to the subfield with the most citations.
fn top_k_sf_indices(arr: &AuthorCitSfArr) -> [usize; N_PEER_SF_DIMS] {
    let mut top = [(0, 0usize); N_PEER_SF_DIMS]; // (val, sf_idx)
    let mut min_val = 0;
    let mut min_pos = 0;
    for (sf, &v) in arr.iter().enumerate() {
        if v > min_val {
            top[min_pos] = (v, sf);
            min_val = u32::MAX;
            min_pos = 0;
            for k in 0..N_PEER_SF_DIMS {
                if top[k].0 < min_val {
                    min_val = top[k].0;
                    min_pos = k;
                }
            }
        }
    }
    top.sort_unstable_by(|a, b| b.0.cmp(&a.0));
    top.map(|(_, sf)| sf)
}

// 12-dimensional weighted squared distance:
// - 10 dims: log-scaled citation counts in hero's top subfields, weights 2.0 * 0.9^k
// - 2 dims: normalized ln_cites and ln_papers from pre-computed coords, weight 1.0 each
fn peer_sq_dist(
    coord_a: [f64; 2],
    coord_b: [f64; 2],
    arr_a: &AuthorCitSfArr,
    arr_b: &AuthorCitSfArr,
    top_sfs: &[usize; N_PEER_SF_DIMS],
    weights: &[f64; N_PEER_SF_DIMS],
) -> f64 {
    let mut dist = 0.0f64;
    for k in 0..N_PEER_SF_DIMS {
        let sf = top_sfs[k];
        let va = (arr_a[sf].max(1) as f64).ln();
        let vb = (arr_b[sf].max(1) as f64).ln();
        dist += weights[k] * (va - vb).powi(2);
    }
    dist += (coord_a[0] - coord_b[0]).powi(2);
    dist += (coord_a[1] - coord_b[1]).powi(2);
    dist
}

fn make_peer_embed(coord: [f64; 2], pca: &[f32; N_PCA_DIMS]) -> [f32; N_EMBED_DIMS] {
    let mut point = [0f32; N_EMBED_DIMS];
    point[0] = coord[0] as f32;
    point[1] = coord[1] as f32;
    point[2..].copy_from_slice(pca);
    point
}

/// Computes whitened PCA of log-citation-subfield vectors for filtered authors.
/// Public so this can be moved to derive_links2 later and stored to disk.
pub fn compute_sf_pca(cit_sfs: &[AuthorCitSfArr], filter: &[u8]) -> PcaResult {
    let n_total = cit_sfs.len();
    let n_sf = if n_total == 0 { 0 } else { cit_sfs[0].len() };
    let filtered_ids: Vec<usize> = (0..n_total).filter(|&i| filter[i] > 0).collect();
    let n_filtered = filtered_ids.len();
    let nf = n_filtered as f64;
    let n_threads = std::thread::available_parallelism().map_or(1, |p| p.get());

    // Pass 1: per-SF log-means over filtered authors.
    let mut means = vec![0f64; n_sf];
    for &dm_id in &filtered_ids {
        let x = &cit_sfs[dm_id];
        for sf in 0..n_sf {
            means[sf] += (x[sf].max(1) as f64).ln();
        }
    }
    for m in &mut means {
        *m /= nf;
    }
    println!(
        "[pca] means computed, {} filtered authors, {} subfield dims",
        n_filtered, n_sf
    );

    // Pass 2: n_sf × n_sf covariance matrix, parallelised over filtered authors.
    // Each thread accumulates into a local flat upper-triangle buffer; merged after.
    let chunk_size = (n_filtered + n_threads - 1) / n_threads;
    let cov_flat: Vec<f64> = std::thread::scope(|s| {
        filtered_ids
            .chunks(chunk_size)
            .map(|chunk| {
                let means = means.as_slice();
                s.spawn(move || {
                    let mut local = vec![0f64; n_sf * n_sf];
                    let mut centered = vec![0f64; n_sf];
                    for &dm_id in chunk {
                        let x = &cit_sfs[dm_id];
                        for sf in 0..n_sf {
                            centered[sf] = (x[sf].max(1) as f64).ln() - means[sf];
                        }
                        for i in 0..n_sf {
                            let ci = centered[i];
                            for j in i..n_sf {
                                local[i * n_sf + j] += ci * centered[j];
                            }
                        }
                    }
                    local
                })
            })
            .collect::<Vec<_>>()
            .into_iter()
            .map(|h| h.join().unwrap())
            .fold(vec![0f64; n_sf * n_sf], |mut acc, loc| {
                acc.iter_mut().zip(loc.iter()).for_each(|(a, &b)| *a += b);
                acc
            })
    });
    println!("[pca] covariance matrix assembled");

    // Build symmetric nalgebra matrix (normalised by n_filtered).
    let cov = DMatrix::from_fn(n_sf, n_sf, |i, j| {
        let (lo, hi) = if i <= j { (i, j) } else { (j, i) };
        cov_flat[lo * n_sf + hi] / nf
    });

    // Eigendecompose and pick top N_PCA_DIMS by descending eigenvalue.
    let eigen = SymmetricEigen::new(cov);
    let mut order: Vec<usize> = (0..n_sf).collect();
    order.sort_unstable_by(|&a, &b| {
        eigen.eigenvalues[b]
            .partial_cmp(&eigen.eigenvalues[a])
            .unwrap_or(Ordering::Equal)
    });
    let top_eigenvalues: Vec<f64> = order
        .iter()
        .take(N_PCA_DIMS)
        .map(|&i| eigen.eigenvalues[i])
        .collect();
    println!(
        "[pca] top {} eigenvalues: {:?}",
        N_PCA_DIMS, top_eigenvalues
    );
    let top_components: Vec<Vec<f64>> = order
        .iter()
        .take(N_PCA_DIMS)
        .map(|&i| eigen.eigenvectors.column(i).iter().copied().collect())
        .collect();
    let scales: Vec<f64> = top_eigenvalues
        .iter()
        .map(|&v| v.sqrt().max(1e-10))
        .collect();

    // Project all filtered authors and whiten (divide by scale = sqrt(eigenvalue)).
    let chunk_size = (n_total + n_threads - 1) / n_threads;
    let dm_ranges: Vec<std::ops::Range<usize>> = (0..n_total)
        .step_by(chunk_size)
        .map(|lo| lo..(lo + chunk_size).min(n_total))
        .collect();
    let proj_chunks: Vec<Vec<(usize, [f32; N_PCA_DIMS])>> = std::thread::scope(|s| {
        dm_ranges
            .iter()
            .map(|range| {
                let comps = top_components.as_slice();
                let scales = scales.as_slice();
                let means = means.as_slice();
                s.spawn(move || {
                    range
                        .clone()
                        .filter(|&dm_id| filter[dm_id] > 0)
                        .map(|dm_id| {
                            let x = &cit_sfs[dm_id];
                            let proj = core::array::from_fn(|k| {
                                let dot: f64 = comps[k]
                                    .iter()
                                    .enumerate()
                                    .map(|(sf, &c)| c * ((x[sf].max(1) as f64).ln() - means[sf]))
                                    .sum();
                                (dot / scales[k]) as f32
                            });
                            (dm_id, proj)
                        })
                        .collect::<Vec<_>>()
                })
            })
            .collect::<Vec<_>>()
            .into_iter()
            .map(|h| h.join().unwrap())
            .collect()
    });
    let mut projections = vec![[0f32; N_PCA_DIMS]; n_total];
    for chunk in proj_chunks {
        for (dm_id, proj) in chunk {
            projections[dm_id] = proj;
        }
    }
    println!("[pca] projections done");

    PcaResult {
        projections,
        components: PcaComponents {
            means,
            components: top_components,
            scales,
        },
    }
}

fn build_decile_trees(
    entries: &[(usize, [f64; 2])],
    pca_projs: &[[f32; N_PCA_DIMS]],
) -> (Vec<KdTree<PeerKdPoint>>, Vec<usize>) {
    let n = entries.len();
    let chunk = (n + N_DECILES - 1) / N_DECILES;
    let mut trees = Vec::with_capacity(N_DECILES);
    let mut decile_starts = Vec::with_capacity(N_DECILES);
    for d in 0..N_DECILES {
        let lo = (d * chunk).min(n);
        let hi = ((d + 1) * chunk).min(n);
        decile_starts.push(lo);
        let points: Vec<PeerKdPoint> = entries[lo..hi]
            .iter()
            .map(|&(dm_id, coord)| PeerKdPoint {
                point: make_peer_embed(coord, &pca_projs[dm_id]),
                dm_id: dm_id as AuthorId,
            })
            .collect();
        trees.push(KdTree::build_by_ordered_float(points));
    }
    (trees, decile_starts)
}

fn compute_author_peers(stowage: &Stowage, coords: &[[f64; 2]], filter: &[u8]) {
    let cit_sfs =
        Arc::new(stowage.get_marked_interface::<Authors, CitSubfieldsArrayMarker, QuickestBox>());

    // Sort filtered authors by normalised ln_cites so decile splits are citation-ordered.
    let mut entries: Vec<(usize, [f64; 2])> = filter
        .iter()
        .enumerate()
        .filter(|(_, &f)| f > 0)
        .map(|(i, _)| (i, coords[i]))
        .collect();
    entries.sort_by(|a, b| a.1[0].partial_cmp(&b.1[0]).unwrap_or(Ordering::Equal));
    let n = entries.len();

    let mut dm_to_rank = vec![0usize; coords.len()];
    for (rank, &(dm_id, _)) in entries.iter().enumerate() {
        dm_to_rank[dm_id] = rank;
    }

    let sf_weights: [f64; N_PEER_SF_DIMS] = core::array::from_fn(|k| 2.0 * 0.9f64.powi(k as i32));

    let t0 = std::time::Instant::now();
    let pca = compute_sf_pca(&cit_sfs, filter);
    println!("[peers] PCA total: {:.2?}", t0.elapsed());

    let t1 = std::time::Instant::now();
    let (decile_trees, decile_starts) = build_decile_trees(&entries, &pca.projections);
    println!(
        "[peers] {} decile trees built ({} filtered authors): {:.2?}",
        N_DECILES,
        n,
        t1.elapsed()
    );

    let peers_out = Arc::new(Mutex::new(vec![
        [AuthorId::default(); N_PEERS];
        coords.len()
    ]));
    let entries_arc = Arc::new(entries);
    let t2 = std::time::Instant::now();
    PeerWorker {
        entries: entries_arc.clone(),
        cit_sfs,
        pca_projs: Arc::new(pca.projections),
        decile_trees: Arc::new(decile_trees),
        decile_starts: Arc::new(decile_starts),
        dm_to_rank: Arc::new(dm_to_rank),
        sf_weights,
        peers: peers_out.clone(),
    }
    .para(entries_arc.iter().copied());
    println!(
        "[peers] parallel phase 2+3 ({} filtered authors): {:.2?}",
        n,
        t2.elapsed()
    );

    let peers = Arc::try_unwrap(peers_out).unwrap().into_inner().unwrap();
    stowage.ditf::<PeerAuthorMarker, Authors, _>(peers, "peers");
}

pub fn work_count<E>(stowage: &Stowage)
where
    E: MarkedAttribute<MainWorkMarker>,
    MAA<E, MainWorkMarker>: Entity<T = Box<[ET<Works>]>> + NamespacedEntity + VariableSizeAttribute,
{
    stowage.declare_iter::<DowncastingBuilder, _, _, E, WorkCountMarker>(
        stowage
            .get_entity_interface::<MAA<E, MainWorkMarker>, ReadIter>()
            .map(|e| e.len()),
        &format!("{}-work-count", E::NAME),
    );
}

pub fn get_nobeled_works(stowage: &Stowage, w_years: &[ET<Years>]) -> HashSet<ET<Works>> {
    let author_nobels = stowage.get_entity_interface::<AuthorNobels, QuickestBox>();
    let mut nobeled_works = HashSet::new();
    for (wid, w_aids) in stowage
        .get_entity_interface::<WorkFilteredAuthors, ReadIter>()
        .enumerate()
    {
        let wyear = w_years[wid];
        for aid in w_aids {
            let anobely = author_nobels[aid.to_usize()].1;
            if anobely >= wyear {
                nobeled_works.insert(ET::<Works>::from_usize(wid));
            }
        }
    }
    nobeled_works
}

pub fn main(stowage: Stowage) -> std::io::Result<()> {
    let starc = Arc::new(stowage);
    para_multi_gen_run!(work_count, Sources, Institutions, Authors, Subfields, Topics, Countries; starc)
        .last();

    let cc_interface = starc.get_entity_interface::<MAA<Works, CiteCountMarker>, QuickestBox>();
    let w_sfs = starc.get_entity_interface::<WorkSubfields, QuickestVBox>();
    let w_topics = starc.get_entity_interface::<WorkTopics, QuickestVBox>();
    let w_years = starc.get_entity_interface::<WorkYears, QuickestBox>();

    let topic_limits = get_limits::<Topics, _, _, _>(
        TOP_TOPIC,
        w_topics.0.iter().map(|e| e.iter().map(|se| *se)),
        &cc_interface,
    );

    let year_bms = compute_year_bms(&w_years, &cc_interface);
    let sf_bms = compute_sf_bms(&w_sfs.0, &cc_interface);
    let sf_year_bms = compute_sf_year_bms(&w_sfs.0, &w_years, &cc_interface, &year_bms);

    let nobeled_works = get_nobeled_works(&starc, &w_years);

    let doi_interface = starc.get_entity_interface::<WorkDois, QuickestVBox>();
    let name_interface = starc.get_entity_interface::<WorksNames, ReadIter>();
    let mut hit_names = vec!["Unknown".to_string()];
    let mut hit_dois = vec!["".to_string()];
    let mut hit_ccounts = vec![0];
    let mut hit_wids = vec![vec![].into_boxed_slice()];
    let this_year = YearInterface::parse(FINAL_YEAR);

    let hit_papers = name_interface.enumerate().filter_map(|(wid, name)| {
        if w_years[wid] >= this_year {
            return None;
        }
        let widt = ET::<Works>::from_usize(wid);
        let wcc = cc_interface[wid];
        let cc_n = wcc.to_usize();
        let year = w_years[wid].to_usize();

        let reaches_any_topic_limit = w_topics.0[wid]
            .iter()
            .any(|e| topic_limits[e.to_usize()] <= wcc);
        let multiplier = if nobeled_works.contains(&widt) {
            NOBEL_MULTIPLIER
        } else {
            1.0
        };
        let bm = paper_bm(&w_sfs.0[wid], year, &sf_year_bms, &sf_bms, &year_bms);
        let score = if bm > 0.0 {
            cc_n as f64 / bm * multiplier
        } else {
            0.0
        };

        let qualifies = (cc_n >= MIN_NEEDED)
            & (cc_n >= MIN_UNIVERSAL || reaches_any_topic_limit || score >= SCORE_THRESHOLD);

        if qualifies {
            hit_names.push(name);
            hit_dois.push(doi_interface.0[wid].to_string());
            hit_ccounts.push(cc_n);
            //TODO: unnecessary but low cost - hit_papers contains the exact same info
            //but this is so that something that is a Box<[wid]> can be assigned to hit-papers
            //as in memory wid store for trees
            //this is the way to add an N+1 hit papers with all of them
            hit_wids.push(vec![wid as ET<Works>].into_boxed_slice());
            Some(wid as BigId)
        } else {
            None
        }
    });

    let w2amap = starc.get_entity_interface::<WorkFilteredAuthors, QuickestVBox>();
    let coauthorships: Vec<Box<[(ET<Authors>, u8)]>> = starc
        .get_entity_interface::<AuthorWorks, ReadIter>()
        .enumerate()
        .map(|(aid, aworks)| {
            let mut coauthor_map = HashMap::<ET<Authors>, u8>::new();
            IntoIterator::into_iter(aworks).for_each(|wid| {
                w2amap.0[wid.to_usize()].iter().for_each(|c_aid| {
                    if c_aid.to_usize() != aid {
                        let entry = coauthor_map.entry(*c_aid).or_insert(0);
                        if *entry <= 200 {
                            entry.add_assign(1)
                        }
                    }
                });
            });
            coauthor_map
                .into_iter()
                .collect::<Vec<(ET<Authors>, u8)>>()
                .into_boxed_slice()
        })
        .collect();

    starc.add_iter_owned::<Data64MappedEntityBuilder, _, _>(hit_papers, Some("hit-papers"));

    starc.add_iter_owned::<VarAttBuilder, _, _>(hit_names.into_iter(), Some("hit-papers-names"));
    starc.add_iter_owned::<VarAttBuilder, _, _>(hit_dois.into_iter(), Some("hit-papers-dois"));
    starc.add_iter_owned::<VarAttBuilder, _, _>(hit_wids.into_iter(), Some("hit-papers-wids"));
    starc.add_iter_owned::<VarAttBuilder, _, _>(coauthorships.into_iter(), Some("coauthors"));
    starc.add_iter_owned::<DowncastingBuilder, _, _>(
        hit_ccounts.into_iter(),
        Some("hit-papers-cite-counts"),
    );

    entity_coords_filter!(starc, Institutions, |_i, _c, _p| true);
    entity_coords_filter!(starc, Subfields, |_i, _c, _p| true);
    entity_coords_filter!(starc, Countries, |_i, _c, _p| true);

    let source_stats = starc.get_entity_interface::<SourceStats, QuickestBox>();
    entity_coords_filter!(starc, Sources, |i, c, p| {
        p > 10 && c > 20 && source_stats[i].1 <= 2
    });

    let author_yearly_papers =
        starc.get_marked_interface::<Authors, YearlyPapersMarker, QuickestBox>();
    let author_oa_ids = reverse_id::<Authors>(&starc);
    let (author_coords, author_filter) = entity_coords_filter!(starc, Authors, |i, _c, p| {
        p < 10_000
            && *author_yearly_papers[i].iter().max().unwrap_or(&0) < 300
            && !AUTHOR_BLACKLIST.contains(&author_oa_ids[i])
    });

    println!("computing author peers");
    compute_author_peers(&starc, &author_coords, &author_filter);

    starc.write_code()?;
    Ok(())
}

fn compute_year_bms(w_years: &[ET<Years>], ccs: &[CCUI]) -> Box<[f64]> {
    let mut groups = init_empty_slice::<Years, Vec<CCUI>>();
    for (wid, yr) in w_years.iter().enumerate() {
        groups[yr.to_usize()].push(ccs[wid]);
    }
    groups
        .iter_mut()
        .map(|g| top_pctile(g))
        .collect::<Vec<_>>()
        .into()
}

fn compute_sf_year_bms(
    w_sfs: &[Box<[ET<Subfields>]>],
    w_years: &[ET<Years>],
    ccs: &[CCUI],
    year_bms: &[f64],
) -> HashMap<(usize, usize), f64> {
    let mut groups: HashMap<(usize, usize), Vec<CCUI>> = HashMap::new();
    for (wid, sfs) in w_sfs.iter().enumerate() {
        let yr = w_years[wid].to_usize();
        let cc = ccs[wid];
        for sf in sfs.iter() {
            groups.entry((sf.to_usize(), yr)).or_default().push(cc);
        }
    }
    groups
        .into_iter()
        .map(|((sf, yr), mut v)| {
            let bm = if v.len() >= SF_YEAR_MIN_PAPERS {
                top_pctile(&mut v)
            } else {
                year_bms[yr]
            };
            ((sf, yr), bm)
        })
        .collect()
}

fn compute_sf_bms(w_sfs: &[Box<[ET<Subfields>]>], ccs: &[CCUI]) -> HashMap<usize, f64> {
    let mut groups: HashMap<usize, Vec<CCUI>> = HashMap::new();
    for (wid, sfs) in w_sfs.iter().enumerate() {
        for sf in sfs.iter() {
            groups.entry(sf.to_usize()).or_default().push(ccs[wid]);
        }
    }
    groups
        .into_iter()
        .map(|(sf, mut v)| (sf, top_pctile(&mut v)))
        .collect()
}

fn paper_bm(
    sfs: &[ET<Subfields>],
    year: usize,
    sf_year_bms: &HashMap<(usize, usize), f64>,
    sf_bms: &HashMap<usize, f64>,
    year_bms: &[f64],
) -> f64 {
    if sfs.is_empty() {
        return year_bms[year];
    }
    let n = sfs.len() as f64;
    let yr_bm = year_bms[year];
    let sf_year_avg = sfs
        .iter()
        .map(|sf| *sf_year_bms.get(&(sf.to_usize(), year)).unwrap_or(&yr_bm))
        .sum::<f64>()
        / n;
    let sf_avg = sfs
        .iter()
        .map(|sf| *sf_bms.get(&sf.to_usize()).unwrap_or(&yr_bm))
        .sum::<f64>()
        / n;
    W_SF_YEAR * sf_year_avg + W_SF * sf_avg + W_YEAR * yr_bm
}

fn top_pctile(ccs: &mut Vec<CCUI>) -> f64 {
    if ccs.is_empty() {
        return 0.0;
    }
    ccs.sort_unstable_by(|a, b| b.cmp(a));
    let top_n = ((ccs.len() as f64 * TOP_PCTILE).ceil() as usize)
        .max(1)
        .min(ccs.len());
    ccs[top_n - 1].to_usize() as f64
}

fn get_limits<E, I, I2, U>(n: usize, it: I, ccs: &Box<[CCUI]>) -> Box<[CCUI]>
where
    E: Entity,
    I: Iterator<Item = I2>,
    I2: Iterator<Item = U>,
    U: UnsignedNumber,
{
    let mut count_heaps = init_empty_slice::<E, BinaryHeap<CCUI>>();
    it.enumerate().for_each(|(wid, atts)| {
        atts.for_each(|a| count_heaps[a.to_usize()].push(ccs[wid]));
    });
    count_heaps
        .to_vec()
        .into_iter()
        .map(|e| topn(e, n))
        .collect::<Vec<CCUI>>()
        .into()
}

fn topn(mut h: BinaryHeap<CCUI>, n: usize) -> CCUI {
    let mut out = CCUI::MAX;
    for _ in 0..n {
        match h.pop() {
            Some(e) => out = e,
            None => break,
        }
    }
    out
}
