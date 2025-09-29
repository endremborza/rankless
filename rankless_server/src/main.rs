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
    para_multi_gen_run, Entity, InitEmpty, NamespacedEntity, UnsignedNumber, ET,
};
use hashbrown::HashMap;
use kd_tree::{KdPoint, KdTree};
use rand::{rngs::StdRng, seq::SliceRandom, SeedableRng};
use serde::{Deserialize, Serialize};
use socket2::{Domain, Socket, Type};
use std::{
    cmp::{max, min},
    net::SocketAddr,
    sync::{Arc, Mutex},
    thread::sleep,
    time,
};
use tokio::{net::TcpListener, sync::Notify};

use muwo_search::SearchEngine;
use rankless_rs::{
    common::{MainEntity, NET},
    gen::a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics},
    gen::derive_links3::HitPapers,
    steps::{
        a1_entity_mapping::{Qs, RawYear, YearInterface, Years},
        derive_links5::{EraRec, InstRelation},
    },
    Stowage,
};
use rankless_trees::{
    extensions::DistinctionText,
    interfacing::{
        Getters, MetaMapGetter, NodeInterfaceable, NodeInterfaces, RootInterfaceable,
        RootInterfaces,
    },
    io::{ShallowQ, ShallowTreesResponse, TreeQ, TreeResponse, TreeRunManager},
    AttributeLabelUnion,
};

