use std::{
    cmp::{Ordering, Reverse},
    ops::RangeInclusive,
    sync::Arc,
};

use kd_tree::{KdPoint, KdTree};
use nalgebra::{DMatrix, SymmetricEigen};
use ordered_float::FloatCore;
use typenum;

use dmove::UnsignedNumber;

use crate::{
    common::{NumberedEntity, PeerMarker, NET},
    fixed_heap::FixedHeap,
    Stowage,
};

// Field-size dampening exponent for top-subfield selection: score[s] = cit[s] / field_size[s]^beta.
// 0.0 = raw citations; 1.0 = entity's share of the field. Shared so peer matching, the precomputed
// top-subfield relations, and the server's displayed comparison basis all rank subfields the same.
pub const SPEC_BETA: f64 = 0.75;
// The distance at which `geo_dist` has covered 1 - 1/e of its range.
pub const PEER_GEO_SCALE_KM: f64 = 500.0;

const EARTH_RADIUS_KM: f64 = 6371.0;

pub struct PartitionedTrees<const D: usize>
where
    Embed<D>: KdPoint,
{
    partition_len: usize,
    trees: Box<[KdTree<Embed<D>>]>,
}

pub struct Embed<const D: usize> {
    pub coords: [f32; D],
    pub eid: usize,
}

struct PcaComponents<const D: usize> {
    scales: [f32; D],
    components: [Vec<f32>; D],
}

struct FilterConf<const D: usize> {
    filtered_inds: Vec<usize>,
    means: [f32; D],
}

/// What an embedding's PCA runs on, per row of counts.
#[derive(Clone, Copy)]
pub(crate) enum RowScale {
    /// The log of each count. The first component is size, and every component is scaled to unit
    /// variance so that size does not drown the rest.
    LogCount,
    /// The square root of each count's share of its row (the Hellinger transform). It carries no
    /// size, a zero stays a zero, and the components keep their variance, so the distance between
    /// two embedded rows approximates the Hellinger distance between their profiles.
    SqrtShare,
}

pub trait PeerCalculator {
    type E: NumberedEntity;
    type EmbBasis;
    const N_CANDIDATES: usize;
    const N_PARTITIONS: usize = 1;
    fn get_embedding_basis(&self) -> Box<[Self::EmbBasis]>;
    /// The part of a candidate's distance from `ind` that the pair alone decides.
    fn pair_distance(&self, ind: usize, candidate: usize) -> f64;
    /// The distance of each candidate from `ind`, in the candidates' order. The whole set comes at
    /// once so that a calculator can add terms put on one scale over it.
    fn final_distances<'a>(
        &'a self,
        ind: usize,
        candidates: &'a [usize],
    ) -> impl Iterator<Item = f64> + 'a {
        candidates.iter().map(move |&c| self.pair_distance(ind, c))
    }

    // Grouping for the rank-discounted bonus: candidates sharing a query's group key (e.g. country)
    // get their distance reduced by `group_discount(rank)`, where rank is their position among
    // same-group candidates ordered by base distance. Default: no grouping.
    fn group_key(&self, _ind: usize) -> Option<usize> {
        None
    }
    fn group_discount(&self, _rank: usize) -> f64 {
        0.0
    }
}

macro_rules! impl_kdpoint {
    ($($d:expr => $t:ty),*) => {
        $(
            impl KdPoint for Embed<$d> {
                type Scalar = f32;
                type Dim = $t;

                fn at(&self, k: usize) -> f32 {
                    self.coords[k]
                }
            }
        )*
    };
}

impl_kdpoint!(
    1 => typenum::U1,
    2 => typenum::U2,
    3 => typenum::U3,
    4 => typenum::U4,
    8 => typenum::U8,
    10 => typenum::U10
);

impl<const D: usize> FilterConf<D> {
    fn new(arrs: &[[u32; D]], filter: &[bool], scale: RowScale) -> Self {
        let filtered_inds: Vec<usize> = (0..arrs.len()).filter(|&i| filter[i]).collect();
        Self {
            means: filtered_means(arrs, &filtered_inds, scale),
            filtered_inds,
        }
    }
}

