#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;

mod consts;

use axum::{
    body::Body,
    extract::{Path, Query, State},
    http::{header::CACHE_CONTROL, HeaderMap, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use dmove::{
    para::{set_and_notify, wait_for_data_copy, AcTuple},
    para_multi_gen_run, reverse_prefixed_n, ByteArrayInterface, Entity, EntityMutableMapperBackend,
    MmapSlice, NamespacedEntity, UnsignedNumber, VattReadingArcMap, ET,
};
use hashbrown::{HashMap, HashSet};
use rand::seq::SliceRandom;
use serde::{Deserialize, Serialize};
use socket2::{Domain, Socket, Type};
use std::{
    cmp::{max, min},
    fs,
    net::SocketAddr,
    path::PathBuf,
    sync::{Arc, Mutex},
    thread::sleep,
    time,
};
use tokio::{net::TcpListener, sync::Notify};

use muwo_search::SearchEngine;
use rankless_rs::{
    common::{
        CitSubfieldsArrayMarker, HIndexMarker, MainEntity, MmapBox, QuickestBox,
        YearCentroidMarker, EXT_SEP,
    },
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{AuthorOrcids, DiscardedAuthorsNames, WorkBiblios, WorkDois},
        derive_links3::HitPapers,
    },
    ladder::{LADDER_LEN, LADDER_PCT_BANDS},
    steps::{
        a1_entity_mapping::{Qs, RawYear, YearInterface, Years},
        a2_init_atts::OrcidType,
        derive_links2::EraRec,
    },
    Stowage, N_PEERS,
};
use rankless_trees::{
    extensions::DistinctionText,
    interfacing::{
        make_stats_entry_arc, Getters, NodeInterfaceable, NodeInterfaces, RootInterfaceable,
        RootInterfaces,
    },
    io::{
        EntityAttsForLinks, ManFileHandle, ShallowQ, ShallowTreesResponse, TreeQ, TreeResponse,
        TreeRunManager, WT,
    },
    path_finder::{extend_with_once_removed, get_direct_links, RefDAG},
    AttributeLabelUnion,
};

const MAX_HITS: usize = 80;
const PORT: u16 = 3038;
const SEARCH_SIZE: usize = 20;
const MAX_SLICE: usize = 40_000;
const CACHEABLE_FROM: u32 = 10_000;
const DEFAULT_N_THREADS: usize = 16;
const ETYPE_ENC: [&str; 7] = [
    Institutions::NAME,
    Authors::NAME,
    Subfields::NAME,
    Countries::NAME,
    Sources::NAME,
    Topics::NAME,
    HitPapers::NAME,
];

type InstTrm = TreeRunManager<(
    Institutions,
    Authors,
    Subfields,
    Countries,
    Sources,
    HitPapers,
)>;
type NameStateMap = HashMap<&'static str, NameState>;
type StatesT = State<(
    Arc<NameStateMap>,
    Arc<AttributeLabelUnion>,
    Arc<InstTrm>,
    Arc<PeerAuxMap>,
)>;
type StateKv = (&'static str, (NameState, TopResult, EntityDescription));
type PeerAuxMap = HashMap<&'static str, PeerAux>;

const N_SUBFIELDS: usize = Subfields::N;

struct PeerAux {
    cit_subfields: MmapSlice<[u32; N_SUBFIELDS]>,
    h_indices: Option<Box<[u32]>>,
    year_centroids: Option<Box<[f32]>>,
}

#[derive(Serialize)]
struct PeerSubfieldInfo {
    name: Arc<str>,
    #[serde(rename = "semanticId")]
    semantic_id: Arc<str>,
    #[serde(rename = "dmId")]
    dm_id: usize,
}

#[derive(Serialize)]
struct PeerEntry {
    //TODO - this should just be another view
    name: Arc<str>,
    #[serde(rename = "semanticId")]
    semantic_id: Arc<str>,
    papers: u32,
    citations: u32,
    #[serde(rename = "subfieldCitations")]
    subfield_citations: Vec<u32>,
    #[serde(rename = "yearlyPapers")]
    yearly_papers: EraRec,
    #[serde(rename = "yearlyCites")]
    yearly_cites: EraRec,
    #[serde(rename = "startYear")]
    start_year: RawYear,
    #[serde(rename = "hIndex", skip_serializing_if = "Option::is_none")]
    h_index: Option<u32>,
    #[serde(rename = "yearCentroid", skip_serializing_if = "Option::is_none")]
    year_centroid: Option<f32>,
    country: Option<Arc<str>>,
}

#[derive(Serialize)]
struct EntityPeersResp {
    #[serde(rename = "topSubfields")]
    top_subfields: Vec<PeerSubfieldInfo>,
    peers: Vec<PeerEntry>,
    hero: PeerEntry,
}

// Per-cohort-entity-type rank-breakpoint table the client caches once per root type and uses to tag
// any citation count with its subfield standing (the standing is computed on the frontend).
#[derive(Serialize)]
struct LadderResp {
    #[serde(rename = "pctBands")]
    pct_bands: &'static [f64],
    // One row per subfield dm_id; each cell is the citation threshold for that percentile band, or
    // null when the cohort is too small for it.
    ladder: Vec<Vec<Option<u32>>>,
}

#[derive(Deserialize)]
struct BasicQ {
    q: Option<String>,
}

#[derive(Deserialize)]
struct WorksQ {
    n: Option<usize>,
}

#[derive(Deserialize)]
struct ResolveWorkQ {
    wid: Option<usize>,
    oa_id: Option<u64>,
    doi: Option<String>,
}

#[derive(Deserialize)]
struct ResolveAuthorQ {
    semantic_id: Option<String>,
    orcid: Option<String>,
    oa_id: Option<u64>,
    dm_id: Option<usize>,
}

#[derive(Serialize)]
struct ResolveWorkResp {
    #[serde(rename = "oaId")]
    oa_id: u64,
    wid: usize,
    doi: String,
    year: u16,
    name: String,
}

#[derive(Serialize)]
struct ResolveAuthorResp {
    #[serde(rename = "oaId")]
    oa_id: u64,
    #[serde(rename = "dmId")]
    dm_id: usize,
    #[serde(rename = "semanticId")]
    semantic_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    orcid: Option<String>,
    name: String,
}

#[derive(Serialize)]
struct ViewResult {
    #[serde(flatten)]
    sr: SearchResult,
    #[serde(flatten)]
    ext: SerializableExt,
    #[serde(skip_serializing_if = "Option::is_none")]
    meta: Option<HashMap<&'static str, String>>,
    similars: Vec<SearchResult>,
}

#[derive(Serialize, Clone)]
struct PostAttRelatedEntity {
    name: String,
    #[serde(rename = "semanticId")]
    semantic_id: String,
    etype: String,
    #[serde(rename = "relType")]
    rel_type: u8,
    score: u32,
}

struct PreAttRelatedEntity {
    dm_id: u32,
    etype_id: u8,
    rel_type: u8,
    score: u32,
}

#[derive(Serialize)]
struct TopResult {
    name: String,
    entities: Vec<SearchResult>,
}

#[derive(Serialize)]
struct EntityDescription {
    name: String,
    count: usize,
}

#[derive(Serialize)]
struct CountsResponse {
    entities: Vec<EntityDescription>,
    total_citations: u64,
    total_works: usize,
}

fn fnv64(iter: impl Iterator<Item = impl AsRef<[u8]>>) -> u64 {
    const BASIS: u64 = 0xcbf29ce484222325;
    const PRIME: u64 = 0x00000100000001b3;
    let mut h = BASIS;
    for chunk in iter {
        for &b in chunk.as_ref() {
            h ^= b as u64;
            h = h.wrapping_mul(PRIME);
        }
    }
    h
}

fn try_load_engine<const S: usize>(
    bin_path: &PathBuf,
    stamp_path: &PathBuf,
    key: u64,
) -> Option<SearchEngine<S>> {
    let raw = fs::read(stamp_path).ok()?;
    let stamp_key = u64::from_ne_bytes(raw.try_into().ok()?);
    if stamp_key != key {
        let _ = fs::remove_file(bin_path);
        let _ = fs::remove_file(stamp_path);
        return None;
    }
    let mut file = fs::File::open(bin_path).ok()?;
    SearchEngine::try_load(&mut file)
}

fn save_engine<const S: usize>(
    engine: &SearchEngine<S>,
    bin_path: &PathBuf,
    stamp_path: &PathBuf,
    cache_dir: &PathBuf,
    key: u64,
) {
    if let Err(e) = fs::create_dir_all(cache_dir) {
        println!("search cache: could not create dir: {e}");
        return;
    }
    let result = (|| -> std::io::Result<()> {
        engine.save(&mut fs::File::create(bin_path)?)?;
        fs::write(stamp_path, key.to_ne_bytes())
    })();
    if let Err(e) = result {
        println!("search cache: write failed: {e}");
        let _ = fs::remove_file(bin_path);
        let _ = fs::remove_file(stamp_path);
    }
}

struct NameState {
    engine: SearchEngine<SEARCH_SIZE>,
    responses: Box<[SearchResult]>,
    exts: Box<[EntityExt]>,
    pub semantic_id_map: HashMap<Arc<str>, u32>,
    pub oa_id_map: HashMap<u64, u32>,
    dm_to_response_id: Box<[u32]>,
    peers: Box<[[u32; N_PEERS]]>,
    cit_rank_ladder: Box<[[u32; LADDER_LEN]]>,
}

#[derive(Serialize, Clone)]
struct PaperAuthorship {
    author: String, //prefixed with filtered/discarded
    insts: Vec<usize>,
}

#[derive(Serialize)]
struct PaperOut {
    wid: usize,
    #[serde(rename = "oaId")]
    oa_id: u64,
    year: u16,
    name: String,
    doi: String,
    citations: u32,
    source: usize,
    authorships: Vec<PaperAuthorship>,
    #[serde(rename = "yearlyCites", skip_serializing_if = "Option::is_none")]
    yearly_cites: Option<Box<[u32]>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    biblio: Option<ET<WorkBiblios>>,
    #[serde(rename = "isHit")]
    is_hit: bool,
    #[serde(rename = "hitBm", skip_serializing_if = "Option::is_none")]
    hit_bm: Option<u32>,
    #[serde(rename = "hitSemId", skip_serializing_if = "Option::is_none")]
    hit_sem_id: Option<String>,
    #[serde(rename = "createdTopic", skip_serializing_if = "Option::is_none")]
    created_topic: Option<String>,
}

#[derive(Serialize)]
struct PaperProfileResp {
    dag: RefDAG,
    papers: PaperSetResp,
}

#[derive(Serialize, Clone)]
struct SearchResult {
    name: Arc<str>,
    #[serde(rename = "semanticId")]
    semantic_id: Arc<str>,
    #[serde(rename = "oaId")]
    oa_id: u64,
    #[serde(rename = "dmId")]
    dm_id: usize,
    #[serde(rename = "distinctText", skip_serializing_if = "Option::is_none")]
    distinct_text: Option<String>,
    papers: u32,
    citations: u32,
}

#[derive(Serialize)]
struct UnionSearchResult {
    #[serde(flatten)]
    sr: SearchResult,
    #[serde(rename = "rootType")]
    root_type: &'static str,
}

#[derive(Serialize, Clone)]
struct SerializableExt {
    #[serde(rename = "startYear")]
    start_year: RawYear,
    #[serde(rename = "yearlyPapers")]
    yearly_papers: EraRec,
    #[serde(rename = "yearlyCites")]
    yearly_cites: EraRec,
    #[serde(rename = "primeRelations")]
    prime_relations: Vec<PostAttRelatedEntity>,
    #[serde(rename = "authorNetwork")]
    author_network: Box<[u8]>,
}

#[derive(Serialize)]
struct PaperSetResp {
    papers: Vec<PaperOut>,
    #[serde(rename = "entityAtts")]
    entity_atts: EntityAttsForLinks,
    #[serde(rename = "discAuthorNames")]
    disc_author_names: HashMap<String, String>,
    #[serde(rename = "authorsMeta")]
    authors_meta: HashMap<usize, PaperAuthorMeta>, //only filtered authors
}

#[derive(Serialize)]
struct PaperAuthorMeta {
    prize: u8,
    year: u16,
}

#[derive(Serialize)]
struct PaginatedPaperSetResp {
    resp: PaperSetResp,
    #[serde(rename = "totalPapers")]
    total_papers: usize,
    #[serde(rename = "sliceStart")]
    slice_start: usize,
}

struct EntityExt {
    start_year: RawYear,
    yearly_papers: EraRec,
    yearly_cites: EraRec,
    prime_relations: Box<[PreAttRelatedEntity]>,
    hit_papers: Box<[ET<HitPapers>]>,
    author_network: Box<[u8]>,
}

trait IsTop: RootInterfaceable + Sized {
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
        consts::FIN_AUTHORS.contains(&sr.semantic_id.as_ref())
    }
}

impl IsTop for Institutions {
    fn is_top(sr: &SearchResult) -> bool {
        const FIN_UNIS: [&str; 2] = ["budapesti-corvinus-egyetem", "tse"];
        let min_citations: u32 = 8_000_000;
        FIN_UNIS.contains(&sr.semantic_id.as_ref()) || sr.citations > min_citations
    }
}

impl IsTop for Sources {
    fn is_top(sr: &SearchResult) -> bool {
        consts::FIN_SOURCES.contains(&sr.semantic_id.as_ref())
    }
}

impl SearchResult {
    fn new<E>(
        i: usize,
        name: Arc<str>,
        semantic_id: Arc<str>,
        distinct_text: Option<String>,
        entif: &RootInterfaces<E>,
    ) -> Self
    where
        E: RootInterfaceable,
    {
        let papers = if entif.wcounts.len() > i {
            entif.wcounts[i].to_usize()
        } else {
            1
        } as u32;
        Self {
            name,
            semantic_id,
            distinct_text,
            papers,
            citations: entif.ccounts[i].to_usize() as u32,
            oa_id: entif.oa_id[i],
            dm_id: i,
        }
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
                    .take(author_dm_ids.len() - 1)
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

    fn to_serializable(
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

fn dedup_search_text(name: &str, ext: &str) -> String {
    let ext_spaced = ext.replace(EXT_SEP, " ");
    let mut seen = HashSet::new();
    name.split_whitespace()
        .chain(ext_spaced.split_whitespace())
        .filter(|w| seen.insert(w.to_lowercase()))
        .collect::<Vec<_>>()
        .join(" ")
}

impl NameState {
    fn new<E>(
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

    fn response_id_from_dm(&self, dm_id: usize) -> Option<usize> {
        let rid = *self.dm_to_response_id.get(dm_id)?;
        if rid == u32::MAX {
            None
        } else {
            Some(rid as usize)
        }
    }
}

impl EntityDescription {
    fn new<E: Entity>(count: usize) -> Self {
        Self {
            name: <E as Entity>::NAME.to_string(),
            count,
        }
    }
}

fn get_rest(
    stowage: Stowage,
    n_threads: usize,
) -> (
    NameStateMap,
    Arc<AttributeLabelUnion>,
    Arc<InstTrm>,
    CountsResponse,
    Vec<TopResult>,
    Arc<PeerAuxMap>,
) {
    let gets = Arc::new(Getters::new(Arc::new(stowage)));
    let mux_satts: Arc<Mutex<AttributeLabelUnion>> = Arc::new(Mutex::new(HashMap::new()));
    let cv_pair = AcTuple::<Option<f64>>::default();
    let mut ns_map: NameStateMap = HashMap::new();
    let mut tops = Vec::new();
    let peer_aux = {
        let stow = &gets.stowage;
        let mut m: PeerAuxMap = HashMap::new();
        m.insert(
            Authors::NAME,
            PeerAux {
                cit_subfields: stow
                    .get_marked_interface::<Authors, CitSubfieldsArrayMarker, MmapBox>(),
                h_indices: Some(stow.get_marked_interface::<Authors, HIndexMarker, QuickestBox>()),
                year_centroids: Some(
                    stow.get_marked_interface::<Authors, YearCentroidMarker, QuickestBox>(),
                ),
            },
        );
        m.insert(
            Institutions::NAME,
            PeerAux {
                cit_subfields: stow
                    .get_marked_interface::<Institutions, CitSubfieldsArrayMarker, MmapBox>(),
                h_indices: None,
                year_centroids: None,
            },
        );
        m.insert(
            Countries::NAME,
            PeerAux {
                cit_subfields: stow
                    .get_marked_interface::<Countries, CitSubfieldsArrayMarker, MmapBox>(),
                h_indices: None,
                year_centroids: None,
            },
        );
        m.insert(
            Sources::NAME,
            PeerAux {
                cit_subfields: stow
                    .get_marked_interface::<Sources, CitSubfieldsArrayMarker, MmapBox>(),
                h_indices: None,
                year_centroids: None,
            },
        );
        print_mem_use("loaded peer aux");
        Arc::new(m)
    };
    let counts_response = {
        let mut descriptions = Vec::new();
        print_mem_use("pre thread starts");
        let arg_tup = (gets.clone(), mux_satts.clone(), cv_pair.clone());
        let ei_ns_kvs = para_multi_gen_run!(get_state_tr_ed_kv, Institutions, Authors, Subfields, Countries, Sources, HitPapers; arg_tup);
        let ccount = gets.total_cite_count();
        set_and_notify(cv_pair, Some(ccount));
        let arg_tup_n = (gets.clone(), mux_satts.clone(), ccount.clone());
        para_multi_gen_run!(update_w_node_if, Topics, Qs; arg_tup_n).last();
        for (name, (nstate, tr, ed)) in ei_ns_kvs {
            tops.push(tr);
            descriptions.push(ed);
            ns_map.insert(name, nstate);
        }
        CountsResponse {
            entities: descriptions,
            total_citations: ccount as u64,
            total_works: Works::N,
        }
    };
    print_mem_use("after ei ns map");
    let satts = Arc::into_inner(mux_satts).unwrap().into_inner().unwrap();
    let asatts = Arc::new(satts);
    let tm: Arc<InstTrm> = TreeRunManager::new(gets, asatts.clone(), n_threads);
    print_mem_use("got tm");
    (ns_map, asatts, tm, counts_response, tops, peer_aux)
}

fn print_mem_use(suff: &str) {
    if let Ok(status) = std::fs::read_to_string("/proc/self/status") {
        for line in status.lines() {
            if line.starts_with("VmRSS:") {
                println!("Memory usage at {suff}: {line}");
                break;
            }
        }
    }
}

fn update_w_node_if<T>(
    (gets, mux_satts, ccount): &(Arc<Getters>, Arc<Mutex<AttributeLabelUnion>>, f64),
) where
    T: NodeInterfaceable,
{
    let (k, v) = NodeInterfaces::<T>::new(&gets.stowage).into_stats_entry(*ccount);
    mux_satts.lock().unwrap().insert(k, v);
}

fn get_state_tr_ed_kv<E>(
    full_tup: &(
        Arc<Getters>,
        Arc<Mutex<AttributeLabelUnion>>,
        AcTuple<Option<f64>>,
    ),
) -> StateKv
where
    E: RootInterfaceable + IsTop + MainEntity + NamespacedEntity + DistinctionText,
{
    let (gets_clone, au_clone, shared_cvp) = full_tup.clone();
    let name = E::NAME.to_string();
    let ent_intf = RootInterfaces::<E>::new(&gets_clone.stowage);
    let names_arc: Box<[Arc<str>]> = (&ent_intf.names).into();
    let sem_ids_arc: Box<[Arc<str>]> = (&ent_intf.sem_ids).into();
    let nstate = NameState::new::<E>(&ent_intf, &gets_clone, &names_arc, &sem_ids_arc);
    let ccount = wait_for_data_copy(shared_cvp);
    let (k, v) = make_stats_entry_arc::<E>(&names_arc, &sem_ids_arc, &ent_intf.ccounts, ccount);
    au_clone.lock().unwrap().insert(k, v);
    let entities = nstate
        .responses
        .iter()
        .filter(|e| <E as IsTop>::is_top(e))
        .map(|e| e.clone())
        .collect();
    let tr = TopResult { name, entities };
    let ed = EntityDescription::new::<E>(nstate.responses.len());
    (E::NAME, (nstate, tr, ed))
}

fn main() {
    let n_threads: usize = std::env::var("RANKLESS_THREAD_COUNT")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(DEFAULT_N_THREADS);

    tokio::runtime::Builder::new_multi_thread()
        .worker_threads(n_threads)
        .enable_all()
        .build()
        .unwrap()
        .block_on(async_main(n_threads));
}

async fn async_main(n_threads: usize) {
    let shutdown = Arc::new(Notify::new());
    let shutdown_clone = shutdown.clone();
    let signal_task = tokio::spawn(async move {
        tokio::signal::ctrl_c().await.unwrap();
        shutdown_clone.notify_one();
    });

    let path: String = std::env::args().last().unwrap();
    let now = std::time::Instant::now();
    println!("threads: {n_threads} path: {path}");
    let stowage = Stowage::new(&path);
    let (ns_map, satts, tree_manager, counts_response, tops, peer_aux) =
        get_rest(stowage, n_threads);
    let ns_map_arc: Arc<NameStateMap> = ns_map.into();

    let response_api = Router::new()
        .route("/names/:etype", get(name_get))
        .route("/slice/:etype/:from/:to", get(slice_get))
        .route("/views/:etype/:semantic_id", get(view_get))
        .route("/sem-id-via-oa/:etype/:oa_id", get(sem_id_get))
        .route("/orcid/:orcid_id", get(orcid_get))
        .route("/resolve/work", get(resolve_work_get))
        .route("/resolve/author", get(resolve_author_get))
        .route("/paper-profile/:asem", get(paper_profile))
        .route("/peers/:etype/:semantic_id", get(peers_get))
        .route("/ladder/:etype", get(ladder_get))
        .route("/trees/:root_type/:semantic_id", get(tree_get))
        .route("/shallows/:root_type", get(shallows_get))
        .route("/works/:etype/:semantic_id/:from", get(works_get))
        .with_state((ns_map_arc, satts, tree_manager.clone(), peer_aux));

    let count_api = static_router(&counts_response);
    let specs_api = static_router(&tree_manager.specs);

    let tops_api = Router::new()
        .route("/", get(tops_get))
        .with_state(Arc::new(tops));

    let api = Router::new()
        .nest("/", response_api)
        .nest("/counts", count_api)
        .nest("/tops", tops_api)
        .nest("/specs", specs_api);

    let app = Router::new().nest("/v1", api);
    let loc_addr = SocketAddr::from(([127, 0, 0, 1], PORT));
    let stime = now.elapsed().as_secs();
    println!(
        "{loc_addr} set-up in {stime}s ({}min {}sec) - shd",
        stime / 60,
        stime % 60
    );
    let socket = Socket::new(Domain::IPV4, Type::STREAM, None).unwrap();
    socket.set_nonblocking(true).unwrap();
    loop {
        match socket.bind(&loc_addr.into()) {
            Ok(_) => break,
            Err(e) => {
                println!("error binding socket: {e}");
                sleep(time::Duration::from_secs(6));
            }
        }
    }
    socket.listen(1024).unwrap();
    let listener = TcpListener::from_std(socket.into()).unwrap();
    axum::serve(listener, app.into_make_service())
        .with_graceful_shutdown(async move {
            shutdown.notified().await;
        })
        .await
        .unwrap();
    signal_task.await.unwrap();
}

async fn slice_get(
    Path((etype, pstart, pend)): Path<(String, usize, usize)>,
    states: StatesT,
) -> Response<Body> {
    if let Some(state) = states.0 .0.get(etype.as_str()) {
        let start = min(pstart, state.responses.len() - 1);
        let end = min(
            max(start + 1, min(start + MAX_SLICE, pend)),
            state.responses.len(),
        );
        Json(&state.responses[start..end]).into_response()
    } else {
        (StatusCode::NOT_FOUND, "no such entity").into_response()
    }
}

async fn state_get(str_state: State<Arc<str>>) -> (HeaderMap, Response<Body>) {
    (cache_header(60), str_state.to_string().into_response())
}

async fn tree_get(
    Path((root_type, semantic_id)): Path<(String, String)>,
    tree_q: Query<TreeQ>,
    states: StatesT,
) -> (HeaderMap, Json<Option<TreeResponse>>) {
    let mut tq = tree_q.0;
    let (ns_map, _, tm, _) = states.0;
    if let Some(nstate) = ns_map.get(root_type.as_str()) {
        if (root_type == HitPapers::NAME) && (semantic_id == "all") {
            tq.cacheable = Some(true);
            //TODO: all hit papers
            // let resp = Json(tm.get_single_resp(tq, &root_type, HitPapers::N + 1));
            // return (cache_header(60), resp);
        }
        let psid = parse_semantic_id(semantic_id);
        if let Some(&dm_id) = nstate.semantic_id_map.get(psid.as_str()) {
            let dm_id_u = dm_id as usize;
            let ncite = nstate
                .response_id_from_dm(dm_id_u)
                .map(|rid| nstate.responses[rid].citations)
                .unwrap_or(0);
            tq.cacheable = Some(ncite >= CACHEABLE_FROM);
            let resp = Json(tm.get_single_resp(tq, &root_type, dm_id_u));
            return (cache_header(60), resp);
        }
    }
    (cache_header(0), None.into())
}

async fn shallows_get(
    Path(root_type): Path<String>,
    q: Query<ShallowQ>,
    states: StatesT,
) -> (HeaderMap, Json<Option<ShallowTreesResponse>>) {
    let resp = Json(states.0 .2.get_shallows(q.0, &root_type));
    (cache_header(60), resp)
}

async fn tops_get(tops_state: State<Arc<Vec<TopResult>>>) -> Json<Vec<TopResult>> {
    let mut rng = rand::thread_rng();
    const TOP_N: usize = 5;
    let out = tops_state
        .iter()
        .map(|e| TopResult {
            name: e.name.clone(),
            entities: e
                .entities
                .choose_multiple(&mut rng, TOP_N)
                .map(Clone::clone)
                .collect(),
        })
        .collect();
    Json(out)
}

async fn view_get(
    Path((etype, semantic_id)): Path<(String, String)>,
    states: StatesT,
) -> Json<Option<ViewResult>> {
    let satts = &states.0 .1;
    let mut out = None;
    if let Some(state) = states.0 .0.get(etype.as_str()) {
        let psid = parse_semantic_id(semantic_id);
        if let Some(&dm_id) = state.semantic_id_map.get(psid.as_str()) {
            let dm_id_u = dm_id as usize;
            if let Some(i) = state.response_id_from_dm(dm_id_u) {
                let srs = &state.responses[i];
                let similars = state.peers[dm_id_u]
                    .iter()
                    .filter(|&&pid| pid != 0)
                    .filter_map(|&pid| {
                        state
                            .response_id_from_dm(pid as usize)
                            .map(|rid| state.responses[rid].clone())
                    })
                    .collect();
                let gets = &states.0 .2.state.gets;
                let meta = compute_meta(etype.as_str(), dm_id_u, gets, &state.exts[i]);
                let vr = ViewResult {
                    similars,
                    ext: state.exts[i].to_serializable(satts, &states.0 .0),
                    sr: srs.clone(),
                    meta,
                };
                out = Some(vr)
            }
        };
    }
    Json(out)
}

async fn sem_id_get(
    Path((etype, oa_id)): Path<(String, u64)>,
    states: StatesT,
) -> Json<[Option<String>; 1]> {
    let mut out = None;
    if let Some(nstate) = states.0 .0.get(etype.as_str()) {
        if let Some(&rid) = nstate.oa_id_map.get(&oa_id) {
            let s = nstate.responses[rid as usize].semantic_id.to_string();
            out = Some(s);
        }
    }
    Json([out])
}

async fn resolve_work_get(
    q: Query<ResolveWorkQ>,
    states: StatesT,
) -> (StatusCode, Json<Option<ResolveWorkResp>>) {
    let trm = &states.0 .2;
    let gets = &trm.state.gets;
    let wid = if let Some(wid) = q.wid {
        if wid >= gets.work_oa.len() {
            return (StatusCode::NOT_FOUND, Json(None));
        }
        wid
    } else if let Some(oa_id) = q.oa_id {
        match gets.work_oa.iter().position(|&x| x == oa_id) {
            Some(i) => i,
            None => return (StatusCode::NOT_FOUND, Json(None)),
        }
    } else if q.doi.is_some() {
        // Phase 1: doi-only lookup not implemented (no reverse index built);
        // claim flow stores doi as primary identifier without resolution.
        return (StatusCode::NOT_IMPLEMENTED, Json(None));
    } else {
        return (StatusCode::BAD_REQUEST, Json(None));
    };
    let mut wname_handler: ManFileHandle = trm.get_file_handle();
    let mut doi_handler: VattReadingArcMap<WorkDois> = trm.get_file_handle();
    let name = wname_handler
        .get_via_mut(&wid)
        .unwrap_or_else(|| "Unknown".to_string());
    let doi = doi_handler.get_via_mut(&wid).unwrap_or_default();
    let resp = ResolveWorkResp {
        oa_id: gets.work_oa[wid],
        wid,
        doi,
        year: YearInterface::reverse(*gets.year(&wid)),
        name,
    };
    (StatusCode::OK, Json(Some(resp)))
}

async fn resolve_author_get(
    q: Query<ResolveAuthorQ>,
    states: StatesT,
) -> (StatusCode, Json<Option<ResolveAuthorResp>>) {
    let nstate = match states.0 .0.get(Authors::NAME) {
        Some(s) => s,
        None => return (StatusCode::NOT_FOUND, Json(None)),
    };
    let gets = &states.0 .2.state.gets;
    let dm_id: usize = if let Some(d) = q.dm_id {
        d
    } else if let Some(sem_id) = &q.semantic_id {
        let psid = parse_semantic_id(sem_id.clone());
        match nstate.semantic_id_map.get(psid.as_str()) {
            Some(&d) => d as usize,
            None => return (StatusCode::NOT_FOUND, Json(None)),
        }
    } else if let Some(orcid_str) = &q.orcid {
        let obytes: OrcidType = match orcid_str.as_bytes().try_into() {
            Ok(b) => b,
            Err(_) => return (StatusCode::BAD_REQUEST, Json(None)),
        };
        match gets.orcid_map.get(&obytes) {
            Some(&d) => d,
            None => return (StatusCode::NOT_FOUND, Json(None)),
        }
    } else if let Some(oa_id) = q.oa_id {
        match nstate.oa_id_map.get(&oa_id) {
            Some(&rid) => nstate.responses[rid as usize].dm_id,
            None => return (StatusCode::NOT_FOUND, Json(None)),
        }
    } else {
        return (StatusCode::BAD_REQUEST, Json(None));
    };
    let rid = match nstate.response_id_from_dm(dm_id) {
        Some(r) => r,
        None => return (StatusCode::NOT_FOUND, Json(None)),
    };
    let sr = &nstate.responses[rid];
    let na_orcid = OrcidType::default();
    let orcid = if dm_id < <Authors as Entity>::N {
        let bytes = *gets.author_orcids(&dm_id);
        if bytes == na_orcid {
            None
        } else {
            String::from_utf8(bytes.to_vec()).ok()
        }
    } else {
        None
    };
    let resp = ResolveAuthorResp {
        oa_id: sr.oa_id,
        dm_id: sr.dm_id,
        semantic_id: sr.semantic_id.to_string(),
        orcid,
        name: sr.name.to_string(),
    };
    (StatusCode::OK, Json(Some(resp)))
}

async fn orcid_get(Path(orcid_id): Path<String>, states: StatesT) -> Json<Option<SearchResult>> {
    let mut out = None;
    let obytes: ET<AuthorOrcids> = orcid_id
        .into_bytes()
        .into_iter()
        .collect::<Vec<u8>>()
        .try_into()
        .unwrap_or(<ET<AuthorOrcids> as Default>::default());
    if let Some(&a_dm_id) = states.0 .2.state.gets.orcid_map.get(&obytes) {
        if let Some(nstate) = states.0 .0.get(Authors::NAME) {
            if let Some(a_rid) = nstate.response_id_from_dm(a_dm_id) {
                let s = nstate.responses[a_rid].clone();
                out = Some(s);
            }
        }
    }
    Json(out)
}

async fn paper_profile(
    Path(author_sem_id): Path<String>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let astates = states.0 .0.get(Authors::NAME).unwrap();
    let gets = &states.0 .2.state.gets;
    let Some(&aid_dm) = astates.semantic_id_map.get(author_sem_id.as_str()) else {
        return get_empty();
    };
    let aid = aid_dm as usize;
    let Some(aid_rid) = astates.response_id_from_dm(aid) else {
        return get_empty();
    };
    let hw_set: HashSet<WT> = astates.exts[aid_rid]
        .hit_papers
        .iter()
        .map(|hwid| gets.hit_papers[hwid.to_usize()])
        .collect();

    let direct_hit_wids: Vec<WT> = gets
        .author_citing_direct(aid)
        .iter()
        .map(|&hid| gets.hit_papers[hid as usize] as WT)
        .collect();
    let once_hit_wids: Vec<WT> = gets
        .author_citing_once(aid)
        .iter()
        .map(|&hid| gets.hit_papers[hid as usize] as WT)
        .collect();

    let refed_wids: &[WT] = gets.aworks(ET::<Authors>::from_usize(aid));
    let refed_set: HashSet<WT> = refed_wids.iter().copied().collect();

    let mut conn = get_direct_links(gets, refed_set.clone(), &direct_hit_wids);
    extend_with_once_removed(gets, refed_set, &once_hit_wids, &mut conn);

    let wids = hw_set
        .iter()
        .chain(conn.wids.iter().filter(|wid| !hw_set.contains(*wid)))
        .map(|e| e.to_usize());

    let papers = get_paper_set_resp(wids, states.2.clone());
    let out = PaperProfileResp {
        dag: conn.dag,
        papers,
    };
    (cache_header(60), Json(out).into_response())
}

fn build_peer_entry(
    rid: usize,
    dm_id: usize,
    astates: &NameState,
    aux: &PeerAux,
    satts: &AttributeLabelUnion,
    sf_indices: &[usize],
) -> PeerEntry {
    let sr = &astates.responses[rid];
    let ext = &astates.exts[rid];
    let row = aux.cit_subfields.row(dm_id);
    let sf_cits: Vec<u32> = sf_indices.iter().map(|&si| row[si]).collect();
    let country = ext
        .prime_relations
        .iter()
        .find(|r| r.rel_type == 3)
        .and_then(|r| {
            satts
                .get(ETYPE_ENC[r.etype_id as usize])
                .and_then(|labels| labels.get(r.dm_id as usize))
                .map(|l| l.name.clone())
        });
    PeerEntry {
        name: sr.name.clone(),
        semantic_id: sr.semantic_id.clone(),
        papers: sr.papers,
        citations: sr.citations,
        subfield_citations: sf_cits,
        yearly_papers: ext.yearly_papers,
        yearly_cites: ext.yearly_cites,
        start_year: ext.start_year,
        h_index: aux.h_indices.as_ref().and_then(|h| h.get(dm_id).copied()),
        year_centroid: aux
            .year_centroids
            .as_ref()
            .and_then(|y| y.get(dm_id).copied()),
        country,
    }
}

async fn ladder_get(Path(etype): Path<String>, states: StatesT) -> (HeaderMap, Response) {
    let Some(nstate) = states.0 .0.get(etype.as_str()) else {
        return get_empty();
    };
    let ladder = nstate
        .cit_rank_ladder
        .iter()
        .map(|row| row.iter().map(|&t| (t != u32::MAX).then_some(t)).collect())
        .collect();
    let resp = LadderResp {
        pct_bands: &LADDER_PCT_BANDS,
        ladder,
    };
    (cache_header(1440), Json(resp).into_response())
}

async fn peers_get(
    Path((etype, sem_id)): Path<(String, String)>,
    states: StatesT,
) -> (HeaderMap, Response) {
    peers_inner(&etype, &sem_id, &states)
}

fn peers_inner(etype: &str, sem_id: &str, states: &StatesT) -> (HeaderMap, Response) {
    let (Some(astates), Some(aux)) = (states.0 .0.get(etype), states.0 .3.get(etype)) else {
        return get_empty();
    };
    let satts = &states.0 .1;

    let Some(&hero_dm) = astates.semantic_id_map.get(sem_id) else {
        return get_empty();
    };
    let hero_dm = hero_dm as usize;
    let Some(hero_rid) = astates.response_id_from_dm(hero_dm) else {
        return get_empty();
    };

    let sf_atts = &satts[Subfields::NAME];
    let sf_row = aux.cit_subfields.row(hero_dm);
    // All subfields the hero has citations in, most-cited first. The client defaults to the top few
    // and lets the user expand the comparison basis, so no refetch is needed on selection change.
    let mut sf_scores: Vec<(usize, u32)> = (0..N_SUBFIELDS)
        .map(|si| (si, sf_row[si]))
        .filter(|(_, c)| *c > 0)
        .collect();
    sf_scores.sort_unstable_by(|a, b| b.1.cmp(&a.1));
    let sf_indices: Vec<usize> = sf_scores.into_iter().map(|(si, _)| si).collect();

    let top_subfields: Vec<PeerSubfieldInfo> = sf_indices
        .iter()
        .map(|&si| {
            let att = &sf_atts[si];
            PeerSubfieldInfo {
                name: att.name.clone(),
                semantic_id: att.semantic_id.clone(),
                dm_id: si,
            }
        })
        .collect();

    let hero = build_peer_entry(hero_rid, hero_dm, astates, aux, satts, &sf_indices);

    let peers: Vec<PeerEntry> = astates.peers[hero_dm]
        .iter()
        .filter(|&&pid| pid != 0)
        .filter_map(|&pid| {
            let peer_dm = pid as usize;
            astates
                .response_id_from_dm(peer_dm)
                .map(|rid| build_peer_entry(rid, peer_dm, astates, aux, satts, &sf_indices))
        })
        .collect();

    let resp = EntityPeersResp {
        top_subfields,
        peers,
        hero,
    };
    (cache_header(60), Json(resp).into_response())
}

async fn name_get(
    Path(etype): Path<String>,
    q: Query<BasicQ>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let q_string = q.q.as_deref().unwrap_or("");
    let ns_map = &states.0 .0;
    if etype == "all" {
        const UNION_ORDER: [&str; 6] = [
            Authors::NAME,
            Institutions::NAME,
            Sources::NAME,
            Countries::NAME,
            Subfields::NAME,
            HitPapers::NAME,
        ];
        let out: Vec<UnionSearchResult> = UNION_ORDER
            .iter()
            .filter_map(|&rt| ns_map.get(rt).map(|state| (rt, state)))
            .flat_map(|(rt, state)| {
                state
                    .engine
                    .query(q_string)
                    .into_iter()
                    .filter_map(move |e| {
                        state.responses.get(e as usize).map(|sr| UnionSearchResult {
                            sr: sr.clone(),
                            root_type: rt,
                        })
                    })
            })
            .collect();
        return (cache_header(60), Json(out).into_response());
    }
    if let Some(state) = ns_map.get(etype.as_str()) {
        let top_n_inds = state.engine.query(q_string);
        let resp: Json<Vec<SearchResult>> = Json(
            top_n_inds
                .into_iter()
                .filter(|e| (*e as usize) < state.responses.len())
                .map(|e| state.responses[e as usize].clone())
                .collect(),
        );
        (cache_header(60), resp.into_response())
    } else {
        get_empty()
    }
}

async fn works_get(
    Path((etype, sem_id, pstart)): Path<(String, String, usize)>,
    Query(wq): Query<WorksQ>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let page_size =
        wq.n.unwrap_or(consts::WORKS_PAGE_SIZE_MAX)
            .min(consts::WORKS_PAGE_SIZE_MAX);
    if let Some(state) = states.0 .0.get(etype.as_str()) {
        let psid = parse_semantic_id(sem_id);
        if let Some(&dm_id) = state.semantic_id_map.get(psid.as_str()) {
            if let Some(work_arr) = states
                .0
                 .2
                .state
                .gets
                .works_of_entity(dm_id as usize, etype)
            {
                if !work_arr.is_empty() {
                    let start = min(pstart, work_arr.len() - 1);
                    let wids = work_arr[start..].iter().take(page_size).map(WT::to_usize);
                    let resp = get_paper_set_resp(wids, states.2.clone());
                    let out = PaginatedPaperSetResp {
                        resp,
                        total_papers: work_arr.len(),
                        slice_start: start,
                    };
                    return (cache_header(60), Json(out).into_response());
                }
            }
        }
    }
    get_empty()
}

fn get_paper_set_resp<I>(wids: I, trm: Arc<InstTrm>) -> PaperSetResp
where
    I: Iterator<Item = usize>,
{
    let mut disc_author_names = HashMap::new();
    let mut authors_meta = HashMap::new();
    let mut wnames_handle = trm.get_file_handle();
    let mut doi_hand = trm.get_file_handle();
    let mut dan_hand = trm.get_file_handle();

    let mut entity_atts: EntityAttsForLinks = HashMap::new();
    let papers = wids
        .map(|wid| {
            paper_out(
                wid.to_usize(),
                &trm.state.gets,
                &mut wnames_handle,
                &mut doi_hand,
                &mut dan_hand,
                &mut disc_author_names,
                &mut authors_meta,
                &mut entity_atts,
                &trm.state.att_union,
            )
        })
        .collect();
    PaperSetResp {
        papers,
        entity_atts,
        disc_author_names,
        authors_meta,
    }
}

fn paper_out(
    wid: usize,
    gets: &Getters,
    wname_handler: &mut ManFileHandle,
    doi_handler: &mut VattReadingArcMap<WorkDois>,
    disc_name_handler: &mut VattReadingArcMap<DiscardedAuthorsNames>,
    discarded_author_name_map: &mut HashMap<String, String>,
    authors_meta: &mut HashMap<usize, PaperAuthorMeta>,
    entity_atts: &mut EntityAttsForLinks,
    att_union: &AttributeLabelUnion,
) -> PaperOut {
    let mut yearly_cites = None;
    let mut is_hit = false;
    let mut hit_bm = None;
    let mut hit_sem_id = None;
    let mut created_topic = None;
    let (name, doi) = if let (Some(hwid), Some(hit_attlu)) = (
        gets.hit_wid_map.get(&WT::from_usize(wid)),
        att_union.get(HitPapers::NAME),
    ) {
        let hit_atts = &hit_attlu[*hwid];
        let name = hit_atts.name.to_string();
        hit_sem_id = Some(hit_atts.semantic_id.to_string());
        let ct = gets.hit_created_topic(hwid).to_usize();
        if ct != 0 {
            created_topic = att_union
                .get(Topics::NAME)
                .and_then(|labels| labels.get(ct))
                .map(|label| label.name.to_string());
        }
        let doi = if hit_atts.semantic_id.starts_with("W") {
            hit_atts.semantic_id.to_string()
        } else {
            String::new()
        };
        yearly_cites = Some(gets.hit_yearlies(*hwid).into());
        hit_bm = Some(gets.hit_bms(hwid).to_usize() as u32);
        is_hit = true;
        (name, doi)
    } else {
        let name = wname_handler
            .get_via_mut(&wid)
            .unwrap_or("Unknown".to_string());
        let doi = doi_handler.get_via_mut(&wid).unwrap_or("".to_string());
        (name, doi)
    };
    let mut add_to_eatts = |etype: &str, k: usize| {
        if let Some(u_eatts) = att_union.get(etype) {
            let eatts = entity_atts
                .entry(etype.to_string())
                .or_insert_with(HashMap::new);
            if eatts.contains_key(&k) {
                return;
            };
            if let Some(v) = u_eatts.get(k) {
                eatts.insert(k, v.clone());
            }
        }
    };
    //this is similarly to String with hit paper names not automatically remakes
    //the var sized element from &[SubType]
    let biblio = Some(<ET<WorkBiblios> as ByteArrayInterface>::from_bytes(
        gets.wbiblios(wid),
    ));
    let mut positioned_ships: Vec<(usize, PaperAuthorship)> = Vec::new();
    for anyship in gets.wanyships(wid) {
        let (is_filterd, ship_id) = reverse_prefixed_n(anyship.to_usize());
        let (full_aid, insts_slice, position) = if is_filterd {
            let aid = gets.fshipa(&ship_id);
            add_to_eatts(Authors::NAME, aid.to_usize());
            let prize_rec = gets.author_prizes(aid);
            authors_meta.insert(
                aid.to_usize(),
                PaperAuthorMeta {
                    prize: prize_rec.0,
                    year: YearInterface::reverse(prize_rec.1),
                },
            );
            let pos = gets.fship_pos(&ship_id).to_usize();
            (format!("F{aid}"), gets.fshipis(ship_id), pos)
        } else {
            let aid = gets.dshipa(&ship_id);
            let name = disc_name_handler
                .get_via_mut(&aid.to_usize())
                .unwrap_or("Unknown".to_string());
            let full_aid = format!("D{aid}");
            discarded_author_name_map.insert(full_aid.clone(), name);
            let pos = gets.dship_pos(&ship_id).to_usize();
            (full_aid, gets.dshipis(ship_id), pos)
        };
        let mut insts = Vec::new();
        for iid in insts_slice {
            add_to_eatts(Institutions::NAME, iid.to_usize());
            insts.push(iid.to_usize());
        }
        positioned_ships.push((
            position,
            PaperAuthorship {
                author: full_aid,
                insts,
            },
        ));
    }
    positioned_ships.sort_by_key(|(p, _)| *p);
    let authorships: Vec<PaperAuthorship> = positioned_ships.into_iter().map(|(_, a)| a).collect();
    let source = gets.top_source(&wid).to_usize();
    add_to_eatts(Sources::NAME, source);

    PaperOut {
        wid,
        oa_id: gets.work_oa.get(wid).copied().unwrap_or(0),
        year: YearInterface::reverse(*gets.year(&wid)),
        name,
        hit_sem_id,
        doi,
        citations: gets.wccount(wid) as u32,
        yearly_cites,
        biblio,
        source,
        authorships,
        is_hit,
        hit_bm,
        created_topic,
    }
}

fn cache_header(mins: usize) -> HeaderMap {
    let mut headers = HeaderMap::new();
    headers.insert(
        CACHE_CONTROL,
        HeaderValue::from_str(&format!("public, max-age={}", mins * 60)).unwrap(),
    );
    headers
}

fn static_router<O: Serialize>(o: &O) -> Router {
    let arc: Arc<str> = Arc::from(serde_json::to_string(o).unwrap().as_str());
    Router::new().route("/", get(state_get)).with_state(arc)
}

fn parse_semantic_id(id: String) -> String {
    id.replace("%2F", "/")
}

fn compute_meta(
    etype: &str,
    dm_id: usize,
    gets: &Getters,
    ext: &EntityExt,
) -> Option<HashMap<&'static str, String>> {
    if etype == Authors::NAME {
        author_meta(dm_id, gets, ext)
    } else if etype == Institutions::NAME {
        inst_meta(dm_id, gets)
    } else {
        None
    }
}

fn author_meta(
    dm_id: usize,
    gets: &Getters,
    ext: &EntityExt,
) -> Option<HashMap<&'static str, String>> {
    let slug = String::from_utf8(gets.aslugs(dm_id).to_vec()).unwrap_or_default();
    let any_hits = if (gets.author_citing_once(dm_id).len() > 0)
        || (gets.author_citing_direct(dm_id).len() > 0)
        || (ext.hit_papers.len() > 0)
    {
        "1"
    } else {
        "0"
    };
    let na_orcid: ET<AuthorOrcids> = <ET<AuthorOrcids> as Default>::default();
    let orcid_o = gets.author_orcids(&dm_id);
    let orcid = if orcid_o == &na_orcid {
        ""
    } else {
        std::str::from_utf8(orcid_o).unwrap_or("")
    };
    let kvs = vec![
        ("wikiSlug", slug),
        ("rawCites", gets.raw_cites(&dm_id).to_string()),
        ("rawPapers", gets.raw_works(&dm_id).to_string()),
        ("anyHits", any_hits.to_string()),
        ("orcid", orcid.to_string()),
    ];
    Some(HashMap::from_iter(kvs.into_iter()))
}

fn inst_meta(dm_id: usize, gets: &Getters) -> Option<HashMap<&'static str, String>> {
    let loc = gets.iloc(&dm_id);
    let kvs = vec![("lat", loc.0.to_string()), ("lon", loc.1.to_string())];
    Some(HashMap::from_iter(kvs.into_iter()))
}

fn add_to_relations<RE, T>(arr: &[(u32, T)], prels: &mut Vec<PreAttRelatedEntity>, rel_type: u8)
where
    RE: Entity,
    T: UnsignedNumber,
{
    arr.iter().for_each(|e| {
        let etype_id = ETYPE_ENC
            .iter()
            .enumerate()
            .filter(|e| *e.1 == RE::NAME)
            .next()
            .unwrap()
            .0 as u8;
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

fn get_empty() -> (HeaderMap, Response) {
    (
        HeaderMap::new(),
        (StatusCode::NOT_FOUND, "no such entity").into_response(),
    )
}
