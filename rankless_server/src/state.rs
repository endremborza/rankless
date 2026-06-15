use std::sync::Arc;

use axum::extract::State;
use hashbrown::{HashMap, HashSet};
use muwo_search::SearchEngine;

use dmove::{Entity, UnsignedNumber, ET};
use rankless_rs::{
    common::EXT_SEP,
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics},
        derive_links3::HitPapers,
    },
    ladder::LADDER_LEN,
    steps::{
        a1_entity_mapping::{RawYear, YearInterface, Years},
        derive_links2::EraRec,
    },
    N_PEERS,
};
use rankless_trees::{
    extensions::DistinctionText,
    interfacing::{Getters, PeerAuxMap, RootInterfaceable, RootInterfaces},
    io::TreeRunManager,
    AttributeLabelUnion,
};

use crate::consts::{ETYPE_ENC, MAX_HITS, SEARCH_SIZE};
use crate::responses::{PostAttRelatedEntity, SearchResult, SerializableExt};
use crate::search_cache::{fnv64, save_engine, try_load_engine};

pub(crate) type InstTrm = TreeRunManager<(
    Institutions,
    Authors,
    Subfields,
    Countries,
    Sources,
    HitPapers,
)>;
pub(crate) type NameStateMap = HashMap<&'static str, NameState>;
pub(crate) type StatesT = State<(
    Arc<NameStateMap>,
    Arc<AttributeLabelUnion>,
    Arc<InstTrm>,
    Arc<PeerAuxMap>,
)>;

pub(crate) struct NameState {
    pub engine: SearchEngine<SEARCH_SIZE>,
    pub responses: Box<[SearchResult]>,
    pub exts: Box<[EntityExt]>,
    pub semantic_id_map: HashMap<Arc<str>, u32>,
    pub oa_id_map: HashMap<u64, u32>,
    dm_to_response_id: Box<[u32]>,
    pub peers: Box<[[u32; N_PEERS]]>,
    pub cit_rank_ladder: Box<[[u32; LADDER_LEN]]>,
}

pub(crate) struct EntityExt {
    pub start_year: RawYear,
    pub yearly_papers: EraRec,
    pub yearly_cites: EraRec,
    pub prime_relations: Box<[PreAttRelatedEntity]>,
    pub hit_papers: Box<[ET<HitPapers>]>,
    author_network: Box<[u8]>,
}

pub(crate) struct PreAttRelatedEntity {
    pub dm_id: u32,
    pub etype_id: u8,
    pub rel_type: u8,
    pub score: u32,
}

pub(crate) trait IsTop: RootInterfaceable + Sized {
    fn is_top(_sr: &SearchResult) -> bool {
        true
    }
}

impl IsTop for Countries {}
impl IsTop for Subfields {}

impl IsTop for HitPapers {
    fn is_top(_sr: &SearchResult) -> bool {
        false
    }
}

impl IsTop for Authors {
    fn is_top(sr: &SearchResult) -> bool {
        crate::consts::FIN_AUTHORS.contains(&sr.semantic_id.as_ref())
    }
}

impl IsTop for Institutions {
    fn is_top(sr: &SearchResult) -> bool {
        let min_citations: u32 = 8_000_000;
        crate::consts::FIN_UNIS.contains(&sr.semantic_id.as_ref()) || sr.citations > min_citations
    }
}

impl IsTop for Sources {
    fn is_top(sr: &SearchResult) -> bool {
        crate::consts::FIN_SOURCES.contains(&sr.semantic_id.as_ref())
    }
}

