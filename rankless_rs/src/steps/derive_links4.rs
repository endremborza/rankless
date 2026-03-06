use hashbrown::{HashMap, HashSet};
use muwo_search::FixedHeap;
use std::{cmp::Reverse, io, sync::Arc};
use tqdm::Iter;

use dmove::{
    para_multi_gen_run, BigId, Entity, LoadedIdMap, MarkedAttribute, NamespacedEntity,
    UnsignedNumber, VarAttBuilder, VariableSizeAttribute, ET, MAA,
};

use crate::{
    common::{init_empty_slice, EmptyAttributeEntity, HitWorkMarker, MainWorkMarker},
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{WorkReferences, WorkYears},
        derive_links1::WorkFilteredAuthors,
        derive_links2::{SourceStats, WorkCitingCounts, WorkTopSource},
        derive_links3::{
            HitPapers, HitPapersCiteCounts, HitPapersDois, HitPapersNames, HitPapersWids,
        },
    },
    steps::derive_links3::{get_nobeled_works, COORD_MIN_CITES, COORD_MIN_PAPERS},
    CiteCountMarker, CoordinateMarker, NameExtensionMarker, NameMarker, PageFilterMarker,
    QuickestBox, QuickestNumbered, QuickestVBox, ReadIter, SemanticIdMarker, Stowage,
};

// Metric weights for scoring hit-paper connections.
// Score = (cite_count * CITE_COUNT_WEIGHT + source_prestige * SOURCE_PRESTIGE_WEIGHT + 1)
// Direct connections are multiplied by DIRECT_MULTIPLIER before comparison.
// Source prestige = (5 - min(quartile, 5)) * h_index * 2 + median_citations * 3
// Nobel laureate reference authors get an additional NOBEL_MULTIPLIER on direct connections,
// biasing their top-50 toward hit papers that directly cited their work.
const CITE_COUNT_WEIGHT: u64 = 3;
const SOURCE_PRESTIGE_WEIGHT: u64 = 5;
const DIRECT_MULTIPLIER: u64 = 3;
const NOBEL_MULTIPLIER: u64 = 2;
const TOP_HIT_PAPERS: usize = 50;

fn citing_score(cite_count: ET<WorkCitingCounts>, stats: ([u32; 2], u8)) -> u64 {
    let ([h, median], q) = stats;
    let prestige = (5u32.saturating_sub(q as u32)) * h * 2 + median * 3;
    cite_count as u64 * CITE_COUNT_WEIGHT + prestige as u64 * SOURCE_PRESTIGE_WEIGHT + 1
}

fn sorted_hit_papers<E>(
    parc: &(
        Stowage,
        LoadedIdMap<ET<HitPapers>>,
        Box<[ET<WorkCitingCounts>]>,
    ),
) where
    E: MarkedAttribute<MainWorkMarker>,
    MAA<E, MainWorkMarker>: Entity<T = Box<[ET<Works>]>> + NamespacedEntity + VariableSizeAttribute,
{
    let hits = parc
        .0
        .get_entity_interface::<MAA<E, MainWorkMarker>, ReadIter>()
        .map(|e| {
            let mut v: Vec<(ET<HitPapers>, usize)> = e
                .iter()
                .filter_map(|wid| match parc.1 .0.get(&(*wid as BigId)) {
                    Some(hw) => Some((*hw, wid.to_usize())),
                    None => None,
                })
                .collect();
            v.sort_by(|l, r| parc.2[r.1].cmp(&parc.2[l.1]));
            v.into_iter()
                .map(|(hid, _)| hid)
                .collect::<Vec<ET<HitPapers>>>()
                .into_boxed_slice()
        });
    parc.0
        .declare_iter::<VarAttBuilder, _, _, E, HitWorkMarker>(hits, &format!("{}-hits", E::NAME));
}

impl MarkedAttribute<NameMarker> for HitPapers {
    type AttributeEntity = HitPapersNames;
}

impl MarkedAttribute<SemanticIdMarker> for HitPapers {
    type AttributeEntity = HitPapersDois;
}

impl MarkedAttribute<CiteCountMarker> for HitPapers {
    type AttributeEntity = HitPapersCiteCounts;
}

impl MarkedAttribute<MainWorkMarker> for HitPapers {
    type AttributeEntity = HitPapersWids;
}

impl MarkedAttribute<NameExtensionMarker> for HitPapers {
    type AttributeEntity = EmptyAttributeEntity<String>;
}

