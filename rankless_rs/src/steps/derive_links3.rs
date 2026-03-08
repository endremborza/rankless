use std::{
    cmp::Ordering,
    collections::BinaryHeap,
    ops::AddAssign,
    sync::{Arc, Mutex},
};

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
// Fraction of total filtered authors to include as candidates below/above the hero.
const CANDIDATE_PCTILE_LOW: f64 = 0.05;
const CANDIDATE_PCTILE_HIGH: f64 = 0.05;
// Top subfield dimensions used in the weighted distance metric.
const N_PEER_SF_DIMS: usize = 10;

pub const AUTHOR_BLACKLIST: [u64; 3] = [
    5030786976, //Lynnette Nathalie Lyzwinski
    5036138197, //David S. Gokhin
    5034807195, //Shadi Yarandi
];

type CCUI = ET<MAA<Works, CiteCountMarker>>;
type AuthorId = ET<Authors>;
type AuthorCitSfArr = ET<MAA<Authors, CitSubfieldsArrayMarker>>;

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
    dm_to_rank: Arc<Vec<usize>>,
    sf_weights: [f64; N_PEER_SF_DIMS],
    n: usize,
    peers: Arc<Mutex<Vec<[AuthorId; N_PEERS]>>>,
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
            if cand_dm_id == dm_id {
                continue;
            }
            let dist_sq = peer_sq_dist(
                ref_coord,
                cand_coord,
                hero_arr,
                &self.cit_sfs[cand_dm_id],
                &top_sfs,
                &self.sf_weights,
            );
            if heap.len() < N_PEERS || dist_sq < heap.peek().unwrap().dist_sq {
                if heap.len() >= N_PEERS {
                    heap.pop();
                }
                heap.push(PeerCandidate {
                    dist_sq,
                    dm_id: cand_dm_id as AuthorId,
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
    let mut top = [(0usize, 0usize); N_PEER_SF_DIMS]; // (val, sf_idx)
    let mut min_val = 0usize;
    let mut min_pos = 0;
    for (sf, &v) in arr.iter().enumerate() {
        if v > min_val {
            top[min_pos] = (v, sf);
            min_val = usize::MAX;
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

fn compute_author_peers(stowage: &Stowage, coords: &[[f64; 2]], filter: &[u8]) {
    let cit_sfs =
        Arc::new(stowage.get_marked_interface::<Authors, CitSubfieldsArrayMarker, QuickestBox>());

    // Sort filtered authors by normalized ln_cites (coord[0]) to enable percentile windows.
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

    // Weights: 2.0 * 0.9^k for k = 0..N_PEER_SF_DIMS (applied to top subfields, descending).
    let sf_weights: [f64; N_PEER_SF_DIMS] = core::array::from_fn(|k| 2.0 * 0.9f64.powi(k as i32));

    let peers_out = Arc::new(Mutex::new(vec![
        [AuthorId::default(); N_PEERS];
        coords.len()
    ]));
    let entries_arc = Arc::new(entries);
    PeerWorker {
        entries: entries_arc.clone(),
        cit_sfs,
        dm_to_rank: Arc::new(dm_to_rank),
        sf_weights,
        n,
        peers: peers_out.clone(),
    }
    .para(entries_arc.iter().copied());

    let peers = Arc::try_unwrap(peers_out).unwrap().into_inner().unwrap();
    println!("computed peers for {} filtered authors", n);
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
