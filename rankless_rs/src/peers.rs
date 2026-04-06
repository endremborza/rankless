use std::{
    cmp::{Ordering, Reverse},
    collections::BinaryHeap,
    sync::Arc,
    usize,
};

use kd_tree::{KdPoint, KdTree};
use muwo_search::{FixedHeap, Mined};
use nalgebra::{DMatrix, SymmetricEigen};
use typenum;

use dmove::UnsignedNumber;

use crate::{
    common::{NumberedEntity, PeerMarker, NET},
    Stowage,
};

pub struct GenericPeerCtx {}

pub struct PartitionedTrees<const D: usize, T>
where
    Embed<D>: KdPoint,
{
    partition_start_points: Box<[T]>,
    trees: Box<[KdTree<Embed<D>>]>,
}

struct PcaComponents<const D: usize> {
    eigenvalues: [f32; D],
    scales: [f32; D],
    components: [Vec<f32>; D],
}

struct FilterConf<const D: usize> {
    filtered_inds: Vec<usize>,
    means: [f32; D],
}

struct Embed<const D: usize> {
    pub coords: [f32; D],
    pub eid: usize,
}

pub trait PeerCalculator {
    type E: NumberedEntity;
    type EmbBasis;
    const EMBED_DIMS: usize;
    const N_CANDIDATES: usize;
    const N_PARTITIONS: usize = 1;
    fn get_embedding_basis(&self) -> Box<[Self::EmbBasis]>;
    fn final_distance_calc(&self, ind: usize, candidate_ind: usize) -> f64;
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
    2 => typenum::U2,
    3 => typenum::U3,
    4 => typenum::U4,
    8 => typenum::U8
);

impl<const D: usize> FilterConf<D> {
    fn new(arrs: &[[u32; D]], filter: &[bool]) -> Self {
        let filtered_inds: Vec<usize> = (0..arrs.len()).filter(|&i| filter[i]).collect();
        Self {
            means: filtered_logmeans(arrs, &filtered_inds),
            filtered_inds,
        }
    }
}

impl<const D: usize> PcaComponents<D> {
    fn from_cov<const IN_DIM: usize>(cov: DMatrix<f32>) -> Self {
        let eigen = SymmetricEigen::new(cov);
        let mut eigenvalues = [0.0; D];
        let mut scales = [0.0; D];
        let mut components = core::array::from_fn(|_| Vec::new());
        let mut order: Vec<usize> = (0..eigen.eigenvalues.len()).collect();
        order.sort_unstable_by(|&a, &b| {
            eigen.eigenvalues[b]
                .partial_cmp(&eigen.eigenvalues[a])
                .unwrap_or(Ordering::Equal)
        });
        for i in order.into_iter().take(D) {
            eigenvalues[i] = eigen.eigenvalues[i];
            scales[i] = eigenvalues[i].sqrt().max(1e-10);
            components[i] = eigen.eigenvectors.column(i).iter().copied().collect();
        }
        println!("[pca] top {D} eigenvalues: {:?}", eigenvalues);
        PcaComponents {
            eigenvalues,
            scales,
            components,
        }
    }
}

impl<const D: usize, T> PartitionedTrees<D, T>
where
    T: Ord + Copy,
    Embed<D>: KdPoint,
    <Embed<D> as KdPoint>::Scalar: Ord,
{
    fn new(
        ndim_order_base: &[[f32; D]],
        n_partitions: usize,
        filtered_entries: &[(T, usize)],
    ) -> Self {
        let n_filtered = filtered_entries.len();
        let chunk = (n_filtered + n_partitions - 1) / n_partitions;
        let partition_start_inds: Vec<usize> = (0..n_partitions)
            .map(|d| (d * chunk).min(n_filtered))
            .collect();

        let trees: Vec<KdTree<Embed<D>>> = partition_start_inds
            .iter()
            .enumerate()
            .map(|(d, &lo)| {
                let hi = ((d + 1) * chunk).min(n_filtered);
                KdTree::build(
                    filtered_entries[lo..hi]
                        .iter()
                        .map(|&(_v, i)| Embed {
                            coords: ndim_order_base[i],
                            eid: i,
                        })
                        .collect(),
                )
            })
            .collect();
        let partition_start_points = partition_start_inds
            .iter()
            .map(|&e| filtered_entries[e].0)
            .collect();
        Self {
            partition_start_points,
            trees: trees.into_boxed_slice(),
        }
    }

    fn query(&self, oned: T, embed: Embed<D>, n: usize) -> Vec<usize> {
        let part = self
            .partition_start_points
            .iter()
            .enumerate()
            .find_map(|(i, &s)| if s > oned { Some(i) } else { None })
            .unwrap_or(self.partition_start_points.len() - 1)
            .saturating_sub(1);
        let p_lo = part.saturating_sub(1);
        let p_hi = (part + 1).min(self.partition_start_points.len() - 1);
        let mut heap = BinaryHeap::<(<Embed<D> as KdPoint>::Scalar, usize)>::new();
        for p in p_lo..=p_hi {
            for hit in self.trees[p].nearests(&embed, n) {
                let cid = hit.item.eid;
                let dist = hit.squared_distance;
                if cid != embed.eid {
                    heap.push((dist, cid));
                }
            }
        }
        heap.into_iter().take(n).map(|(_, i)| i).collect()
    }
}

