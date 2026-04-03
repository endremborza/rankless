use std::{cmp::Ordering, collections::BinaryHeap};

use kd_tree::{KdPoint, KdTree};
use nalgebra::{DMatrix, SymmetricEigen};
use typenum;

use dmove::{ByteFixArrayInterface, UnsignedNumber, ET};

use crate::{
    common::{NumberedEntity, PeerMarker, NET, N_PEERS},
    Stowage,
};

pub const N_PEER_SF_DIMS: usize = 10;
pub const W_PEER_SF: f64 = 1.0;
pub const W_PEER_RATE: f64 = 0.5;
pub const W_PEER_GEO: f64 = 0.3;
pub const W_PEER_COUNTRY: f64 = 0.5;
pub const W_PEER_TEMPORAL: f64 = 0.4;

const N_DECILES: usize = 20;
const K_TREE: usize = 500;

// --- Prefilter embed types ---
//
// Each entity type provides a `Point` associated type in `PeerConfig`.
// Embed2 is the default for 2D prefiltering (e.g. [ln_cites, ln_papers] for authors).
// Adding a 3rd dimension (e.g. temporal centroid) means switching to Embed3 —
// change `type Point = Embed2` to `type Point = Embed3` in the concrete impl.

#[derive(Clone)]
pub struct Embed1 {
    pub coord: f32,
    pub dm_id: usize,
}

#[derive(Clone)]
pub struct Embed2 {
    pub coords: [f32; 2],
    pub dm_id: usize,
}

#[derive(Clone)]
pub struct Embed3 {
    pub coords: [f32; 3],
    pub dm_id: usize,
}

impl KdPoint for Embed1 {
    type Scalar = f32;
    type Dim = typenum::U1;
    fn at(&self, _: usize) -> f32 {
        self.coord
    }
}

impl KdPoint for Embed2 {
    type Scalar = f32;
    type Dim = typenum::U2;
    fn at(&self, k: usize) -> f32 {
        self.coords[k]
    }
}

impl KdPoint for Embed3 {
    type Scalar = f32;
    type Dim = typenum::U3;
    fn at(&self, k: usize) -> f32 {
        self.coords[k]
    }
}

pub trait PeerPoint: KdPoint<Scalar = f32> + Clone + Sync {
    fn dm_id(&self) -> usize;
}

impl PeerPoint for Embed1 {
    fn dm_id(&self) -> usize {
        self.dm_id
    }
}
impl PeerPoint for Embed2 {
    fn dm_id(&self) -> usize {
        self.dm_id
    }
}
impl PeerPoint for Embed3 {
    fn dm_id(&self) -> usize {
        self.dm_id
    }
}

// --- Candidate heap ---

pub struct PeerCandidate {
    pub dist_sq: f64,
    pub dm_id: usize,
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

// --- PeerConfig trait ---
//
// Concrete impls live in the step files (derive3, derive4).
// Each impl carries its pre-loaded data and provides:
//   - filter: which entities participate
//   - rank_val: primary sort key for decile construction
//   - point: embed for KD-tree prefilter
//   - dist: full distance metric between entity indices

pub trait PeerConfig: Sync {
    type E: NumberedEntity + Sync;
    type Point: PeerPoint;

    fn n(&self) -> usize;
    fn filter(&self) -> &[u8];
    fn rank_val(&self, idx: usize) -> f32;
    fn point(&self, idx: usize) -> Self::Point;
    fn dist(&self, a: usize, b: usize) -> f64;

    fn n_deciles(&self) -> usize {
        N_DECILES
    }
    fn k_candidates(&self) -> usize {
        K_TREE
    }
}

pub fn compute_peers<C>(stowage: &Stowage, config: &C)
where
    C: PeerConfig,
    ET<C::E>: UnsignedNumber,
    [NET<C::E>; N_PEERS]: ByteFixArrayInterface,
    <C::Point as KdPoint>::Dim: Sync,
{
    let filter = config.filter();
    let n = config.n();

    let mut entries: Vec<(usize, f32)> = (0..n)
        .filter(|&i| filter[i] > 0)
        .map(|i| (i, config.rank_val(i)))
        .collect();
    entries.sort_unstable_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(Ordering::Equal));

    let n_filtered = entries.len();
    let n_dec = config.n_deciles().max(1);
    let chunk = (n_filtered + n_dec - 1) / n_dec;
    let decile_starts: Vec<usize> = (0..n_dec).map(|d| (d * chunk).min(n_filtered)).collect();

    let mut dm_to_rank = vec![0usize; n];
    for (rank, &(dm_id, _)) in entries.iter().enumerate() {
        dm_to_rank[dm_id] = rank;
    }

    let t0 = std::time::Instant::now();
    let trees: Vec<KdTree<C::Point>> = (0..n_dec)
        .map(|d| {
            let lo = decile_starts[d];
            let hi = ((d + 1) * chunk).min(n_filtered);
            KdTree::build_by_ordered_float(
                entries[lo..hi]
                    .iter()
                    .map(|&(dm_id, _)| config.point(dm_id))
                    .collect(),
            )
        })
        .collect();
    println!(
        "[peers {}] {} trees ({} filtered): {:.2?}",
        <C::E as dmove::Entity>::NAME,
        n_dec,
        n_filtered,
        t0.elapsed()
    );