impl RowScale {
    fn apply<const D: usize>(self, row: &[u32; D]) -> [f32; D] {
        match self {
            Self::LogCount => row.map(tolog),
            Self::SqrtShare => {
                let total: f64 = row.iter().map(|&v| v as f64).sum();
                if total == 0.0 {
                    return [0.0; D];
                }
                row.map(|v| (v as f64 / total).sqrt() as f32)
            }
        }
    }

    fn unit_variance(self) -> bool {
        matches!(self, Self::LogCount)
    }
}

impl<const D: usize> PcaComponents<D> {
    fn from_cov<const IN_DIM: usize>(cov: DMatrix<f32>, unit_variance: bool) -> Self {
        let eigen = SymmetricEigen::new(cov);
        let mut eigenvalues = [0.0; D];
        let mut scales = [1.0; D];
        let mut components = core::array::from_fn(|_| Vec::new());
        let mut order: Vec<usize> = (0..eigen.eigenvalues.len()).collect();
        order.sort_unstable_by(|&a, &b| eigen.eigenvalues[b].total_cmp(&eigen.eigenvalues[a]));
        for (i, ei) in order.into_iter().take(D).enumerate() {
            eigenvalues[i] = eigen.eigenvalues[ei];
            if unit_variance {
                scales[i] = eigenvalues[i].sqrt().max(1e-10);
            }
            components[i] = eigen.eigenvectors.column(ei).iter().copied().collect();
        }
        println!("[pca] top {D} eigenvalues: {:?}", eigenvalues);
        PcaComponents { scales, components }
    }
}

impl<const D: usize> PartitionedTrees<D>
where
    Embed<D>: KdPoint,
    <Embed<D> as KdPoint>::Scalar: FloatCore,
{
    /// `filtered_entries` in partition order; partition `p` holds the entries at positions
    /// `p * partition_len..(p + 1) * partition_len`, so entries tied on the order value can sit in
    /// different partitions.
    fn new<T>(
        ndim_order_base: &[[f32; D]],
        n_partitions: usize,
        filtered_entries: &[(T, usize)],
    ) -> Self {
        let partition_len = filtered_entries.len().div_ceil(n_partitions).max(1);
        let trees = filtered_entries
            .chunks(partition_len)
            .map(|part| {
                KdTree::build_by_ordered_float(
                    part.iter()
                        .map(|&(_, i)| Embed {
                            coords: ndim_order_base[i],
                            eid: i,
                        })
                        .collect(),
                )
            })
            .collect();
        Self {
            partition_len,
            trees,
        }
    }

    /// The `n` points nearest to `embed`, itself left out, in `searched_partitions(pos)`.
    fn query(&self, pos: usize, embed: Embed<D>, n: usize) -> Vec<usize> {
        let mut hits: Vec<(<Embed<D> as KdPoint>::Scalar, usize)> = Vec::new();
        for tree in &self.trees[self.searched_partitions(pos)] {
            for hit in tree.nearests(&embed, n) {
                let cid = hit.item.eid;
                if cid != embed.eid {
                    hits.push((hit.squared_distance, cid));
                }
            }
        }
        hits.sort_unstable_by(|a, b| a.0.partial_cmp(&b.0).unwrap_or(Ordering::Equal));
        hits.into_iter().take(n).map(|(_, i)| i).collect()
    }

    /// The partition of the entry at `pos` and the one on either side.
    fn searched_partitions(&self, pos: usize) -> RangeInclusive<usize> {
        let part = pos / self.partition_len;
        part.saturating_sub(1)..=(part + 1).min(self.trees.len() - 1)
    }
}

/// Top subfields by specialization, not raw citations: each subfield's count is dampened by its
/// field size `G[s]^beta` (number of papers in the subfield). `beta = 0` reproduces raw-count
/// ranking; `beta = 1` ranks by the entity's share of the field. This decides which subfields enter
/// the final distance — and since `sf_log_dist` compares `ln(a) - ln(b)`, the per-subfield `G[s]^beta`
/// constant cancels there, so dampening only changes the *selection*, not the distance math.
pub fn compute_top_sfs<const ID: usize, const OD: usize>(
    arrs: &[[u32; ID]],
    field_sizes: &[f64; ID],
    beta: f64,
) -> Vec<[usize; OD]> {
    let denom: [f64; ID] = core::array::from_fn(|s| field_sizes[s].max(1.0).powf(beta));
    arrs.iter()
        .map(|arr| top_k_by_score::<OD, ID>(arr, &denom))
        .collect()
}