const MAX_HITS: usize = 80;
const PORT: u16 = 3038;
const SEARCH_SIZE: usize = 20;
const MAX_SLICE: usize = 40_000;
const CACHEABLE_FROM: u32 = 10_000;
const N_THREADS: usize = 16;
const UPPER_LIMIT: u32 = u32::MAX;
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
type Coords = [f64; 2];
type NameStateMap = HashMap<&'static str, NameState>;
type StatesT = State<(Arc<NameStateMap>, Arc<AttributeLabelUnion>, Arc<InstTrm>)>;
type StateKv = (&'static str, (NameState, TopResult, EntityDescription));

#[derive(Deserialize)]
struct BasicQ {
    q: Option<String>,
}

#[derive(Serialize)]
struct ViewResult {
    #[serde(flatten)]
    sr: SearchResult,
    #[serde(flatten)]
    ext: ResultExtension,
    #[serde(flatten)]
    prep_ext: PostAttResultExtension,
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

struct NameState {
    engine: SearchEngine<SEARCH_SIZE>,
    responses: Box<[SearchResult]>,
    exts: Box<[ResultExtension]>,
    prep_exts: Box<[PreAttResultExtension]>,
    means: Box<Coords>,
    vars: Box<Coords>,
    pub semantic_id_map: HashMap<String, SemVal>,
    pub oa_id_map: HashMap<usize, usize>,
    query_tree: KdTree<KDItem>,
}

#[derive(Clone)]
struct SemVal {
    result_id: usize,
    dm_id: usize,
}

#[derive(Serialize, Clone)]
struct EntityRelationshipOut {
    start: u16,
    end: u16,
    #[serde(rename = "semId")]
    inst_sem_id: String,
    #[serde(rename = "name")]
    inst_name: String,
    papers: u16,
    citations: u32,
}

#[derive(Serialize, Clone)]
struct PaperOut {
    year: u16,
    name: String,
    doi: String,
    citations: u32,
    #[serde(rename = "yearlyCites", skip_serializing_if = "Option::is_none")]
    yearly_cites: Option<Box<[u32]>>,
}

#[derive(Serialize, Clone)]
struct SearchResult {
    name: String,
    #[serde(rename = "semanticId")]
    semantic_id: String,
    #[serde(skip_serializing)]
    full_name: String,
    #[serde(skip_serializing)]
    oa_id: u64,
    #[serde(rename = "dmId")]
    dm_id: usize,
    #[serde(rename = "distinctText", skip_serializing_if = "Option::is_none")]
    distinct_text: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    meta: Option<HashMap<&'static str, String>>,
    papers: u32,
    citations: u32,
}

#[derive(Serialize, Clone)]
struct ResultExtension {
    // #[serde(rename = "instRels")]
    // inst_rels: Box<[InstRelOut]>,
    #[serde(rename = "startYear")]
    start_year: RawYear,
    #[serde(rename = "yearlyPapers")]
    yearly_papers: EraRec,
    #[serde(rename = "yearlyCites")]
    yearly_cites: EraRec,
}

#[derive(Serialize, Clone)]
struct PostAttResultExtension {
    #[serde(rename = "primeRelations")]
    prime_relations: Vec<PostAttRelatedEntity>,
    #[serde(rename = "hitPapers")]
    hit_papers: Box<[PaperOut]>,
    #[serde(rename = "authorNetwork")]
    author_network: Box<[u8]>,
}

struct PreAttResultExtension {
    prime_relations: Box<[PreAttRelatedEntity]>,
    hit_papers: Box<[usize]>,
    author_network: Box<[u8]>,
}

struct KDItem {
    point: Coords,
    id: usize,
}

trait PrepFilter: RootInterfaceable + Sized {
    //TODO: move to dmove steps, so that gets is not needed
    fn filter_sr(sr: &SearchResult, _gets: &Getters, _entif: &RootInterfaces<Self>) -> bool {
        (sr.full_name.trim().len() > 0)
            & (sr.semantic_id.trim().len() > 0)
            & (sr.papers > 1)
            & (sr.citations > 2)
            & (sr.citations <= UPPER_LIMIT)
    }

    fn is_top(_sr: &SearchResult) -> bool {
        true
    }
}

macro_rules! i_fil {
    ($($t:ty),*) => {
        $(impl PrepFilter for $t {})*
    };
}

i_fil!(Countries, Subfields);

impl PrepFilter for HitPapers {
    fn filter_sr(_sr: &SearchResult, _gets: &Getters, _entif: &RootInterfaces<Self>) -> bool {
        true
    }
    fn is_top(_sr: &SearchResult) -> bool {
        false
    }
}

impl PrepFilter for Authors {
    fn filter_sr(sr: &SearchResult, _gets: &Getters, entif: &RootInterfaces<Self>) -> bool {
        let max_yearly_pcount = *entif.yearly_papers[sr.dm_id].iter().max().unwrap_or(&0);
        let is_not_paper_mill = (sr.papers < 10_000) & (max_yearly_pcount < 300);
        (sr.full_name.trim().len() > 0)
            & (sr.semantic_id.trim().len() > 0)
            & (sr.papers > 1)
            & (sr.citations > 2)
            & is_not_paper_mill
            & !(consts::AUTHOR_BLACKLIST.contains(&sr.oa_id))
    }

    fn is_top(sr: &SearchResult) -> bool {
        consts::FIN_AUTHORS.contains(&sr.semantic_id.as_str())
    }
}

impl PrepFilter for Institutions {
    fn is_top(sr: &SearchResult) -> bool {
        const FIN_UNIS: [&str; 2] = ["budapesti-corvinus-egyetem", "tse"];
        let min_citations: u32 = 8_000_000;
        FIN_UNIS.contains(&sr.semantic_id.as_str()) || sr.citations > min_citations
    }
}

impl PrepFilter for Sources {
    fn filter_sr(sr: &SearchResult, gets: &Getters, _entif: &RootInterfaces<Self>) -> bool {
        let id = NET::<Sources>::from_usize(sr.dm_id);
        let mut best_q = 5;
        for ty8 in YearInterface::iter() {
            let q = *gets.sqy(&(id, ty8));
            if q != 0 {
                best_q = min(best_q, q);
            }
        }
        (sr.full_name.trim().len() > 0)
            & (sr.semantic_id.trim().len() > 0)
            & (sr.papers > 10)
            & (sr.citations > 20)
            & (sr.citations <= UPPER_LIMIT)
            & (best_q <= 2)
    }

    fn is_top(sr: &SearchResult) -> bool {
        consts::FIN_SOURCES.contains(&sr.semantic_id.as_str())
    }
}

impl KdPoint for KDItem {
    type Scalar = f64;
    type Dim = typenum::U2;
    fn at(&self, k: usize) -> f64 {
        self.point[k]
    }
}

impl SearchResult {
    fn new<E>(
        i: usize,
        name: String,
        ext: String,
        semantic_id: String,
        distinct_text: Option<String>,
        entif: &RootInterfaces<E>,
        gets: &Getters,
    ) -> Self
    where
        E: RootInterfaceable + MetaMapGetter,
    {
        let papers = if entif.wcounts.len() > i {
            entif.wcounts[i].to_usize()
        } else {
            1
        } as u32;
        Self {
            full_name: format!("{name} {ext}").trim().to_string(),
            name,
            semantic_id,
            distinct_text,
            papers,
            citations: entif.ccounts[i].to_usize() as u32,
            oa_id: entif.oa_id[i],
            meta: E::get_meta(i, gets),
            dm_id: i,
        }
    }
}

impl ResultExtension {
    fn from_resps<E>(responses: &Box<[SearchResult]>, entif: &RootInterfaces<E>) -> Box<[Self]>
    where
        E: RootInterfaceable,
    {
        let mut out = Vec::new();
        for res in responses.iter() {
            let i = res.dm_id;

            let mut sy_ind = 0;
            let mut yearly_papers = EraRec::init_empty();
            if let Some(ypi) = entif.yearly_papers.get(i) {
                yearly_papers = ypi.clone();
                for (yi, ycount) in ypi.into_iter().enumerate() {
                    if (sy_ind == 0) & (*ycount > 0) {
                        sy_ind = yi;
                        break;
                    }
                }
            }
            // let get_rem = |arr: &Box<[EraRec]>| arr[i].iter().skip(sy_ind).map(|e| *e).collect();
            // let yearly_cites = get_rem(&entif.yearly_cites);
            // let yearly_papers = get_rem(&entif.yearly_papers);

            out.push(Self {
                start_year: YearInterface::reverse(sy_ind as ET<Years>),
                yearly_cites: entif.yearly_cites[i].clone(),
                yearly_papers,
            })
        }

        out.into()
    }
}

impl PreAttResultExtension {
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
                let mut prime_relations = Vec::new();
                let mut hit_papers = Vec::new();
                let mut author_collabs = Vec::new();
                if E::NAME != HitPapers::NAME {
                    add_to_relations::<Subfields, _>(
                        &entif.top_paper_sfc[i],
                        &mut prime_relations,
                        0,
                    );
                    add_to_relations::<Subfields, _>(
                        &entif.top_citing_sfc[i],
                        &mut prime_relations,
                        1,
                    );
                    add_to_relations::<Topics, _>(
                        &entif.top_paper_topic[i],
                        &mut prime_relations,
                        2,
                    );
                    add_to_relations::<Countries, _>(
                        &entif.top_aff_countries[i],
                        &mut prime_relations,
                        3,
                    );
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
                    if let Some(hits) = entif.hit_works.0.get(i) {
                        hits.iter()
                            .take(MAX_HITS)
                            .for_each(|e| hit_papers.push(e.to_usize()));
                    }
                }
                Self {
                    prime_relations: prime_relations.into(),
                    hit_papers: hit_papers.into(),
                    author_network: author_collabs.into_boxed_slice(),
                }
            })
            .collect()
    }

    fn to_post(
        &self,
        satts: &AttributeLabelUnion,
        nstates: &NameStateMap,
        gets: &Getters,
    ) -> PostAttResultExtension {
        let prime_relations = self
            .prime_relations
            .iter()
            .filter_map(|sr| {
                let etype = ETYPE_ENC[sr.etype_id as usize];
                let att = &satts[etype][sr.dm_id.to_usize()];
                let mut semantic_id = "".to_string();
                if let Some(rstate) = nstates.get(etype) {
                    if let Some(_) = rstate.semantic_id_map.get(&att.semantic_id) {
                        semantic_id = att.semantic_id.clone();
                    } else {
                        return None;
                    }
                }
                Some(PostAttRelatedEntity {
                    semantic_id,
                    name: att.name.clone(),
                    etype: etype.to_string(),
                    rel_type: sr.rel_type,
                    score: sr.score,
                })
            })
            .collect();
        let hit_papers = self
            .hit_papers
            .iter()
            .map(|hwid| {
                let wid = gets.hit_papers[*hwid].to_usize();
                PaperOut {
                    year: YearInterface::reverse(*gets.year(&wid)),
                    name: String::from_utf8(gets.hit_names(*hwid).to_vec()).unwrap(),
                    doi: String::from_utf8(gets.hit_dois(*hwid).to_vec()).unwrap(),
                    citations: *gets.wccount(&wid) as u32,
                    yearly_cites: Some(gets.hit_yearlies(*hwid).into()),
                }
            })
            .collect();
        PostAttResultExtension {
            prime_relations,
            hit_papers,
            author_network: self.author_network.clone(),
        }
    }
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