pub fn compute_peers<const D: usize, const N_PEERS: usize, C, ST>(
    stowage: &Stowage,
    calculator: &C,
    filter: &[bool],
    order_basis: Box<[ST]>,
) where
    C: PeerCalculator<EmbBasis = [f32; D]> + Sync,
    ST: Ord + Copy + Sync,
    Embed<D>: KdPoint,
    <Embed<D> as KdPoint>::Scalar: Ord,
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
    std::thread::scope(|s| {
        filtered_entries
            .chunks(tc)
            .map(|slice| {
                s.spawn(|| {
                    slice
                        .iter()
                        .map(|&(st_val, dm_id)| {
                            let embed = Embed { coords: ndim_order_base[dm_id], eid: dm_id };
                            let candidates =
                                parted_trees.query(st_val, embed, C::N_CANDIDATES);
                            let mut heap =
                                FixedHeap::<(f64, usize), { N_PEERS }>::new();
                            for c in candidates {
                                heap.push_unique((calculator.final_distance_calc(dm_id, c), c));
                            }
                            let mut arr = [NET::<C::E>::default(); N_PEERS];
                            for (k, (_, cid)) in heap.into_iter().enumerate() {
                                arr[k] = NET::<C::E>::from_usize(cid);
                            }
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
    if total_a == 0.0 || total_b == 0.0 {
        return 0.0;
    }
    let mut dist = 0.0;
    for k in 0..N {
        let sf = top_sfs[k];
        let ra = arr_a[sf] as f64 / total_a;
        let rb = arr_b[sf] as f64 / total_b;
        dist += (ra - rb).powi(2);
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

pub fn normalize_opt_arr<const DIM: usize>(embeds: Vec<[Option<f32>; DIM]>) -> Vec<[f32; DIM]> {
    let mut pf_n = 0.0;
    let mut means = [0.0; DIM];
    for arr in embeds.iter() {
        let mut any = false;
        for j in 0..DIM {
            if let Some(v) = arr[j] {
                means[j] += v;
                any = true;
            }
        }
        if any {
            pf_n += 1.0;
        }
    }
    for i in 0..DIM {
        means[i] /= pf_n;
    }
    let mut vars = [0.0; DIM];
    for arr in embeds.iter() {
        for j in 0..DIM {
            if let Some(v) = arr[j] {
                vars[j] += (v - means[j]).powi(2) / pf_n;
            }
        }
    }
    let stds: [f32; DIM] = std::array::from_fn(|i| vars[i].sqrt().max(1e-10));
    embeds
        .iter()
        .map(|e| {
            let mut arr = [0.0; DIM];
            for j in 0..DIM {
                if let Some(v) = e[j] {
                    arr[j] = (v - means[j]) / stds[j]
                }
            }
            arr
        })
        .collect()
}

fn top_k_indices<const K: usize, T>(arr: &[T]) -> [usize; K]
where
    T: Ord + Mined + Copy,
{
    let mut h = FixedHeap::<(Reverse<T>, usize), K>::new();
    for (i, v) in arr.iter().enumerate() {
        h.push_unique((Reverse(*v), i));
    }
    h.arr.sort();
    std::array::from_fn(|i| h.arr[i].1)
}

fn compute_log_pca<const IN_DIM: usize, const OUT_DIM: usize>(
    arrs: &[[u32; IN_DIM]],
    filter: &[bool],
) -> Vec<[f32; OUT_DIM]> {
    let filter_conf = FilterConf::new(arrs, filter);
    let cov = get_cov_mat(arrs, &filter_conf);
    let pca_comps: PcaComponents<OUT_DIM> = PcaComponents::from_cov::<IN_DIM>(cov);
    chunked_project(arrs, &filter_conf, Arc::new(pca_comps))
}

fn get_cov_mat<const IN_DIM: usize>(
    arrs: &[[u32; IN_DIM]],
    filter_conf: &FilterConf<IN_DIM>,
) -> DMatrix<f32> {
    let chunk_size = get_chunk_size(filter_conf.filtered_inds.len());
    let cov_flat: Vec<f32> = std::thread::scope(|s| {
        filter_conf
            .filtered_inds
            .chunks(chunk_size)
            .map(|chunk| s.spawn(move || local_covs(chunk, &arrs, &filter_conf.means)))
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
) -> Vec<[f32; OUT_DIM]> {
    let chunk_size = get_chunk_size(arrs.len());
    let inds: Vec<usize> = (0..arrs.len()).collect();
    std::thread::scope(|s| {
        inds.chunks(chunk_size)
            .map(|chunk| {
                let apca = pca_comps.clone();
                s.spawn(move || calc_projections(chunk, &arrs, &apca, &filter_conf.means))
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
) -> Vec<f32> {
    let mut local = vec![0.0; IN_DIM * IN_DIM];
    let mut centered = [0.0; IN_DIM];
    for &dm_id in id_chunk {
        let x = arrs[dm_id];
        for j in 0..IN_DIM {
            centered[j] = tolog(x[j]) - means[j];
        }
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
) -> Vec<[f32; OUT_DIM]> {
    id_chunk
        .iter()
        .map(|&dm_id| {
            let x = arrs[dm_id];
            core::array::from_fn(|k| {
                let dot: f32 = pca_comps.components[k]
                    .iter()
                    .enumerate()
                    .map(|(j, &c)| c * (tolog(x[j]) - means[j]))
                    .sum();
                (dot / pca_comps.scales[k]) as f32
            })
        })
        .collect::<Vec<_>>()
}

fn get_chunk_size(size: usize) -> usize {
    let n_threads = std::thread::available_parallelism().map_or(1, |p| p.get());
    (size + n_threads - 1) / n_threads
}

fn filtered_logmeans<const DIM: usize>(
    arrs: &[[u32; DIM]],
    filtered_ids: &Vec<usize>,
) -> [f32; DIM] {
    let n_filtered = filtered_ids.len();
    let nf = n_filtered as f32;
    let mut means = [0.0; DIM];
    for &dm_id in filtered_ids {
        let x = &arrs[dm_id];
        for j in 0..DIM {
            means[j] += tolog(x[j]);
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