pub fn compute_sf_totals<const D: usize>(arrs: &[[u32; D]]) -> Vec<f64> {
    arrs.iter()
        .map(|arr| arr.iter().map(|&v| v as f64).sum())
        .collect()
}

/// The great-circle distance between two (latitude, longitude) points in degrees, squashed into
/// [0, 1): 0 at the same place and close to 1 from a few `PEER_GEO_SCALE_KM` on, so that two far
/// candidates differ little however far apart they are. A missing location (`None`) is as far as
/// the range goes from every place.
pub fn geo_dist(a: Option<(f64, f64)>, b: Option<(f64, f64)>) -> f64 {
    match (a, b) {
        (Some(a), Some(b)) => 1.0 - (-haversine_km(a, b) / PEER_GEO_SCALE_KM).exp(),
        _ => 1.0,
    }
}

/// The z-scores of the values present, over the values present; an absent value scores 0, as does
/// every value when they do not vary. A distance term standardized over one query's candidates is
/// on the scale every such term shares, so a weight says how much the term counts and not how
/// large its numbers are.
pub fn standardize(values: impl Iterator<Item = Option<f64>>) -> Vec<f64> {
    let values: Vec<Option<f64>> = values.collect();
    let present = || values.iter().flatten();
    let n = present().count() as f64;
    let mean = present().sum::<f64>() / n;
    let std = (present().map(|v| (v - mean).powi(2)).sum::<f64>() / n).sqrt();
    values
        .iter()
        .map(|v| match v {
            Some(v) if std > 0.0 => (v - mean) / std,
            _ => 0.0,
        })
        .collect()
}

/// Every row's PCA embedding, the components fitted over the rows `filter` keeps.
pub(crate) fn compute_pca<const IN_DIM: usize, const OUT_DIM: usize>(
    arrs: &[[u32; IN_DIM]],
    filter: &[bool],
    scale: RowScale,
) -> Box<[[f32; OUT_DIM]]> {
    let filter_conf = FilterConf::new(arrs, filter, scale);
    let cov = get_cov_mat(arrs, &filter_conf, scale);
    let pca_comps: PcaComponents<OUT_DIM> =
        PcaComponents::from_cov::<IN_DIM>(cov, scale.unit_variance());
    chunked_project(arrs, &filter_conf, Arc::new(pca_comps), scale).into_boxed_slice()
}

