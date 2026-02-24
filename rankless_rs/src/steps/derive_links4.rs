use hashbrown::HashSet;
use std::{io, sync::Arc};
use tqdm::Iter;

use dmove::{
    para_multi_gen_run, BigId, Entity, LoadedIdMap, MarkedAttribute, NamespacedEntity,
    UnsignedNumber, VarAttBuilder, VariableSizeAttribute, ET, MAA,
};

use crate::{
    common::{EmptyAttributeEntity, HitWorkMarker, MainWorkMarker},
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::WorkReferences,
        derive_links1::WorkFilteredAuthors,
        derive_links2::WorkCitingCounts,
        derive_links3::{
            HitPapers, HitPapersCiteCounts, HitPapersDois, HitPapersNames, HitPapersWids,
        },
    },
    steps::derive_links3::work_count,
    CiteCountMarker, NameExtensionMarker, NameMarker, QuickestBox, QuickestNumbered, QuickestVBox,
    ReadIter, SemanticIdMarker, Stowage,
};

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
    work_count::<Countries>(&stowage);
    let hit_map = stowage.get_entity_interface::<HitPapers, QuickestNumbered>(); //TODO: this can
                                                                                 //try and fail with QuickMap
    let wcc = stowage.get_entity_interface::<WorkCitingCounts, QuickestBox>();
    let wor_refs = stowage.get_entity_interface::<WorkReferences, QuickestVBox>();
    let w2a = stowage.get_entity_interface::<WorkFilteredAuthors, QuickestVBox>();

    let parc = Arc::new((stowage, hit_map, wcc));
    para_multi_gen_run!(sorted_hit_papers, Institutions, Authors, Countries, Sources, Subfields, Topics; parc).last();

    let mut direct: Vec<HashSet<ET<HitPapers>>> = vec![HashSet::new(); Authors::N];
    let mut once_removed: Vec<HashSet<ET<HitPapers>>> = vec![HashSet::new(); Authors::N];

    for (&hp_wid_big, &hp_id) in parc.1 .0.iter().tqdm().desc(Some("hit papers for authors")) {
        let hp_wid = hp_wid_big.to_usize();
        let hp_authors: HashSet<ET<Authors>> = w2a.0[hp_wid].iter().copied().collect();

        for &ref_wid in wor_refs.0[hp_wid].iter() {
            let ru = ref_wid.to_usize();
            let ref_authors = &w2a.0[ru];
            for &aid in ref_authors.iter() {
                if !hp_authors.contains(&aid) {
                    direct[aid.to_usize()].insert(hp_id);
                }
            }
            for &ref2_wid in wor_refs.0[ru].iter() {
                let r2u = ref2_wid.to_usize();
                let ref2_authors = &w2a.0[r2u];
                for &aid in ref2_authors.iter() {
                    if !hp_authors.contains(&aid)
                        && !ref_authors.contains(&aid)
                        && !direct[aid.to_usize()].contains(&hp_id)
                    {
                        once_removed[aid.to_usize()].insert(hp_id);
                    }
                }
            }
        }
    }

    let to_sorted = |sets: Vec<HashSet<ET<HitPapers>>>| {
        sets.into_iter().map(|s| {
            let mut v: Vec<ET<HitPapers>> = s.into_iter().collect();
            v.sort();
            v.into_boxed_slice()
        })
    };

    let n_direct: usize = direct.iter().map(|s| s.len()).sum();
    let n_once: usize = once_removed.iter().map(|s| s.len()).sum();
    println!("direct: {n_direct} total entries, once_removed: {n_once} total entries");
    parc.0.add_iter_owned::<VarAttBuilder, _, _>(
        to_sorted(direct),
        Some("author-citing-hits-direct"),
    );
    parc.0.add_iter_owned::<VarAttBuilder, _, _>(
        to_sorted(once_removed),
        Some("author-citing-hits-once"),
    );
    parc.0.write_code()?;
    Ok(())
}