impl EntityExt {
    fn from_resps<E>(
        responses: &Box<[SearchResult]>,
        entif: &RootInterfaces<E>,
        gets: &Getters,
    ) -> Box<[Self]>
    where
        E: RootInterfaceable,
    {
        responses
            .iter()
            .map(|res| {
                let i = res.dm_id;

                let mut sy_ind = 0;
                let mut yearly_papers = EraRec::default();
                if let Some(ypi) = entif.yearly_papers.get(i) {
                    yearly_papers = ypi.clone();
                    for (yi, ycount) in ypi.into_iter().enumerate() {
                        if (sy_ind == 0) & (*ycount > 0) {
                            sy_ind = yi;
                            break;
                        }
                    }
                }
                if E::NAME == HitPapers::NAME {
                    //TODO: this shows the crazy indexing of gets
                    let wid = gets.hit_papers[i];
                    sy_ind = gets.year(&wid.to_usize()).to_usize();
                }

                let mut prime_relations = Vec::new();
                let mut hit_papers = Vec::new();
                let mut author_collabs = Vec::new();
                add_to_relations::<Subfields, _>(&entif.top_paper_sfc[i], &mut prime_relations, 0);
                add_to_relations::<Subfields, _>(&entif.top_citing_sfc[i], &mut prime_relations, 1);
                add_to_relations::<Sources, _>(&entif.top_journals[i], &mut prime_relations, 4);
                const TA_RTYPE: u8 = 5;
                add_to_relations::<Authors, _>(
                    &entif.top_authors[i],
                    &mut prime_relations,
                    TA_RTYPE,
                );
                let author_dm_ids: Vec<u32> = prime_relations
                    .iter()
                    .filter(|e| e.rel_type == TA_RTYPE)
                    .map(|e| e.dm_id)
                    .collect();
                author_dm_ids
                    .iter()
                    .take(author_dm_ids.len().saturating_sub(1))
                    .enumerate()
                    .for_each(|(si, said)| {
                        let coll_nums = gets.coathors(*said);
                        for ti in (si + 1)..author_dm_ids.len() {
                            let taid = author_dm_ids[ti];
                            let mut coll_num = 0;
                            for (ctaid, n) in coll_nums {
                                if ctaid.to_usize() == taid.to_usize() {
                                    coll_num = *n;
                                    break;
                                }
                            }
                            author_collabs.push(coll_num);
                        }
                    });
                if E::NAME != HitPapers::NAME {
                    add_to_relations::<Countries, _>(
                        &entif.top_aff_countries[i],
                        &mut prime_relations,
                        3,
                    );
                    add_to_relations::<Topics, _>(
                        &entif.top_paper_topic[i],
                        &mut prime_relations,
                        2,
                    );
                    if let Some(hits) = entif.hit_works.0.get(i) {
                        hits.iter().take(MAX_HITS).for_each(|e| hit_papers.push(*e));
                    }
                }

                Self {
                    start_year: YearInterface::reverse(sy_ind as ET<Years>),
                    yearly_cites: entif.yearly_cites[i].clone(),
                    yearly_papers,
                    prime_relations: prime_relations.into(),
                    hit_papers: hit_papers.into(),
                    author_network: author_collabs.into_boxed_slice(),
                }
            })
            .collect()
    }

    pub fn to_serializable(
        &self,
        satts: &AttributeLabelUnion,
        nstates: &NameStateMap,
    ) -> SerializableExt {
        let prime_relations = self
            .prime_relations
            .iter()
            .map(|sr| {
                let etype = ETYPE_ENC[sr.etype_id as usize];
                let att = &satts[etype][sr.dm_id.to_usize()];
                let semantic_id = nstates
                    .get(etype)
                    .and_then(|rstate| rstate.semantic_id_map.get(att.semantic_id.as_ref()))
                    .map(|_| att.semantic_id.to_string())
                    .unwrap_or_default();
                PostAttRelatedEntity {
                    semantic_id,
                    name: att.name.to_string(),
                    etype: etype.to_string(),
                    rel_type: sr.rel_type,
                    score: sr.score,
                }
            })
            .collect();
        SerializableExt {
            start_year: self.start_year,
            yearly_papers: self.yearly_papers,
            yearly_cites: self.yearly_cites,
            prime_relations,
            author_network: self.author_network.clone(),
        }
    }
}

