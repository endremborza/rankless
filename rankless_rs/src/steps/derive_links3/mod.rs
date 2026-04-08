use std::{ops::AddAssign, sync::Arc};

use dmove::{
    BigId, Data64MappedEntityBuilder, DowncastingBuilder, Entity, MarkedAttribute,
    NamespacedEntity, UnsignedNumber, VarAttBuilder, VariableSizeAttribute, ET, MAA,
};
use hashbrown::HashMap;

use crate::{
    common::{reverse_id, MainWorkMarker, YearlyPapersMarker},
    env_consts::FINAL_YEAR,
    filter::FIX_AUTHORS,
    gen::{
        a1_entity_mapping::{Authors, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{WorkDois, WorkTopics, WorkYears, WorksNames},
        derive_links1::WorkSubfields,
        derive_links2::{AuthorWorks, SourceStats},
    },
    peers,
    steps::a1_entity_mapping::YearInterface,
    CiteCountMarker, QuickestBox, QuickestVBox, ReadIter, Stowage, WorkCountMarker,
};

mod entity_sem_ids;
mod hit_papers;
mod peer_ctx;

pub use hit_papers::get_nobeled_works;
pub use peer_ctx::AuthorPeerCtx;

pub const AUTHOR_BLACKLIST: [u64; 3] = [
    5030786976, //Lynnette Nathalie Lyzwinski
    5036138197, //David S. Gokhin
    5034807195, //Shadi Yarandi
];

pub(super) fn dec_work_count<E: Entity, I: Iterator<Item = usize>>(stowage: &Stowage, it: I) {
    stowage.declare_iter::<DowncastingBuilder, _, _, E, WorkCountMarker>(
        it,
        &format!("{}-work-count", E::NAME),
    )
}

pub fn main(stowage: Stowage) -> std::io::Result<()> {
    let starc = Arc::new(stowage);
    work_count::<Topics>(&starc);

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

    let topic_limits = hit_papers::get_limits::<Topics, _, _, _>(
        hit_papers::TOP_TOPIC,
        w_topics.0.iter().map(|e| e.iter().map(|se| *se)),
        &cc_interface,
    );

    let (year_bms, sf_bms) = std::thread::scope(|s| {
        let h1 = s.spawn(|| hit_papers::compute_year_bms(&w_years, &cc_interface));
        let h2 = s.spawn(|| hit_papers::compute_sf_bms(&w_sfs.0, &cc_interface));
        (h1.join().unwrap(), h2.join().unwrap())
    });
    let sf_year_bms = hit_papers::compute_sf_year_bms(&w_sfs.0, &w_years, &cc_interface, &year_bms);

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
            hit_papers::NOBEL_MULTIPLIER
        } else {
            1.0
        };
        let bm = hit_papers::paper_bm(&w_sfs.0[wid], year, &sf_year_bms, &sf_bms, &year_bms);
        let score = if bm > 0.0 {
            cc_n as f64 / bm * multiplier
        } else {
            0.0
        };

        let qualifies = (cc_n >= hit_papers::MIN_NEEDED)
            & (cc_n >= hit_papers::MIN_UNIVERSAL
                || reaches_any_topic_limit
                || score >= hit_papers::SCORE_THRESHOLD);

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

    let w2amap = starc
        .get_entity_interface::<crate::gen::derive_links1::WorkFilteredAuthors, QuickestVBox>();
    let coauthorships: Vec<Box<[(ET<Authors>, u8)]>> = starc
        .get_entity_interface::<AuthorWorks, ReadIter>()
        .enumerate()
        .map(|(aid, aworks)| {
            let mut coauthor_map = HashMap::<ET<Authors>, u8>::new();
            IntoIterator::into_iter(aworks).for_each(|wid| {
                w2amap.0[wid.to_usize()].iter().for_each(|c_aid| {
                    if c_aid.to_usize() != aid {
                        let entry = coauthor_map.entry(*c_aid).or_insert(0);
                        if *entry <= 250 {
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

    // --- Page filters, work counts, and semantic IDs ---

    let source_stats = starc.get_entity_interface::<SourceStats, QuickestBox>();
    let (inst_filter, inst_wcounts) = entity_sem_ids::page_filter::<Institutions, _, _>(
        &starc,
        |_, _, _| true,
        entity_sem_ids::institution_sem_names,
    );
    let (sf_filter, sf_wcounts) = entity_sem_ids::page_filter::<Subfields, _, _>(
        &starc,
        |_, _, _| true,
        entity_sem_ids::basic_sem_names,
    );
    let (source_filter, source_wcounts) = entity_sem_ids::page_filter::<Sources, _, _>(
        &starc,
        |i, c, p| p > 10 && c > 20 && source_stats[i].1 <= 2,
        entity_sem_ids::source_sem_names,
    );

    let author_oa_ids = reverse_id::<Authors>(&starc);
    let author_yearly_papers =
        starc.get_marked_interface::<Authors, YearlyPapersMarker, QuickestBox>();
    let (author_filter, author_wcounts) = entity_sem_ids::page_filter::<Authors, _, _>(
        &starc,
        |i, _c, p| {
            FIX_AUTHORS.contains(&author_oa_ids[i])
                || (p < 10_000
                    && *author_yearly_papers[i].iter().max().unwrap_or(&0) < 300
                    && !AUTHOR_BLACKLIST.contains(&author_oa_ids[i]))
        },
        entity_sem_ids::basic_sem_names,
    );
    let (country_filter, country_wcounts) = entity_sem_ids::country_page_filter(&starc);

    // Peers

    let inst_ctx = peer_ctx::InstPeerCtx::new(&starc, inst_filter, &inst_wcounts);
    peers::compute_peers::<_, 10, _, _>(&*starc, &inst_ctx, &inst_ctx.filter, &inst_wcounts);

    let sf_ctx = peer_ctx::SfPeerCtx::new(&starc, sf_filter, &sf_wcounts);
    peers::compute_peers::<_, 10, _, _>(&*starc, &sf_ctx, &sf_ctx.filter, &sf_wcounts);

    let country_ctx = peer_ctx::CountryPeerCtx::new(&starc, country_filter, &country_wcounts);
    peers::compute_peers::<_, 10, _, _>(
        &*starc,
        &country_ctx,
        &country_ctx.filter,
        &country_wcounts,
    );

    let source_ctx = peer_ctx::SourcePeerCtx::new(&starc, source_filter, &source_wcounts);
    peers::compute_peers::<_, 10, _, _>(&*starc, &source_ctx, &source_ctx.filter, &source_wcounts);

    println!("computing author peers");
    let author_ctx = AuthorPeerCtx::new(&starc, author_filter, &author_wcounts);
    peers::compute_peers::<_, 10, _, _>(&*starc, &author_ctx, &author_ctx.filter, &author_wcounts);

    starc.write_code()?;
    Ok(())
}

fn work_count<E>(stowage: &Stowage)
where
    E: MarkedAttribute<MainWorkMarker>,
    MAA<E, MainWorkMarker>: Entity<T = Box<[ET<Works>]>> + NamespacedEntity + VariableSizeAttribute,
{
    dec_work_count::<E, _>(
        stowage,
        stowage
            .get_entity_interface::<MAA<E, MainWorkMarker>, ReadIter>()
            .map(|e| e.len()),
    );
}
