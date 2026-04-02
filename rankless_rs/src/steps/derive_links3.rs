use std::{collections::BinaryHeap, ops::AddAssign, sync::Arc};

use dmove::{
    para_multi_gen_run, BigId, ByteFixArrayInterface, CompactEntity, Data64MappedEntityBuilder,
    DowncastingBuilder, Entity, MarkedAttribute, NamespacedEntity, UnsignedNumber, VarAttBuilder,
    VarSizedAttributeElement, VariableSizeAttribute, ET, MAA,
};
use hashbrown::{HashMap, HashSet};

use crate::{
    common::{
        init_empty_slice, reverse_id, CitSubfieldsArrayMarker, CoordinateMarker, MainWorkMarker,
        NameMarker, PageFilterMarker, YearlyPapersMarker,
    },
    env_consts::FINAL_YEAR,
    filter::FIX_AUTHORS,
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{
            AuthorNobels, InstCountries, InstLocs, WorkDois, WorkTopics, WorkYears, WorksNames,
        },
        derive_links1::{WorkFilteredAuthors, WorkSubfields},
        derive_links2::{AuthorWorks, SourceStats},
    },
    peers,
    steps::a1_entity_mapping::{YearInterface, Years},
    CiteCountMarker, QuickestBox, QuickestVBox, ReadIter, Stowage, WorkCountMarker,
};

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

pub const AUTHOR_BLACKLIST: [u64; 3] = [
    5030786976, //Lynnette Nathalie Lyzwinski
    5036138197, //David S. Gokhin
    5034807195, //Shadi Yarandi
];