    let k_cand = config.k_candidates();
    let select = |dm_id: usize| -> [NET<C::E>; N_PEERS] {
        let rank = dm_to_rank[dm_id];
        let dec = decile_starts
            .partition_point(|&s| s <= rank)
            .saturating_sub(1);
        let d_lo = dec.saturating_sub(1);
        let d_hi = (dec + 1).min(trees.len() - 1);
        let query = config.point(dm_id);
        let mut heap = BinaryHeap::<PeerCandidate>::new();
        for d in d_lo..=d_hi {
            for hit in trees[d].nearests(&query, k_cand) {
                let cid = hit.item.dm_id();
                if cid != dm_id {
                    let dist = config.dist(dm_id, cid);
                    if heap.len() < N_PEERS || dist < heap.peek().unwrap().dist_sq {
                        if heap.len() >= N_PEERS {
                            heap.pop();
                        }
                        heap.push(PeerCandidate {
                            dist_sq: dist,
                            dm_id: cid,
                        });
                    }
                }
            }
        }
        let mut out = [NET::<C::E>::default(); N_PEERS];
        for (i, pc) in heap.into_sorted_vec().into_iter().enumerate() {
            out[i] = NET::<C::E>::from_usize(pc.dm_id);
        }
        out
    };

    let mut peers_out = vec![[NET::<C::E>::default(); N_PEERS]; n];
    let t1 = std::time::Instant::now();
    let n_threads = std::thread::available_parallelism().map_or(1, |p| p.get());
    let tc = (n_filtered + n_threads - 1) / n_threads;
    std::thread::scope(|s| {
        entries
            .chunks(tc)
            .map(|slice| {
                s.spawn(|| {
                    slice
                        .iter()
                        .map(|&(dm_id, _)| (dm_id, select(dm_id)))
                        .collect::<Vec<_>>()
                })
            })
            .collect::<Vec<_>>()
            .into_iter()
            .flat_map(|h| h.join().unwrap())
            .for_each(|(dm_id, arr)| peers_out[dm_id] = arr);
    });
    println!(
        "[peers {}] parallel phase: {:.2?}",
        <C::E as dmove::Entity>::NAME,
        t1.elapsed()
    );

    stowage.ditf::<PeerMarker, C::E, _>(peers_out, "peers");
}

// --- Distance utilities ---

pub fn sf_log_dist(
    arr_a: &[u32],
    arr_b: &[u32],
    top_sfs: &[usize; N_PEER_SF_DIMS],
    weights: &[f64; N_PEER_SF_DIMS],
) -> f64 {
    let mut dist = 0.0;
    for k in 0..N_PEER_SF_DIMS {
        let sf = top_sfs[k];
        let va = (arr_a[sf].max(1) as f64).ln();
        let vb = (arr_b[sf].max(1) as f64).ln();
        dist += weights[k] * (va - vb).powi(2);
    }
    dist
}

pub fn sf_rate_dist(
    arr_a: &[u32],
    arr_b: &[u32],
    top_sfs: &[usize; N_PEER_SF_DIMS],
    total_a: f64,
    total_b: f64,
) -> f64 {
    if total_a == 0.0 || total_b == 0.0 {
        return 0.0;
    }
    let mut dist = 0.0;
    for k in 0..N_PEER_SF_DIMS {
        let sf = top_sfs[k];
        let ra = arr_a[sf] as f64 / total_a;
        let rb = arr_b[sf] as f64 / total_b;
        dist += (ra - rb).powi(2);
    }
    dist
}

pub fn geo_sq_dist(a: (f64, f64), b: (f64, f64)) -> f64 {
    if (a.0 == 0.0 && a.1 == 0.0) || (b.0 == 0.0 && b.1 == 0.0) {
        return 0.0;
    }
    let dlat = (a.0 - b.0).to_radians();
    let dlon = (a.1 - b.1).to_radians();
    let cos_avg = ((a.0 + b.0) / 2.0).to_radians().cos();
    dlat * dlat + (dlon * cos_avg) * (dlon * cos_avg)
}

// --- Prefilter embed helpers ---