impl NameState {
    fn new<E>(entif: &RootInterfaces<E>, gets: &Getters) -> Self
    where
        E: RootInterfaceable + PrepFilter + DistinctionText + MetaMapGetter,
    {
        let responses = Self::get_resps(entif, gets);
        let now = std::time::Instant::now();
        let engine = SearchEngine::new(responses.iter().map(|e| e.full_name.clone()));
        println!(
            "search engine for {} (n={}) in {}s",
            E::NAME,
            responses.len(),
            now.elapsed().as_secs()
        );
        let mut semantic_id_map = HashMap::new();
        let mut oa_id_map = HashMap::new();
        let mut kdt_base = Vec::new();
        let (mut means, mut vars) = ([0.0, 0.0], [0.0, 0.0]);
        let float_n = f64::from(responses.len() as u32);
        for (i, res) in responses.iter().enumerate() {
            let kd_rec = get_arr_base(res);
            for j in 0..kd_rec.len() {
                means[j] += kd_rec[j] / float_n;
            }
            kdt_base.push(kd_rec);
            let dm_id = res.dm_id;
            let oa_id = entif.oa_id[dm_id as usize];
            oa_id_map.insert(oa_id.to_usize(), i);
            semantic_id_map.insert(
                res.semantic_id.clone(),
                SemVal {
                    result_id: i,
                    dm_id,
                },
            );
        }

        for rec in kdt_base.iter_mut() {
            for i in 0..rec.len() {
                rec[i] -= means[i];
                vars[i] += rec[i].powi(2) / float_n;
            }
        }

        for rec in kdt_base.iter_mut() {
            for i in 0..rec.len() {
                rec[i] /= vars[i].sqrt();
            }
        }

        let query_tree = tree_from_iter(kdt_base);

        Self {
            engine: engine.into(),
            exts: ResultExtension::from_resps(&responses, entif),
            prep_exts: PreAttResultExtension::from_resps(&responses, entif, gets),
            responses,
            semantic_id_map,
            oa_id_map,
            query_tree,
            means: means.into(),
            vars: vars.into(),
        }
    }

