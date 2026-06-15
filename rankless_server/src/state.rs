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

use crate::consts::{MAX_HITS, SEARCH_SIZE};
use crate::responses::{PostAttRelatedEntity, RelationGroups, SearchResult, SerializableExt};
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
    pub hit_papers: Box<[ET<HitPapers>]>,
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

                let mut hit_papers = Vec::new();
                if E::NAME != HitPapers::NAME {
                    if let Some(hits) = entif.hit_works.0.get(i) {
                        hits.iter().take(MAX_HITS).for_each(|e| hit_papers.push(*e));
                    }
                }

                Self {
                    start_year: YearInterface::reverse(sy_ind as ET<Years>),
                    yearly_cites: entif.yearly_cites[i].clone(),
                    yearly_papers,
                    hit_papers: hit_papers.into(),
                }
            })
            .collect()
    }

    // Relations + co-author network are rebuilt on demand from the mmapped top-N tables rather than
    // held resident: each entity view reads only its own rows. `dm_id` is the raw entity dm id.
    pub fn to_serializable(
        &self,
        etype: &str,
        dm_id: usize,
        satts: &AttributeLabelUnion,
        nstates: &NameStateMap,
        gets: &Getters,
    ) -> SerializableExt {
        let (relations, author_network) = build_relations(etype, dm_id, satts, nstates, gets);
        SerializableExt {
            start_year: self.start_year,
            yearly_papers: self.yearly_papers,
            yearly_cites: self.yearly_cites,
            relations,
            author_network,
        }
    }
}

fn build_relations(
    etype: &str,
    dm_id: usize,
    satts: &AttributeLabelUnion,
    nstates: &NameStateMap,
    gets: &Getters,
) -> (RelationGroups, Box<[u8]>) {
    let Some(tr) = gets.top_rels_for(etype) else {
        return (RelationGroups::default(), Box::new([]));
    };
    // Hit papers don't surface affiliation-country or topic relations (empty placeholders, no mmap).
    let collab_nation = tr
        .aff_countries
        .as_ref()
        .map(|m| resolve_group(m.row(dm_id), Countries::NAME, satts, nstates, gets))
        .unwrap_or_default();
    let paper_topics = tr
        .paper_topic
        .as_ref()
        .map(|m| resolve_group(m.row(dm_id), Topics::NAME, satts, nstates, gets))
        .unwrap_or_default();
    let relations = RelationGroups {
        paper_fields: resolve_group(
            tr.paper_sfc.row(dm_id),
            Subfields::NAME,
            satts,
            nstates,
            gets,
        ),
        citing_fields: resolve_group(
            tr.citing_sfc.row(dm_id),
            Subfields::NAME,
            satts,
            nstates,
            gets,
        ),
        paper_journals: resolve_group(tr.journals.row(dm_id), Sources::NAME, satts, nstates, gets),
        paper_authors: resolve_group(tr.authors.row(dm_id), Authors::NAME, satts, nstates, gets),
        collab_nation,
        paper_topics,
    };
    let author_network = build_author_network(tr.authors.row(dm_id), gets);
    (relations, author_network)
}

// One top-N row → resolved related entities. dm id 0 is the empty/padding sentinel. Topics carry
// their parent field, resolved via `gets.tsuf`, so the hero can nest them.
fn resolve_group<ID, const N: usize>(
    row: [(u32, ID); N],
    target_etype: &'static str,
    satts: &AttributeLabelUnion,
    nstates: &NameStateMap,
    gets: &Getters,
) -> Vec<PostAttRelatedEntity>
where
    ID: UnsignedNumber,
{
    let is_topic = target_etype == Topics::NAME;
    row.into_iter()
        .filter_map(|(score, id)| {
            let dm = id.to_usize();
            if dm == 0 {
                return None;
            }
            let att = &satts[target_etype][dm];
            let semantic_id = nstates
                .get(target_etype)
                .and_then(|rs| rs.semantic_id_map.get(att.semantic_id.as_ref()))
                .map(|_| att.semantic_id.to_string())
                .unwrap_or_default();
            let (parent_name, parent_semantic_id) = if is_topic {
                let sf_dm = gets.tsuf(&dm).to_usize();
                if sf_dm != 0 {
                    let p = &satts[Subfields::NAME][sf_dm];
                    let sid = nstates
                        .get(Subfields::NAME)
                        .and_then(|rs| rs.semantic_id_map.get(p.semantic_id.as_ref()))
                        .map(|_| p.semantic_id.to_string());
                    (Some(p.name.to_string()), sid)
                } else {
                    (None, None)
                }
            } else {
                (None, None)
            };
            Some(PostAttRelatedEntity {
                name: att.name.to_string(),
                semantic_id,
                etype: target_etype.to_string(),
                score,
                parent_name,
                parent_semantic_id,
            })
        })
        .collect()
}

// Upper-triangular co-authorship counts among the entity's top paper-authors (same order as the
// `paper-authors` group), each looked up against the resident per-author `coathors` lists.
fn build_author_network<ID, const N: usize>(row: [(u32, ID); N], gets: &Getters) -> Box<[u8]>
where
    ID: UnsignedNumber,
{
    let ids: Vec<usize> = row
        .into_iter()
        .map(|(_, a)| a.to_usize())
        .filter(|&a| a != 0)
        .collect();
    let mut out: Vec<u8> = Vec::new();
    for si in 0..ids.len().saturating_sub(1) {
        let coll_nums = gets.coathors(ids[si]);
        for &taid in ids.iter().skip(si + 1) {
            let mut coll_num: u8 = 0;
            for (ctaid, n) in coll_nums {
                if ctaid.to_usize() == taid {
                    coll_num = *n;
                    break;
                }
            }
            out.push(coll_num);
        }
    }
    out.into()
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
