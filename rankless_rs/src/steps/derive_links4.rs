use std::{io, sync::Arc};

use dmove::{
    para_multi_gen_run, BigId, Entity, LoadedIdMap, MarkedAttribute, NamespacedEntity,
    UnsignedNumber, VarAttBuilder, VariableSizeAttribute, ET, MAA,
};

use crate::{
    common::{HitWorkMarker, MainWorkMarker},
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        derive_links2::WorkCitingCounts,
        derive_links3::HitPapers,
    },
    steps::derive_links3::work_count,
    QuickestBox, QuickestNumbered, ReadIter, Stowage,
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

pub fn main(stowage: Stowage) -> io::Result<()> {
    work_count::<Countries>(&stowage);
    let hit_map = stowage.get_entity_interface::<HitPapers, QuickestNumbered>(); //TODO: whis can
                                                                                 //try and fail with QuickMap
    let wcc = stowage.get_entity_interface::<WorkCitingCounts, QuickestBox>();
    let parc = Arc::new((stowage, hit_map, wcc));
    para_multi_gen_run!(sorted_hit_papers, Institutions, Authors, Countries, Sources, Subfields, Topics; parc).last();
    parc.0.write_code()?;
    Ok(())
}