pub fn compute_peers<const D: usize, const N_PEERS: usize, C, ST>(
    stowage: &Stowage,
    calculator: &C,
    filter: &[bool],
    order_basis: &[ST],
) where
    C: PeerCalculator<EmbBasis = [f32; D]> + Sync,
    ST: Ord + Copy + Sync,
    Embed<D>: KdPoint,
    <Embed<D> as KdPoint>::Scalar: FloatCore,
    <Embed<D> as KdPoint>::Dim: Sync,
{
    let mut filtered_entries: Vec<(ST, usize)> = order_basis
        .iter()
        .enumerate()
        .filter(|(i, _)| filter[*i])
        .map(|(i, v)| (*v, i))
        .collect();
    if C::N_PARTITIONS > 1 {
        filtered_entries.sort_unstable();
    }
    let ndim_order_base = calculator.get_embedding_basis();
    let parted_trees = PartitionedTrees::new(&ndim_order_base, C::N_PARTITIONS, &filtered_entries);

    let mut peers_out = vec![[NET::<C::E>::default(); N_PEERS]; filter.len()];
    let t1 = std::time::Instant::now();
    let tc = get_chunk_size(filtered_entries.len());
    let (parted_trees, ndim_order_base) = (&parted_trees, &ndim_order_base);
    std::thread::scope(|s| {
        filtered_entries
            .chunks(tc)
            .enumerate()
            .map(|(chunk_ind, slice)| {
                s.spawn(move || {
                    slice
                        .iter()
                        .enumerate()
                        .map(|(j, &(_, dm_id))| {
                            let embed = Embed {
                                coords: ndim_order_base[dm_id],
                                eid: dm_id,
                            };
                            let pos = chunk_ind * tc + j;
                            let candidates = parted_trees.query(pos, embed, C::N_CANDIDATES);
                            let dist_iter = calculator
                                .final_distances(dm_id, &candidates)
                                .zip(candidates.iter().copied());
                            let arr = match calculator.group_key(dm_id) {
                                Some(q_key) => {
                                    let mut scored: Vec<(f64, usize)> = dist_iter.collect();
                                    let mut same: Vec<usize> = (0..scored.len())
                                        .filter(|&j| {
                                            calculator.group_key(scored[j].1) == Some(q_key)
                                        })
                                        .collect();
                                    same.sort_by(|&a, &b| scored[a].0.total_cmp(&scored[b].0));
                                    for (rank, &j) in same.iter().enumerate() {
                                        scored[j].0 -= calculator.group_discount(rank);
                                    }
                                    pick_nearest_peers::<C::E, N_PEERS, _>(scored.into_iter())
                                }
                                None => pick_nearest_peers::<C::E, N_PEERS, _>(dist_iter),
                            };
                            (dm_id, arr)
                        })
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

pub fn sf_log_dist<const N: usize>(
    arr_a: &[u32],
    arr_b: &[u32],
    top_sfs: &[usize; N],
    weights: &[f64; N],
) -> f64 {
    let mut dist = 0.0;
    for k in 0..N {
        let sf = top_sfs[k];
        let va = (arr_a[sf].max(1) as f64).ln();
        let vb = (arr_b[sf].max(1) as f64).ln();
        dist += weights[k] * (va - vb).powi(2);
    }
    dist
}

pub fn sf_rate_dist<const N: usize>(
    arr_a: &[u32],
    arr_b: &[u32],
    top_sfs: &[usize; N],
    total_a: f64,
    total_b: f64,
) -> f64 {
    // An entity without citing counts has a share of zero in every subfield.
    let share = |arr: &[u32], sf: usize, total: f64| {
        if total > 0.0 {
            arr[sf] as f64 / total
        } else {
            0.0
        }
    };
    let mut dist = 0.0;
    for &sf in top_sfs {
        dist += (share(arr_a, sf, total_a) - share(arr_b, sf, total_b)).powi(2);
    }
    dist
}

pub fn sf_peer_weights<const N: usize>() -> [f64; N] {
    core::array::from_fn(|k| 2.0 * 0.9f64.powi(k as i32))
}

pub fn compute_career_centroid(yearly_papers: &[usize]) -> Option<f32> {
    let total: usize = yearly_papers.iter().sum();
    if total == 0 {
        return None;
    }
    let weighted: f64 = yearly_papers
        .iter()
        .enumerate()
        .map(|(yr, &c)| yr as f64 * c as f64)
        .sum();
    Some((weighted / total as f64) as f32)
}

fn pick_nearest_peers<E, const N: usize, I>(dists: I) -> [NET<E>; N]
where
    E: NumberedEntity,
    I: Iterator<Item = (f64, usize)>,
{
    let mut heap = FixedHeap::<(f64, usize), N>::new();
    for e in dists {
        heap.push_unique(e);
    }
    let mut arr = [NET::<E>::default(); N];
    for (k, (_, cid)) in heap.into_iter().enumerate() {
        arr[k] = NET::<E>::from_usize(cid);
    }
    arr
}

fn top_k_by_score<const K: usize, const D: usize>(arr: &[u32; D], denom: &[f64; D]) -> [usize; K] {
    let mut h = FixedHeap::<(Reverse<f64>, usize), K>::new();
    for s in 0..D {
        h.push_unique((Reverse(arr[s] as f64 / denom[s]), s));
    }
    h.sort();
    core::array::from_fn(|i| h.arr[i].1)
}

fn haversine_km(a: (f64, f64), b: (f64, f64)) -> f64 {
    let (lat_a, lat_b) = (a.0.to_radians(), b.0.to_radians());
    let half_chord = ((lat_b - lat_a) / 2.0).sin().powi(2)
        + lat_a.cos() * lat_b.cos() * ((b.1 - a.1).to_radians() / 2.0).sin().powi(2);
    2.0 * EARTH_RADIUS_KM * half_chord.sqrt().min(1.0).asin()
}

fn get_cov_mat<const IN_DIM: usize>(
    arrs: &[[u32; IN_DIM]],
    filter_conf: &FilterConf<IN_DIM>,
    scale: RowScale,
) -> DMatrix<f32> {
    let chunk_size = get_chunk_size(filter_conf.filtered_inds.len());
    let cov_flat: Vec<f32> = std::thread::scope(|s| {
        filter_conf
            .filtered_inds
            .chunks(chunk_size)
            .map(|chunk| s.spawn(move || local_covs(chunk, &arrs, &filter_conf.means, scale)))
            .fold(vec![0.0; IN_DIM * IN_DIM], |mut acc, loc| {
                acc.iter_mut()
                    .zip(loc.join().unwrap().iter())
                    .for_each(|(a, &b)| *a += b);
                acc
            })
    });
    println!("[pca] covariance matrix assembled");
    let nf = filter_conf.filtered_inds.len() as f32;
    DMatrix::from_fn(IN_DIM, IN_DIM, |i, j| {
        let (lo, hi) = if i <= j { (i, j) } else { (j, i) };
        cov_flat[lo * IN_DIM + hi] / nf
    })
}

fn chunked_project<const IN_DIM: usize, const OUT_DIM: usize>(
    arrs: &[[u32; IN_DIM]],
    filter_conf: &FilterConf<IN_DIM>,
    pca_comps: Arc<PcaComponents<OUT_DIM>>,
    scale: RowScale,
) -> Vec<[f32; OUT_DIM]> {
    let chunk_size = get_chunk_size(arrs.len());
    let inds: Vec<usize> = (0..arrs.len()).collect();
    std::thread::scope(|s| {
        inds.chunks(chunk_size)
            .map(|chunk| {
                let apca = pca_comps.clone();
                s.spawn(move || calc_projections(chunk, &arrs, &apca, &filter_conf.means, scale))
            })
            .map(|h| h.join().unwrap())
            .flatten()
            .collect()
    })
}

fn local_covs<const IN_DIM: usize>(
    id_chunk: &[usize],
    arrs: &[[u32; IN_DIM]],
    means: &[f32],
    scale: RowScale,
) -> Vec<f32> {
    let mut local = vec![0.0; IN_DIM * IN_DIM];
    for &dm_id in id_chunk {
        let centered = centered_row(&arrs[dm_id], means, scale);
        for i in 0..IN_DIM {
            let ci = centered[i];
            for j in i..IN_DIM {
                local[i * IN_DIM + j] += ci * centered[j];
            }
        }
    }
    local
}

fn calc_projections<const IN_DIM: usize, const OUT_DIM: usize>(
    id_chunk: &[usize],
    arrs: &[[u32; IN_DIM]],
    pca_comps: &PcaComponents<OUT_DIM>,
    means: &[f32],
    scale: RowScale,
) -> Vec<[f32; OUT_DIM]> {
    id_chunk
        .iter()
        .map(|&dm_id| {
            let centered = centered_row(&arrs[dm_id], means, scale);
            core::array::from_fn(|k| {
                let dot: f32 = pca_comps.components[k]
                    .iter()
                    .zip(&centered)
                    .map(|(&c, &x)| c * x)
                    .sum();
                dot / pca_comps.scales[k]
            })
        })
        .collect::<Vec<_>>()
}

fn centered_row<const DIM: usize>(row: &[u32; DIM], means: &[f32], scale: RowScale) -> [f32; DIM] {
    let mut scaled = scale.apply(row);
    scaled.iter_mut().zip(means).for_each(|(x, m)| *x -= m);
    scaled
}

fn get_chunk_size(size: usize) -> usize {
    let n_threads = std::thread::available_parallelism().map_or(1, |p| p.get());
    (size + n_threads - 1) / n_threads
}

fn filtered_means<const DIM: usize>(
    arrs: &[[u32; DIM]],
    filtered_ids: &[usize],
    scale: RowScale,
) -> [f32; DIM] {
    let nf = filtered_ids.len() as f32;
    let mut means = [0.0; DIM];
    for &dm_id in filtered_ids {
        let x = scale.apply(&arrs[dm_id]);
        for j in 0..DIM {
            means[j] += x[j];
        }
    }
    for m in &mut means {
        *m /= nf;
    }
    means
}

fn tolog(x: u32) -> f32 {
    (x.max(1) as f32).ln()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn geo_dist_is_bounded_and_scaled_in_km() {
        let budapest = (47.4979, 19.0402);
        let vienna = (48.2082, 16.3738);
        let sydney = (-33.8688, 151.2093);
        let dist = |a, b| geo_dist(Some(a), Some(b));
        assert!((haversine_km(budapest, vienna) - 214.0).abs() < 3.0);
        assert_eq!(dist(budapest, budapest), 0.0);
        assert!(dist(budapest, vienna) < dist(budapest, sydney));
        assert!(dist(budapest, sydney) < 1.0);
        assert_eq!(geo_dist(None, Some(budapest)), 1.0);
        assert_eq!(geo_dist(None, None), 1.0);

        let scale_in_degrees = (PEER_GEO_SCALE_KM / EARTH_RADIUS_KM).to_degrees();
        let one_scale_apart = dist((0.0, 0.0), (0.0, scale_in_degrees));
        assert!((one_scale_apart - (1.0 - (-1.0f64).exp())).abs() < 1e-9);
    }

    #[test]
    fn standardize_gives_every_term_one_scale() {
        let z = |values: &[f64]| standardize(values.iter().map(|&v| Some(v)));
        let small = z(&[0.01, 0.02, 0.04]);
        let large = z(&[100.0, 200.0, 400.0]);
        for (s, l) in small.iter().zip(&large) {
            assert!((s - l).abs() < 1e-9);
        }
        assert!(small[0] < small[1] && small[1] < small[2]);
        assert!(small.iter().sum::<f64>().abs() < 1e-9);
        let variance = small.iter().map(|v| v * v).sum::<f64>() / small.len() as f64;
        assert!((variance - 1.0).abs() < 1e-9);

        assert_eq!(z(&[3.0, 3.0]), [0.0, 0.0]);
        assert!(standardize(std::iter::empty()).is_empty());
        assert_eq!(
            standardize([Some(1.0), None, Some(3.0)].into_iter()),
            [-1.0, 0.0, 1.0]
        );
    }

    #[test]
    fn a_query_reads_its_own_partition_and_its_neighbours() {
        // Work counts tied across both partition edges.
        let entries: Vec<(u32, usize)> = (0..12).map(|i| (i as u32 / 8, i)).collect();
        let basis: Vec<[f32; 1]> = (0..12).map(|i| [i as f32]).collect();
        let trees = PartitionedTrees::new(&basis, 4, &entries);
        assert_eq!(trees.searched_partitions(0), 0..=1);
        assert_eq!(trees.searched_partitions(4), 0..=2);
        assert_eq!(trees.searched_partitions(7), 1..=3);
        assert_eq!(trees.searched_partitions(11), 2..=3);
    }

    #[test]
    fn rate_dist_sets_an_empty_profile_apart() {
        let top_sfs = [0, 1];
        let focused = [90, 10, 0];
        let spread = [10, 10, 80];
        let empty = [0, 0, 0];
        let to =
            |other: &[u32; 3], total: f64| sf_rate_dist(&focused, other, &top_sfs, 100.0, total);
        assert_eq!(to(&focused, 100.0), 0.0);
        assert!(to(&empty, 0.0) > to(&spread, 100.0));
    }

    #[test]
    fn share_embedding_ignores_size() {
        let profiles: [[u32; 4]; 5] = [
            [8, 1, 1, 0],
            [1, 8, 0, 1],
            [2, 2, 3, 3],
            [0, 1, 4, 5],
            [5, 0, 5, 0],
        ];
        let grown = profiles.map(|row| row.map(|v| v * 1000));
        let rows: Vec<[u32; 4]> = profiles.into_iter().chain(grown).collect();
        let filter = vec![true; rows.len()];

        let shares: Box<[[f32; 2]]> = compute_pca(&rows, &filter, RowScale::SqrtShare);
        let logs: Box<[[f32; 2]]> = compute_pca(&rows, &filter, RowScale::LogCount);
        let apart =
            |e: &[[f32; 2]], a: usize, b: usize| (e[a][0] - e[b][0]).hypot(e[a][1] - e[b][1]);
        for i in 0..profiles.len() {
            assert!(apart(&shares, i, i + profiles.len()) < 1e-5);
            assert!(apart(&logs, i, i + profiles.len()) > 0.1);
        }
        assert!(apart(&shares, 0, 1) > 0.1);
    }
}
