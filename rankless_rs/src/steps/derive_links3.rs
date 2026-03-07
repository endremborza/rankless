use std::{cmp::Ordering, collections::BinaryHeap, ops::AddAssign, sync::Arc};

use crate::{
    common::{
        init_empty_slice, reverse_id, CoordinateMarker, MainWorkMarker, NameMarker,
        PageFilterMarker, PeerAuthorMarker, Top3CitingSfMarker, Top3PaperSfMarker,
        YearlyPapersMarker,
    },
    env_consts::FINAL_YEAR,
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{AuthorNobels, WorkDois, WorkTopics, WorkYears, WorksNames},
        derive_links1::{WorkFilteredAuthors, WorkSubfields},
        derive_links2::{AuthorWorks, SourceStats},
    },
    steps::{
        a1_entity_mapping::{YearInterface, Years},
        derive_links2::Top3Rec,
    },
    CiteCountMarker, QuickestBox, QuickestVBox, ReadIter, Stowage, WorkCountMarker,
};
use dmove::{
    para_multi_gen_run, BigId, Data64MappedEntityBuilder, DowncastingBuilder, Entity,
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
const N_PEERS: usize = 5;
const N_COORD_CANDIDATES: usize = 1000;

pub const AUTHOR_BLACKLIST: [u64; 3] = [
    5030786976, //Lynnette Nathalie Lyzwinski
    5036138197, //David S. Gokhin
    5034807195, //Shadi Yarandi
];

type CCUI = ET<MAA<Works, CiteCountMarker>>;

struct CoordCandidate {
    sq_dist: f64,
    idx: usize,
}

struct PeerCandidate {
    neg_similarity: i32,
    coord_dist_sq: f64,
    dm_id: u16,
}

impl PartialEq for CoordCandidate {
    fn eq(&self, other: &Self) -> bool {
        self.sq_dist == other.sq_dist
    }
}
impl Eq for CoordCandidate {}
impl PartialOrd for CoordCandidate {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}
impl Ord for CoordCandidate {
    fn cmp(&self, other: &Self) -> Ordering {
        self.sq_dist
            .partial_cmp(&other.sq_dist)
            .unwrap_or(Ordering::Equal)
    }
}

impl PartialEq for PeerCandidate {
    fn eq(&self, other: &Self) -> bool {
        self.neg_similarity == other.neg_similarity && self.coord_dist_sq == other.coord_dist_sq
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
        self.neg_similarity.cmp(&other.neg_similarity).then(
            self.coord_dist_sq
                .partial_cmp(&other.coord_dist_sq)
                .unwrap_or(Ordering::Equal),
        )
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

fn sf_overlap(a: &Top3Rec<Subfields>, b: &Top3Rec<Subfields>) -> u32 {
    let mut count = 0u32;
    for &(a_count, aid) in a {
        if a_count == 0 {
            continue;
        }
        for &(b_count, bid) in b {
            if b_count > 0 && aid == bid {
                count += 1;
                break;
            }
        }
    }
    count
}

// Returns up to N_COORD_CANDIDATES nearest neighbours of entries[si] by Euclidean
// distance in the 2-D coordinate space, using the sorted order of entries on axis 0
// to prune. Safe to call as a fallback but should not be the primary candidate source:
// for extreme outliers the threshold can inflate (via high-d1 candidates filling the
// heap early) and allow authors with very different citation counts to pass the x-prune.
fn coord_candidates(
    si: usize,
    ref_coord: [f64; 2],
    entries: &[(usize, [f64; 2])],
) -> BinaryHeap<CoordCandidate> {
    let mut heap: BinaryHeap<CoordCandidate> = BinaryHeap::new();
    let mut lo = si as isize - 1;
    let mut hi = si + 1;
    loop {
        let lo_valid = lo >= 0;
        let hi_valid = hi < entries.len();
        if !lo_valid && !hi_valid {
            break;
        }
        let lo_d0 = if lo_valid {
            (entries[lo as usize].1[0] - ref_coord[0]).abs()
        } else {
            f64::MAX
        };
        let hi_d0 = if hi_valid {
            (entries[hi].1[0] - ref_coord[0]).abs()
        } else {
            f64::MAX
        };
        let (cand_si, is_lo) = if lo_d0 <= hi_d0 {
            (lo as usize, true)
        } else {
            (hi, false)
        };
        let d0 = entries[cand_si].1[0] - ref_coord[0];
        let d0_sq = d0 * d0;
        let threshold = if heap.len() >= N_COORD_CANDIDATES {
            heap.peek().unwrap().sq_dist
        } else {
            f64::MAX
        };
        if d0_sq > threshold {
            break;
        }
        let d1 = entries[cand_si].1[1] - ref_coord[1];
        let sq_dist = d0_sq + d1 * d1;
        if sq_dist < threshold {
            if heap.len() >= N_COORD_CANDIDATES {
                heap.pop();
            }
            heap.push(CoordCandidate {
                sq_dist,
                idx: cand_si,
            });
        }
        if is_lo {
            lo -= 1;
        } else {
            hi += 1;
        }
    }
    heap
}

// From a set of (cand_dm_id, sq_dist) candidates already known to be field-relevant,
// selects the N_PEERS best by (sf_overlap descending, sq_dist ascending).
fn select_peers(
    dm_id: usize,
    candidates: &[(usize, f64)],
    citing_sfs: &[Top3Rec<Subfields>],
    paper_sfs: &[Top3Rec<Subfields>],
) -> [u16; N_PEERS] {
    let mut heap: BinaryHeap<PeerCandidate> = BinaryHeap::new();
    for &(cand_dm_id, sq_dist) in candidates {
        let sim = sf_overlap(&citing_sfs[dm_id], &citing_sfs[cand_dm_id])
            + sf_overlap(&paper_sfs[dm_id], &paper_sfs[cand_dm_id]);
        let pc = PeerCandidate {
            neg_similarity: -(sim as i32),
            coord_dist_sq: sq_dist,
            dm_id: cand_dm_id as u16,
        };
        if heap.len() < N_PEERS || pc < *heap.peek().unwrap() {
            if heap.len() >= N_PEERS {
                heap.pop();
            }
            heap.push(pc);
        }
    }
    let mut out = [0u16; N_PEERS];
    for (i, pc) in heap.into_sorted_vec().into_iter().enumerate() {
        out[i] = pc.dm_id;
    }
    out
}

fn compute_author_peers(stowage: &Stowage, coords: &[[f64; 2]], filter: &[u8]) {
    let citing_sfs = stowage.get_marked_interface::<Authors, Top3CitingSfMarker, QuickestBox>();
    let paper_sfs = stowage.get_marked_interface::<Authors, Top3PaperSfMarker, QuickestBox>();

    // Coordinates are pre-normalized by entity_coords_filter! over the page-filtered set.
    let mut entries: Vec<(usize, [f64; 2])> = filter
        .iter()
        .enumerate()
        .filter(|(_, &f)| f > 0)
        .map(|(i, _)| (i, coords[i]))
        .collect();

    // Build per-subfield sorted lists: sf_dm_id → [(author_dm_id, norm_coord)].
    // NET<Subfields> = u8 (N=254), so 256 slots covers all valid dm_ids.
    // These are the primary candidate source: field-first guarantees all candidates
    // share at least one top subfield with the hero, eliminating the coordinate-only
    // contamination by field-unrelated authors.
    const N_SFS: usize = 256;
    let mut sf_to_entries: Vec<Vec<(usize, [f64; 2])>> = vec![Vec::new(); N_SFS];
    for &(dm_id, coord) in &entries {
        let mut seen_sfs = [usize::MAX; 6];
        let mut n_seen = 0usize;
        for t3 in [&citing_sfs[dm_id], &paper_sfs[dm_id]] {
            for &(count, sf_id) in t3.iter() {
                if count == 0 {
                    continue;
                }
                let sf = sf_id.to_usize();
                if seen_sfs[..n_seen].contains(&sf) {
                    continue;
                }
                seen_sfs[n_seen] = sf;
                n_seen += 1;
                sf_to_entries[sf].push((dm_id, coord));
            }
        }
    }
    for list in &mut sf_to_entries {
        list.sort_by(|a, b| a.1[0].partial_cmp(&b.1[0]).unwrap_or(Ordering::Equal));
    }

    entries.sort_by(|a, b| a.1[0].partial_cmp(&b.1[0]).unwrap_or(Ordering::Equal));

    // dm_id → index in sorted entries (needed for fallback coord_candidates).
    let mut dm_to_si = vec![0usize; coords.len()];
    for (si, &(dm_id, _)) in entries.iter().enumerate() {
        dm_to_si[dm_id] = si;
    }

    let half_window = N_COORD_CANDIDATES / 2;
    let mut peers = vec![[0u16; N_PEERS]; coords.len()];
    for &(dm_id, ref_coord) in &entries {
        let hero_citing = &citing_sfs[dm_id];
        let hero_paper = &paper_sfs[dm_id];

        // --- Candidate selection (field-first) ---
        // For each of the hero's top subfields, take the half_window nearest authors
        // above and below in sorted ln_cites order. All candidates share at least one
        // top subfield with the hero, so field relevance is guaranteed by construction.
        let mut seen: HashSet<usize> = HashSet::new();
        seen.insert(dm_id);
        let mut candidates: Vec<(usize, f64)> = Vec::new();

        for t3 in [hero_citing, hero_paper] {
            for &(count, sf_id) in t3.iter() {
                if count == 0 {
                    continue;
                }
                let list = &sf_to_entries[sf_id.to_usize()];
                let pos = list.partition_point(|&(_, c)| c[0] < ref_coord[0]);
                let lo = pos.saturating_sub(half_window);
                let hi = (pos + half_window).min(list.len());
                for &(cand_dm_id, cand_coord) in &list[lo..hi] {
                    if !seen.insert(cand_dm_id) {
                        continue;
                    }
                    let d0 = cand_coord[0] - ref_coord[0];
                    let d1 = cand_coord[1] - ref_coord[1];
                    candidates.push((cand_dm_id, d0 * d0 + d1 * d1));
                }
            }
        }

        // --- Fallback: coordinate-only search when field-matched pool is thin ---
        // This preserves output for authors in niche fields with few filtered peers.
        if candidates.len() < N_PEERS {
            let si = dm_to_si[dm_id];
            for cc in coord_candidates(si, ref_coord, &entries) {
                let (cand_dm_id, _) = entries[cc.idx];
                if seen.insert(cand_dm_id) {
                    candidates.push((cand_dm_id, cc.sq_dist));
                }
            }
        }

        // --- Peer selection from candidates ---
        peers[dm_id] = select_peers(dm_id, &candidates, &citing_sfs, &paper_sfs);
    }

    println!("computed peers for {} filtered authors", entries.len());
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