type CCUI = ET<MAA<Works, CiteCountMarker>>;

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

    let (cc_interface, w_sfs, w_topics, w_years, doi_interface) = std::thread::scope(|s| {
        let h_cc =
            s.spawn(|| starc.get_entity_interface::<MAA<Works, CiteCountMarker>, QuickestBox>());
        let h_sfs = s.spawn(|| starc.get_entity_interface::<WorkSubfields, QuickestVBox>());
        let h_topics = s.spawn(|| starc.get_entity_interface::<WorkTopics, QuickestVBox>());
        let h_years = s.spawn(|| starc.get_entity_interface::<WorkYears, QuickestBox>());
        let h_doi = s.spawn(|| starc.get_entity_interface::<WorkDois, QuickestVBox>());
        (
            h_cc.join().unwrap(),
            h_sfs.join().unwrap(),
            h_topics.join().unwrap(),
            h_years.join().unwrap(),
            h_doi.join().unwrap(),
        )
    });
    let nobeled_works = get_nobeled_works(&starc, &w_years);

    let topic_limits = get_limits::<Topics, _, _, _>(
        TOP_TOPIC,
        w_topics.0.iter().map(|e| e.iter().map(|se| *se)),
        &cc_interface,
    );

    let (year_bms, sf_bms) = std::thread::scope(|s| {
        let h1 = s.spawn(|| compute_year_bms(&w_years, &cc_interface));
        let h2 = s.spawn(|| compute_sf_bms(&w_sfs.0, &cc_interface));
        (h1.join().unwrap(), h2.join().unwrap())
    });
    let sf_year_bms = compute_sf_year_bms(&w_sfs.0, &w_years, &cc_interface, &year_bms);

    let name_interface = starc.get_entity_interface::<WorksNames, ReadIter>();
    let mut hit_names = vec!["Unknown".to_string()];
    let mut hit_dois = vec!["".to_string()];
    let mut hit_ccounts = vec![0];
    let mut hit_bms = vec![0usize];
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
            hit_bms.push(bm.round() as usize);
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
    starc.add_iter_owned::<DowncastingBuilder, _, _>(
        hit_bms.into_iter(),
        Some("hit-papers-benchmarks"),
    );

    let source_stats = starc.get_entity_interface::<SourceStats, QuickestBox>();
    let sf_weights = peers::sf_peer_weights();

    let (inst_sfs, sf_sfs, country_sfs, source_sfs) = std::thread::scope(|s| {
        let h1 = s.spawn(|| {
            starc.get_marked_interface::<Institutions, CitSubfieldsArrayMarker, QuickestBox>()
        });
        let h2 = s.spawn(|| {
            starc.get_marked_interface::<Subfields, CitSubfieldsArrayMarker, QuickestBox>()
        });
        let h3 = s.spawn(|| {
            starc.get_marked_interface::<Countries, CitSubfieldsArrayMarker, QuickestBox>()
        });
        let h4 = s.spawn(|| {
            starc.get_marked_interface::<Sources, CitSubfieldsArrayMarker, QuickestBox>()
        });
        (
            h1.join().unwrap(),
            h2.join().unwrap(),
            h3.join().unwrap(),
            h4.join().unwrap(),
        )
    });
    let inst_locs = starc.get_entity_interface::<InstLocs, QuickestBox>();
    let inst_countries = starc.get_entity_interface::<InstCountries, QuickestBox>();

    std::thread::scope(|s| {
        let h_inst = s.spawn(|| {
            let top_sfs = peers::compute_top_sfs(&*inst_sfs);
            let sf_totals = peers::compute_sf_totals(&*inst_sfs);
            let (coords, filter) = entity_coords_filter::<Institutions, _>(&starc, |_, _, _| true);
            peers::compute_peers::<Institutions>(&starc, &coords, &filter, 10, |a, b, ca, cb| {
                peers::W_PEER_COORD * peers::coord_sq_dist(ca, cb)
                    + peers::W_PEER_SF
                        * peers::sf_log_dist(&inst_sfs[a], &inst_sfs[b], &top_sfs[a], &sf_weights)
                    + peers::W_PEER_RATE
                        * peers::sf_rate_dist(
                            &inst_sfs[a],
                            &inst_sfs[b],
                            &top_sfs[a],
                            sf_totals[a],
                            sf_totals[b],
                        )
                    + peers::W_PEER_GEO * peers::geo_sq_dist(inst_locs[a], inst_locs[b])
                    + peers::W_PEER_COUNTRY
                        * if inst_countries[a] != inst_countries[b] {
                            1.0
                        } else {
                            0.0
                        }
            });
        });
        let h_sf = s.spawn(|| {
            let top_sfs = peers::compute_top_sfs(&*sf_sfs);
            let (coords, filter) = entity_coords_filter::<Subfields, _>(&starc, |_, _, _| true);
            peers::compute_peers::<Subfields>(&starc, &coords, &filter, 1, |a, b, ca, cb| {
                peers::W_PEER_COORD * peers::coord_sq_dist(ca, cb)
                    + peers::W_PEER_SF
                        * peers::sf_log_dist(&sf_sfs[a], &sf_sfs[b], &top_sfs[a], &sf_weights)
            });
        });
        let h_country = s.spawn(|| {
            let top_sfs = peers::compute_top_sfs(&*country_sfs);
            let (coords, filter) = entity_coords_filter::<Countries, _>(&starc, |_, _, _| true);
            peers::compute_peers::<Countries>(&starc, &coords, &filter, 1, |a, b, ca, cb| {
                peers::W_PEER_COORD * peers::coord_sq_dist(ca, cb)
                    + peers::W_PEER_SF
                        * peers::sf_log_dist(
                            &country_sfs[a],
                            &country_sfs[b],
                            &top_sfs[a],
                            &sf_weights,
                        )
            });
        });
        let h_source = s.spawn(|| {
            let top_sfs = peers::compute_top_sfs(&*source_sfs);
            let sf_totals = peers::compute_sf_totals(&*source_sfs);
            let (coords, filter) = entity_coords_filter::<Sources, _>(&starc, |i, c, p| {
                p > 10 && c > 20 && source_stats[i].1 <= 2
            });
            peers::compute_peers::<Sources>(&starc, &coords, &filter, 10, |a, b, ca, cb| {
                peers::W_PEER_COORD * peers::coord_sq_dist(ca, cb)
                    + peers::W_PEER_SF
                        * peers::sf_log_dist(
                            &source_sfs[a],
                            &source_sfs[b],
                            &top_sfs[a],
                            &sf_weights,
                        )
                    + peers::W_PEER_RATE
                        * peers::sf_rate_dist(
                            &source_sfs[a],
                            &source_sfs[b],
                            &top_sfs[a],
                            sf_totals[a],
                            sf_totals[b],
                        )
            });
        });
        for h in [h_inst, h_sf, h_country, h_source] {
            h.join().unwrap();
        }
    });

    let author_yearly_papers =
        starc.get_marked_interface::<Authors, YearlyPapersMarker, QuickestBox>();
    let author_oa_ids = reverse_id::<Authors>(&starc);
    let (author_coords, author_filter) = entity_coords_filter::<Authors, _>(&starc, |i, _c, p| {
        FIX_AUTHORS.contains(&author_oa_ids[i])
            || (p < 10_000
                && *author_yearly_papers[i].iter().max().unwrap_or(&0) < 300
                && !AUTHOR_BLACKLIST.contains(&author_oa_ids[i]))
    });

    let author_sfs = starc.get_marked_interface::<Authors, CitSubfieldsArrayMarker, QuickestBox>();
    let top_sfs = peers::compute_top_sfs(&*author_sfs);
    let career_centroids = peers::compute_career_centroids(&*author_yearly_papers, &author_filter);

    println!("computing author peers");
    peers::compute_pca_peers::<Authors, _>(
        &starc,
        &author_coords,
        &author_filter,
        &*author_sfs,
        |a, b, ca, cb| {
            peers::W_PEER_COORD * peers::coord_sq_dist(ca, cb)
                + peers::W_PEER_SF
                    * peers::sf_log_dist(&author_sfs[a], &author_sfs[b], &top_sfs[a], &sf_weights)
                + peers::W_PEER_TEMPORAL
                    * (career_centroids[a] - career_centroids[b]).powi(2) as f64
        },
    );

    starc.write_code()?;
    Ok(())
}