pub fn main(stowage: Stowage) -> io::Result<()> {
    let hit_map = stowage.get_entity_interface::<HitPapers, QuickestNumbered>();
    let wcc = stowage.get_entity_interface::<WorkCitingCounts, QuickestBox>();
    let wor_refs = stowage.get_entity_interface::<WorkReferences, QuickestVBox>();
    let w2a = stowage.get_entity_interface::<WorkFilteredAuthors, QuickestVBox>();
    let wts = stowage.get_entity_interface::<WorkTopSource, QuickestBox>();
    let w_years = stowage.get_entity_interface::<WorkYears, QuickestBox>();
    let ss = stowage.get_entity_interface::<SourceStats, QuickestBox>();
    let nobeled_works = get_nobeled_works(&stowage, &w_years);

    let parc = Arc::new((stowage, hit_map, wcc));
    para_multi_gen_run!(sorted_hit_papers, Institutions, Authors, Countries, Sources, Subfields, Topics; parc).last();

    let mut direct = init_empty_slice::<Authors, HashMap<ET<HitPapers>, u64>>();
    let mut once_removed = init_empty_slice::<Authors, HashMap<ET<HitPapers>, u64>>();

    for (&hp_wid_big, &hp_id) in parc.1 .0.iter().tqdm().desc(Some("hit papers for authors")) {
        let hp_widu = hp_wid_big.to_usize();
        let hp_authors: HashSet<ET<Authors>> = w2a.0[hp_widu].iter().copied().collect();
        let mut base_score = citing_score(parc.2[hp_widu], ss[wts[hp_widu] as usize]);
        if nobeled_works.contains(&ET::<Works>::from_usize(hp_widu)) {
            base_score = base_score * NOBEL_MULTIPLIER;
        }
        let direct_score = base_score * DIRECT_MULTIPLIER;

        for &ref_wid in wor_refs.0[hp_widu].iter() {
            let ru = ref_wid.to_usize();
            let ref_authors = &w2a.0[ru];
            for &aid in ref_authors.iter() {
                if !hp_authors.contains(&aid) {
                    let aid_u = aid.to_usize();
                    direct[aid_u]
                        .entry(hp_id)
                        .and_modify(|s| *s = (*s).max(direct_score))
                        .or_insert(direct_score);
                }
            }

            for &ref2_wid in wor_refs.0[ru].iter() {
                let r2u = ref2_wid.to_usize();
                let ref2_authors = &w2a.0[r2u];
                for &aid in ref2_authors.iter() {
                    let aid_u = aid.to_usize();
                    if !hp_authors.contains(&aid)
                        && !ref_authors.contains(&aid)
                        && !direct[aid_u].contains_key(&hp_id)
                    {
                        once_removed[aid_u]
                            .entry(hp_id)
                            .and_modify(|s| *s = (*s).max(base_score))
                            .or_insert(base_score);
                    }
                }
            }
        }
    }

    let n_direct: usize = direct.iter().map(|m| m.len()).sum();
    let n_once: usize = once_removed.iter().map(|m| m.len()).sum();
    println!("direct: {n_direct} total entries, once_removed: {n_once} total entries");

    // Select top-50 hit papers per author across both direct and once-removed,
    // then split back into the two output attributes.
    let (direct_out, once_out): (Vec<_>, Vec<_>) = direct
        .into_vec()
        .into_iter()
        .zip(once_removed.into_vec())
        .map(|(dm, orm)| {
            let mut heap = FixedHeap::<Reverse<(u64, ET<HitPapers>)>, TOP_HIT_PAPERS>::new();
            for (&hp_id, &score) in dm.iter().chain(orm.iter()) {
                heap.push_unique(Reverse((score, hp_id)));
            }
            let top: HashSet<ET<HitPapers>> =
                heap.into_iter().map(|Reverse((_, hp_id))| hp_id).collect();
            let mut direct_v: Vec<ET<HitPapers>> = dm
                .into_iter()
                .filter_map(|(hp, _)| top.contains(&hp).then_some(hp))
                .collect();
            let mut once_v: Vec<ET<HitPapers>> = orm
                .into_iter()
                .filter_map(|(hp, _)| top.contains(&hp).then_some(hp))
                .collect();
            direct_v.sort();
            once_v.sort();
            (direct_v.into_boxed_slice(), once_v.into_boxed_slice())
        })
        .unzip();

    parc.0.add_iter_owned::<VarAttBuilder, _, _>(
        direct_out.into_iter(),
        Some("author-citing-hits-direct"),
    );
    parc.0.add_iter_owned::<VarAttBuilder, _, _>(
        once_out.into_iter(),
        Some("author-citing-hits-once"),
    );

    let hp_ccs = parc
        .0
        .get_entity_interface::<HitPapersCiteCounts, QuickestBox>();
    let hit_coords: Vec<[f64; 2]> = hp_ccs
        .iter()
        .map(|&cc| {
            let cf = f64::max(cc as f64, COORD_MIN_CITES);
            [cf.ln(), cf / COORD_MIN_PAPERS]
        })
        .collect();
    let hit_filter: Vec<u8> = vec![1u8; hp_ccs.len()];
    parc.0
        .ditf::<CoordinateMarker, HitPapers, _>(hit_coords, "coordinates");
    parc.0
        .ditf::<PageFilterMarker, HitPapers, _>(hit_filter, "page-filter");

    parc.0.write_code()?;
    Ok(())
}