impl NameState {
    pub fn new<E>(
        entif: &RootInterfaces<E>,
        gets: &Getters,
        names_arc: &[Arc<str>],
        sem_ids_arc: &[Arc<str>],
    ) -> Self
    where
        E: RootInterfaceable + IsTop + DistinctionText,
    {
        let (responses, engine_strs) = Self::get_resps(entif, gets, names_arc, sem_ids_arc);
        let cache_dir = gets.stowage.path_from_ns("search-cache");
        let stem = format!("{}-s{SEARCH_SIZE}", E::NAME);
        let bin_path = cache_dir.join(format!("{stem}.bin"));
        let stamp_path = cache_dir.join(format!("{stem}.stamp"));
        let key = fnv64(engine_strs.iter().map(|s| s.as_bytes()));
        let now = std::time::Instant::now();
        let (engine, from_cache) = match try_load_engine(&bin_path, &stamp_path, key) {
            Some(e) => (e, true),
            None => {
                let e = SearchEngine::new(engine_strs.into_iter());
                save_engine(&e, &bin_path, &stamp_path, &cache_dir, key);
                (e, false)
            }
        };
        println!(
            "search engine for {} (n={}) in {}s ({})",
            E::NAME,
            responses.len(),
            now.elapsed().as_secs(),
            if from_cache { "cached" } else { "built" }
        );
        let n = responses.len();
        let mut semantic_id_map = HashMap::with_capacity(n);
        let mut oa_id_map = HashMap::with_capacity(n);
        let mut dm_to_response_id: Box<[u32]> = vec![u32::MAX; names_arc.len()].into_boxed_slice();
        for (i, res) in responses.iter().enumerate() {
            let dm_id = res.dm_id;
            let oa_id = entif.oa_id[dm_id];
            oa_id_map.insert(oa_id, i as u32);
            semantic_id_map.insert(res.semantic_id.clone(), dm_id as u32);
            if dm_id < dm_to_response_id.len() {
                dm_to_response_id[dm_id] = i as u32;
            }
        }

        let peers: Box<[[u32; N_PEERS]]> = entif
            .peers
            .iter()
            .map(|arr| arr.map(|e| e.to_usize() as u32).try_into().unwrap())
            .collect();

        Self {
            engine: engine.into(),
            exts: EntityExt::from_resps(&responses, entif, gets),
            responses,
            semantic_id_map,
            oa_id_map,
            dm_to_response_id,
            peers,
            cit_rank_ladder: entif.cit_rank_ladder.clone(),
        }
    }

    fn get_resps<E>(
        entif: &RootInterfaces<E>,
        gets: &Getters,
        names_arc: &[Arc<str>],
        sem_ids_arc: &[Arc<str>],
    ) -> (Box<[SearchResult]>, Vec<String>)
    where
        E: RootInterfaceable + IsTop + DistinctionText,
    {
        let dist_txt = <E as DistinctionText>::get_distinction_text_arr(entif, gets);
        let ext_txt = &entif.name_exts.0;
        let mut pairs: Vec<(SearchResult, String)> = names_arc
            .iter()
            .zip(sem_ids_arc.iter())
            .zip(dist_txt.to_vec().into_iter())
            .enumerate()
            .filter(|(i, _)| !sem_ids_arc[*i].is_empty())
            .map(|(i, ((name, semantic_id), dist_txt))| {
                let ext = ext_txt.get(i).map(|s| s.as_str()).unwrap_or("");
                let full_name = dedup_search_text(name, ext);
                let sr = SearchResult::new(i, name.clone(), semantic_id.clone(), dist_txt, entif);
                (sr, full_name)
            })
            .collect();
        pairs.sort_by_key(|e| u32::MAX - e.0.citations);
        let (responses, engine_strs): (Vec<SearchResult>, Vec<String>) = pairs.into_iter().unzip();
        (responses.into_boxed_slice(), engine_strs)
    }

    pub fn response_id_from_dm(&self, dm_id: usize) -> Option<usize> {
        let rid = *self.dm_to_response_id.get(dm_id)?;
        if rid == u32::MAX {
            None
        } else {
            Some(rid as usize)
        }
    }
}

fn dedup_search_text(name: &str, ext: &str) -> String {
    let ext_spaced = ext.replace(EXT_SEP, " ");
    let mut seen = HashSet::new();
    name.split_whitespace()
        .chain(ext_spaced.split_whitespace())
        .filter(|w| seen.insert(w.to_lowercase()))
        .collect::<Vec<_>>()
        .join(" ")
}

fn add_to_relations<RE, T>(arr: &[(u32, T)], prels: &mut Vec<PreAttRelatedEntity>, rel_type: u8)
where
    RE: Entity,
    T: UnsignedNumber,
{
    let etype_id = ETYPE_ENC.iter().position(|name| *name == RE::NAME).unwrap() as u8;
    arr.iter().for_each(|e| {
        let dm_id = e.1.to_usize() as u32;
        if dm_id != 0 {
            prels.push(PreAttRelatedEntity {
                rel_type,
                dm_id,
                etype_id,
                score: e.0,
            })
        }
    });
}