    fn get_resps<E>(entif: &RootInterfaces<E>, gets: &Getters) -> Box<[SearchResult]>
    where
        E: RootInterfaceable + PrepFilter + DistinctionText + MetaMapGetter,
    {
        let dist_txt = <E as DistinctionText>::get_distinction_text_arr(entif, gets);
        let ext_txt = &entif.name_exts.0;
        let mut responses: Vec<SearchResult> = entif
            .names
            .0
            .iter()
            .zip(entif.sem_ids.0.iter())
            .zip(dist_txt.to_vec().into_iter())
            .enumerate()
            .map(|(i, ((name, semantic_id), dist_txt))| {
                let ext = if ext_txt.len() > i {
                    ext_txt[i].to_string()
                } else {
                    "".to_string()
                };
                SearchResult::new(
                    i,
                    name.to_string(),
                    ext,
                    semantic_id.to_string(),
                    dist_txt,
                    entif,
                    gets,
                )
            })
            .filter(|sr| E::filter_sr(sr, gets, entif))
            .collect();
        responses.sort_by_key(|e| u32::MAX - e.citations);
        responses.into()
    }
}

fn coord_dist(l: &Coords, r: &Coords) -> f64 {
    (l[0] - r[0]).powf(2.0) + (l[1] - r[1]).powf(2.0)
}

impl EntityDescription {
    fn new<E: Entity>(count: usize) -> Self {
        Self {
            name: <E as Entity>::NAME.to_string(),
            count,
        }
    }
}