fn entity_coords_filter<E, F>(stowage: &Stowage, extra: F) -> (Vec<[f64; 2]>, Vec<u8>)
where
    E: Entity
        + MarkedAttribute<CiteCountMarker>
        + MarkedAttribute<NameMarker>
        + MarkedAttribute<MainWorkMarker>,
    MAA<E, CiteCountMarker>: NamespacedEntity + CompactEntity,
    ET<MAA<E, CiteCountMarker>>: UnsignedNumber + ByteFixArrayInterface,
    MAA<E, NameMarker>: Entity<T = String> + NamespacedEntity + VariableSizeAttribute,
    MAA<E, MainWorkMarker>: Entity + NamespacedEntity + VariableSizeAttribute,
    ET<MAA<E, MainWorkMarker>>: VarSizedAttributeElement + AsRef<[ET<Works>]>,
    F: Fn(usize, usize, usize) -> bool,
{
    let cites = stowage.get_marked_interface::<E, CiteCountMarker, QuickestBox>();
    let wcounts: Vec<usize> = stowage
        .get_entity_interface::<MAA<E, MainWorkMarker>, ReadIter>()
        .map(|works| works.as_ref().len())
        .collect();
    let n = cites.len();
    let mut filter = Vec::with_capacity(n);
    for (i, name) in stowage
        .get_entity_interface::<MAA<E, NameMarker>, ReadIter>()
        .enumerate()
    {
        let c = cites[i].to_usize();
        let p = wcounts[i];
        let cf = c as f64;
        coords.push([
            f64::max(cf, COORD_MIN_CITES).ln(),
            f64::max(p as f64, COORD_MIN_PAPERS).ln(),
        ]);
        let base = name.trim().len() > 0 && p > 1 && c > 2;
        filter.push(if base && extra(i, c, p) { 1u8 } else { 0u8 });
    }
    peers::normalize_coords_inplace(&mut coords, &filter);
    stowage.ditf::<PageFilterMarker, E, _>(filter.clone(), "page-filter");
    (coords, filter)
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