pub fn top_k_sf_indices(arr: &[u32]) -> [usize; N_PEER_SF_DIMS] {
    let mut top = [(0u32, 0usize); N_PEER_SF_DIMS];
    let mut min_val = 0u32;
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

pub fn compute_top_sfs<const N: usize>(cit_sfs: &[[u32; N]]) -> Vec<[usize; N_PEER_SF_DIMS]> {
    cit_sfs.iter().map(|arr| top_k_sf_indices(arr)).collect()
}

pub fn compute_sf_totals<const N: usize>(cit_sfs: &[[u32; N]]) -> Vec<f64> {
    cit_sfs
        .iter()
        .map(|arr| arr.iter().map(|&v| v as f64).sum())
        .collect()
}

pub fn sf_peer_weights() -> [f64; N_PEER_SF_DIMS] {
    core::array::from_fn(|k| 2.0 * 0.9f64.powi(k as i32))
}

pub fn compute_career_centroids<const N: usize>(
    yearly_papers: &[[u32; N]],
    filter: &[u8],
) -> Vec<f32> {
    let n_total = yearly_papers.len();
    let mut centroids = vec![0f32; n_total];
    for i in 0..n_total {
        if filter[i] == 0 {
            continue;
        }
        let yp = &yearly_papers[i];
        let total: u32 = yp.iter().sum();
        if total == 0 {
            continue;
        }
        let weighted: f64 = yp
            .iter()
            .enumerate()
            .map(|(yr, &c)| yr as f64 * c as f64)
            .sum();
        centroids[i] = (weighted / total as f64) as f32;
    }
    let filtered: Vec<f32> = filter
        .iter()
        .enumerate()
        .filter(|(_, &f)| f > 0)
        .map(|(i, _)| centroids[i])
        .collect();
    let n_f = filtered.len() as f64;
    if n_f == 0.0 {
        return centroids;
    }
    let mean: f64 = filtered.iter().map(|&v| v as f64).sum::<f64>() / n_f;
    let var: f64 = filtered
        .iter()
        .map(|&v| (v as f64 - mean).powi(2))
        .sum::<f64>()
        / n_f;
    let std = var.sqrt().max(1e-10);
    for c in &mut centroids {
        *c = ((*c as f64 - mean) / std) as f32;
    }
    centroids
}

/// Normalizes a 2D embedding array in-place using filtered entries only.
/// Used for the author prefilter embed [ln_cites, ln_papers].
pub fn normalize_2d_inplace(embeds: &mut [[f64; 2]], filter: &[u8]) {
    let pf_n = filter.iter().filter(|&&f| f > 0).count() as f64;
    if pf_n == 0.0 {
        return;
    }
    let mut means = [0.0f64; 2];
    for (i, &f) in filter.iter().enumerate() {
        if f > 0 {
            means[0] += embeds[i][0] / pf_n;
            means[1] += embeds[i][1] / pf_n;
        }
    }
    let mut vars = [0.0f64; 2];
    for (i, &f) in filter.iter().enumerate() {
        if f > 0 {
            vars[0] += (embeds[i][0] - means[0]).powi(2) / pf_n;
            vars[1] += (embeds[i][1] - means[1]).powi(2) / pf_n;
        }
    }
    let stds = [vars[0].sqrt().max(1e-10), vars[1].sqrt().max(1e-10)];
    for e in embeds.iter_mut() {
        e[0] = (e[0] - means[0]) / stds[0];
        e[1] = (e[1] - means[1]) / stds[1];
    }
}

fn compute_sf_pca<const N_SF: usize>(
    cit_sfs: &[[u32; N_SF]],
    filter: &[u8],
) -> Vec<[f32; N_PCA_DIMS]> {
    let n_total = cit_sfs.len();
    let filtered_ids: Vec<usize> = (0..n_total).filter(|&i| filter[i] > 0).collect();
    let n_filtered = filtered_ids.len();
    let nf = n_filtered as f64;
    let n_threads = std::thread::available_parallelism().map_or(1, |p| p.get());

    let mut means = vec![0f64; N_SF];
    for &dm_id in &filtered_ids {
        let x = &cit_sfs[dm_id];
        for sf in 0..N_SF {
            means[sf] += (x[sf].max(1) as f64).ln();
        }
    }
    for m in &mut means {
        *m /= nf;
    }
    println!(
        "[pca] means computed, {} filtered, {} dims",
        n_filtered, N_SF
    );

    let chunk_size = (n_filtered + n_threads - 1) / n_threads;
    let cov_flat: Vec<f64> = std::thread::scope(|s| {
        filtered_ids
            .chunks(chunk_size)
            .map(|chunk| {
                let means = means.as_slice();
                s.spawn(move || {
                    let mut local = vec![0f64; N_SF * N_SF];
                    let mut centered = vec![0f64; N_SF];
                    for &dm_id in chunk {
                        let x = &cit_sfs[dm_id];
                        for sf in 0..N_SF {
                            centered[sf] = (x[sf].max(1) as f64).ln() - means[sf];
                        }
                        for i in 0..N_SF {
                            let ci = centered[i];
                            for j in i..N_SF {
                                local[i * N_SF + j] += ci * centered[j];
                            }
                        }
                    }
                    local
                })
            })
            .collect::<Vec<_>>()
            .into_iter()
            .map(|h| h.join().unwrap())
            .fold(vec![0f64; N_SF * N_SF], |mut acc, loc| {
                acc.iter_mut().zip(loc.iter()).for_each(|(a, &b)| *a += b);
                acc
            })
    });
    println!("[pca] covariance matrix assembled");

    let cov = DMatrix::from_fn(N_SF, N_SF, |i, j| {
        let (lo, hi) = if i <= j { (i, j) } else { (j, i) };
        cov_flat[lo * N_SF + hi] / nf
    });
    let eigen = SymmetricEigen::new(cov);
    let mut order: Vec<usize> = (0..N_SF).collect();
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
    projections
}