impl EntityRelationshipOut {
    fn from(v: &InstRelation, iif: &RootInterfaces<Institutions>, gets: &Getters) -> Self {
        let iid = v.inst.to_usize();
        let inst_name = iif.names.0.get(iid).unwrap().clone();
        let mut inst_sem_id = iif.sem_ids.0.get(iid).unwrap().clone();

        let i_sr = SearchResult::new(
            iid,
            inst_name.to_string(),
            "".to_string(),
            inst_sem_id.to_string(),
            None,
            iif,
            gets,
        );
        if !Institutions::filter_sr(&i_sr, gets, iif) {
            inst_sem_id = "".to_string();
        }

        Self {
            start: YearInterface::reverse(v.start),
            end: YearInterface::reverse(v.end),
            inst_name,
            inst_sem_id,
            citations: v.citations,
            papers: v.papers,
        }
    }
}

fn get_rest(
    stowage: Stowage,
) -> (
    NameStateMap,
    Arc<AttributeLabelUnion>,
    Arc<InstTrm>,
    Vec<EntityDescription>,
    Vec<TopResult>,
) {
    let gets = Arc::new(Getters::new(Arc::new(stowage)));
    let mux_satts: Arc<Mutex<AttributeLabelUnion>> = Arc::new(Mutex::new(HashMap::new()));
    let cv_pair = AcTuple::<Option<f64>>::init_empty();
    let mut ns_map: NameStateMap = HashMap::new();
    let mut tops = Vec::new();
    let mut descriptions = Vec::new();
    {
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
    }
    print_mem_use("after ei ns map");
    let satts = Arc::into_inner(mux_satts).unwrap().into_inner().unwrap();
    let asatts = Arc::new(satts);
    let tm: Arc<InstTrm> = TreeRunManager::new(gets, asatts.clone(), N_THREADS);
    print_mem_use("got tm");
    (ns_map, asatts, tm, descriptions, tops)
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
    NodeInterfaces::<T>::new(&gets.stowage).update_stats(&mut mux_satts.lock().unwrap(), *ccount);
}

fn get_state_tr_ed_kv<E>(
    full_tup: &(
        Arc<Getters>,
        Arc<Mutex<AttributeLabelUnion>>,
        AcTuple<Option<f64>>,
    ),
) -> StateKv
where
    E: RootInterfaceable
        + PrepFilter
        + MainEntity
        + NamespacedEntity
        + DistinctionText
        + MetaMapGetter,
{
    let (gets_clone, au_clone, shared_cvp) = full_tup.clone();
    let name = E::NAME.to_string();
    let ent_intf = RootInterfaces::<E>::new(&gets_clone.stowage);
    let nstate = NameState::new::<E>(&ent_intf, &gets_clone);
    let ccount = wait_for_data_copy(shared_cvp);
    ent_intf.update_stats(&mut au_clone.lock().unwrap(), ccount);
    let entities = nstate
        .responses
        .iter()
        .filter(|e| <E as PrepFilter>::is_top(e))
        .map(|e| e.clone())
        .collect();
    let tr = TopResult { name, entities };
    let ed = EntityDescription::new::<E>(nstate.responses.len());
    (E::NAME, (nstate, tr, ed))
}

