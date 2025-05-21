use std::{collections::BinaryHeap, sync::Arc};

use crate::{
    agg_tree::HeapIterator,
    common::{init_empty_slice, MainWorkMarker},
    env_consts::FINAL_YEAR,
    gen::{
        a1_entity_mapping::{Authors, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{WorkDois, WorkTopics, WorkYears, WorksNames},
        derive_links1::WorkSubfields,
        derive_links2::WorkCountries,
    },
    steps::{
        a1_entity_mapping::{YearInterface, Years},
        derive_links1::invert_read_multi_link_to_work,
    },
    CiteCountMarker, QuickestBox, QuickestVBox, ReadIter, Stowage, WorkCountMarker,
};
use dmove::{
    para_multi_gen_run, BigId, Data64MappedEntityBuilder, DowncastingBuilder, Entity,
    MarkedAttribute, NamespacedEntity, UnsignedNumber, VarAttBuilder, VariableSizeAttribute, ET,
    MAA,
};

const MIN_FOR_HIT: usize = 25;
const TOP_TOPIC: usize = 20;
const TOP_SUBFIELD: usize = 100;
const TOP_YEAR: usize = 50;
const TOP_ALL_TIME: usize = 40_000;

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

pub fn main(stowage: Stowage) -> std::io::Result<()> {
    let starc = Arc::new(stowage);
    para_multi_gen_run!(work_count, Sources, Institutions, Authors, Subfields, Topics; starc);
    invert_read_multi_link_to_work::<WorkCountries>(&starc, "country-works");
    let cc_interface = starc.get_entity_interface::<MAA<Works, CiteCountMarker>, QuickestBox>();

    let w_sfs = starc.get_entity_interface::<WorkSubfields, QuickestVBox>();
    let w_topics = starc.get_entity_interface::<WorkTopics, QuickestVBox>();
    let w_years = starc.get_entity_interface::<WorkYears, QuickestBox>();

    let sf_limits = get_limits::<Subfields, _, _, _>(
        TOP_SUBFIELD,
        w_sfs.0.iter().map(|e| e.iter().map(|se| *se)),
        &cc_interface,
    );

    let topic_limits = get_limits::<Topics, _, _, _>(
        TOP_TOPIC,
        w_topics.0.iter().map(|e| e.iter().map(|se| *se)),
        &cc_interface,
    );

    let year_limits = get_limits::<Years, _, _, _>(
        TOP_YEAR,
        w_years.iter().map(|e| vec![*e].into_iter()),
        &cc_interface,
    );

    let mut theap = BinaryHeap::new();
    cc_interface.iter().for_each(|e| theap.push(*e));
    let global_limit = topn(theap, TOP_ALL_TIME);

    let doi_interface = starc.get_entity_interface::<WorkDois, QuickestVBox>();
    let name_interface = starc.get_entity_interface::<WorksNames, ReadIter>();
    let mut hit_names = vec!["Unknown".to_string()]; //TODO: 0 id is unknown, but all this needing to map to
                                                     //u64 is unnecessary here
    let mut hit_dois = vec!["".to_string()];
    let this_year = YearInterface::parse(FINAL_YEAR);
    let hit_papers = name_interface.enumerate().filter_map(|(wid, name)| {
        if w_years[wid] >= this_year {
            return None;
        }
        let wcc = cc_interface[wid];
        if (wcc.to_usize() >= MIN_FOR_HIT)
            && (wcc >= global_limit
                || wcc >= year_limits[w_years[wid].to_usize()]
                || w_sfs.0[wid].iter().any(|e| sf_limits[e.to_usize()] <= wcc)
                || w_topics.0[wid]
                    .iter()
                    .any(|e| topic_limits[e.to_usize()] <= wcc))
        {
            hit_names.push(name);
            hit_dois.push(doi_interface.0[wid].to_string());
            Some(wid as BigId)
        } else {
            None
        }
    });
    starc.add_iter_owned::<Data64MappedEntityBuilder, _, _>(hit_papers, Some("hit-papers"));
    starc.add_iter_owned::<VarAttBuilder, _, _>(hit_names.into_iter(), Some("hit-papers-names"));
    starc.add_iter_owned::<VarAttBuilder, _, _>(hit_dois.into_iter(), Some("hit-papers-dois"));
    starc.write_code()?;
    Ok(())
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