#[tokio::main(worker_threads = 16)]
async fn main() {
    let shutdown = Arc::new(Notify::new());
    let shutdown_clone = shutdown.clone();
    let signal_task = tokio::spawn(async move {
        tokio::signal::ctrl_c().await.unwrap();
        shutdown_clone.notify_one();
    });

    let path: String = std::env::args().last().unwrap();
    let now = std::time::Instant::now();
    println!("reading from path: {}", path);
    let stowage = Stowage::new(&path);
    let (ns_map, satts, tree_manager, entity_descriptions, tops) = get_rest(stowage);
    let ns_map_arc: Arc<NameStateMap> = ns_map.into();

    let response_api = Router::new()
        .route("/names/:etype", get(name_get))
        .route("/slice/:etype/:from/:to", get(slice_get))
        .route("/views/:etype/:semantic_id", get(view_get))
        .route("/sem-id-via-oa/:etype/:oa_id", get(sem_id_get))
        .route("/trees/:root_type/:semantic_id", get(tree_get))
        .route("/shallows/:root_type", get(shallows_get))
        .with_state((ns_map_arc, satts, tree_manager.clone()));

    let count_api = static_router(&entity_descriptions);
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
    let (ns_map, _, tm) = states.0;
    if let Some(nstate) = ns_map.get(root_type.as_str()) {
        let psid = parse_semantic_id(semantic_id);
        if let Some(sval) = nstate.semantic_id_map.get(&psid) {
            let ncite = nstate.responses[sval.result_id].citations;
            tq.cacheable = Some(ncite >= CACHEABLE_FROM);
            let resp = Json(tm.get_single_resp(tq, &root_type, sval.dm_id));
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
    let satts = states.0 .1;
    let tm = states.0 .2;
    let mut out = None;
    if let Some(state) = states.0 .0.get(etype.as_str()) {
        let psid = parse_semantic_id(semantic_id);
        if let Some(sem_val) = state.semantic_id_map.get(&psid) {
            let i = sem_val.result_id;
            let srs = &state.responses[i];
            let ext = &state.exts[i];
            let query = get_query_arr(&srs, &state);
            let n_close = min(state.responses.len() / 20, 500);
            let mut closes = state.query_tree.nearests(&query, n_close);
            let mut rng = StdRng::seed_from_u64(742);
            closes.shuffle(&mut rng);
            let similars = closes
                .iter()
                .take(8)
                .filter(|e| e.item.id != i)
                .map(|e| state.responses[e.item.id].clone())
                .collect();

            let vr = ViewResult {
                similars,
                ext: ext.clone(),
                sr: srs.clone(),
                prep_ext: state.prep_exts[i].to_post(&satts, &states.0 .0, &tm.state.gets),
            };
            out = Some(vr)
        };
    }
    Json(out)
}

async fn sem_id_get(
    Path((etype, oa_id)): Path<(String, usize)>,
    states: StatesT,
) -> Json<[Option<String>; 1]> {
    let mut out = None;
    if let Some(nstate) = states.0 .0.get(etype.as_str()) {
        if let Some(e) = nstate.oa_id_map.get(&oa_id) {
            let s = nstate.responses[*e].semantic_id.clone();
            out = Some(s);
        }
    }
    Json([out])
}

async fn name_get(
    Path(etype): Path<String>,
    q: Query<BasicQ>,
    states: StatesT,
) -> (HeaderMap, Response) {
    if let Some(state) = states.0 .0.get(etype.as_str()) {
        let q_string = q.q.clone().unwrap_or("".to_string());
        let top_n_inds = state.engine.query(&q_string);
        let resp: Json<Vec<SearchResult>> = Json(
            top_n_inds
                .into_iter()
                .filter(|e| (*e as usize) < state.responses.len())
                .map(|e| state.responses[e as usize].clone())
                .collect(),
        );
        (cache_header(60), resp.into_response())
    } else {
        (
            HeaderMap::new(),
            (StatusCode::NOT_FOUND, "no such entity").into_response(),
        )
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

fn get_arr_base(res: &SearchResult) -> [f64; 2] {
    [
        f64::from(max(res.citations, 1)).ln(),
        f64::from(res.citations) / f64::from(max(res.papers, 3)),
    ]
}

fn get_query_arr(res: &SearchResult, state: &NameState) -> [f64; 2] {
    let mut rec = get_arr_base(res);
    for i in 0..rec.len() {
        rec[i] -= state.means[i];
        rec[i] /= state.vars[i].sqrt();
    }
    rec
}

fn static_router<O: Serialize>(o: &O) -> Router {
    let arc: Arc<str> = Arc::from(serde_json::to_string(o).unwrap().as_str());
    Router::new().route("/", get(state_get)).with_state(arc)
}

fn parse_semantic_id(id: String) -> String {
    id.replace("%2F", "/")
}

fn tree_from_iter(v: Vec<[f64; 2]>) -> KdTree<KDItem> {
    KdTree::build_by_ordered_float(
        v.into_iter()
            .enumerate()
            .map(|(id, point)| KDItem { id, point })
            .collect(),
    )
}
