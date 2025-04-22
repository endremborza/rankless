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
    para::{set_and_notify, AcTuple},
    Entity, InitEmpty, NamespacedEntity, UnsignedNumber, ET,
};
use hashbrown::HashMap;
use kd_tree::{KdPoint, KdTree};
use rand::seq::SliceRandom;
use serde::{Deserialize, Serialize};
use socket2::{Domain, Socket, Type};
use std::{
    cmp::{max, min},
    net::SocketAddr,
    sync::{Arc, Mutex},
    thread::{sleep, JoinHandle},
    time,
};
use tokio::net::TcpListener;

use muwo_search::SearchEngine;
use rankless_rs::{
    common::{MainEntity, NET},
    gen::a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics},
    steps::{
        a1_entity_mapping::{Qs, RawYear, YearInterface, Years},
        derive_links5::{EraRec, InstRelation},
    },
    Stowage,
};
use rankless_trees::{
    interfacing::{Getters, NodeInterfaces, RootInterfaceable, RootInterfaces},
    io::{TreeQ, TreeResponse, TreeRunManager},
    AttributeLabelUnion,
};

const PORT: u16 = 3038;
const CACHEABLE_FROM: u32 = 10_000;
const N_THREADS: usize = 16;
const UPPER_LIMIT: u32 = u32::MAX;
const ETYPE_ENC: [&str; 6] = [
    Institutions::NAME,
    Authors::NAME,
    Subfields::NAME,
    Countries::NAME,
    Sources::NAME,
    Topics::NAME,
];

type InstTrm = TreeRunManager<(Institutions, Authors, Subfields, Countries, Sources)>;
type Coords = [f64; 2];
type NameStateMap = HashMap<&'static str, NameState>;

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
    engine: SearchEngine,
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
struct InstRelOut {
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
    pub prime_relations: Vec<PostAttRelatedEntity>,
}

struct PreAttResultExtension {
    pub prime_relations: Box<[PreAttRelatedEntity]>,
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
        entif: &RootInterfaces<E>,
    ) -> Self
    where
        E: RootInterfaceable,
    {
        Self {
            full_name: format!("{name} {ext}").trim().to_string(),
            name,
            semantic_id,
            papers: entif.wcounts[i].to_usize() as u32,
            citations: entif.ccounts[i].to_usize() as u32,
            oa_id: entif.oa_id[i],
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
            for (yi, ycount) in entif.yearly_papers[i].iter().enumerate() {
                if (sy_ind == 0) & (*ycount > 0) {
                    sy_ind = yi;
                    break;
                }
            }
            // let get_rem = |arr: &Box<[EraRec]>| arr[i].iter().skip(sy_ind).map(|e| *e).collect();
            // let yearly_cites = get_rem(&entif.yearly_cites);
            // let yearly_papers = get_rem(&entif.yearly_papers);

            out.push(Self {
                start_year: YearInterface::reverse(sy_ind as ET<Years>),
                yearly_cites: entif.yearly_cites[i].clone(),
                yearly_papers: entif.yearly_papers[i].clone(),
            })
        }

        out.into()
    }
}

impl PreAttResultExtension {
    fn from_resps<E>(responses: &Box<[SearchResult]>, entif: &RootInterfaces<E>) -> Box<[Self]>
    where
        E: RootInterfaceable,
    {
        responses
            .iter()
            .map(|res| {
                let i = res.dm_id;
                let mut prime_relations = Vec::new();
                add_to_relations::<Subfields, _>(&entif.top_paper_sfc[i], &mut prime_relations, 0);
                add_to_relations::<Subfields, _>(&entif.top_citing_sfc[i], &mut prime_relations, 1);
                add_to_relations::<Topics, _>(&entif.top_paper_topic[i], &mut prime_relations, 2);
                add_to_relations::<Countries, _>(
                    &entif.top_aff_countries[i],
                    &mut prime_relations,
                    3,
                );
                add_to_relations::<Sources, _>(&entif.top_journals[i], &mut prime_relations, 4);
                add_to_relations::<Authors, _>(&entif.top_authors[i], &mut prime_relations, 5);
                Self {
                    prime_relations: prime_relations.into(),
                }
            })
            .collect()
    }

    fn to_post(
        &self,
        satts: &AttributeLabelUnion,
        nstates: &Arc<NameStateMap>,
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
        PostAttResultExtension { prime_relations }
    }
}

fn add_to_relations<RE, T>(arr: &[(u32, T)], prels: &mut Vec<PreAttRelatedEntity>, rel_type: u8)
where
    RE: Entity,
    T: UnsignedNumber,
{
    arr.iter().for_each(|e| {
        let eu = e.1.to_usize() as u32;
        let etype_id = ETYPE_ENC
            .iter()
            .enumerate()
            .filter(|e| *e.1 == RE::NAME)
            .next()
            .unwrap()
            .0 as u8;
        if eu != 0 {
            prels.push(PreAttRelatedEntity {
                rel_type,
                dm_id: eu,
                etype_id,
                score: e.0,
            })
        }
    });
}

impl NameState {
    fn new<E>(entif: &RootInterfaces<E>, gets: &Getters) -> Self
    where
        E: RootInterfaceable + PrepFilter,
    {
        let responses = Self::get_resps(entif, gets);
        let engine = SearchEngine::new(responses.iter().map(|e| e.full_name.clone()));
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
            prep_exts: PreAttResultExtension::from_resps(&responses, entif),
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
        E: RootInterfaceable + PrepFilter,
    {
        let mut responses: Vec<SearchResult> = entif
            .names
            .0
            .iter()
            .zip(entif.name_exts.0.iter())
            .zip(entif.sem_ids.0.iter())
            .enumerate()
            .map(|(i, ((name, ext), semantic_id))| {
                SearchResult::new(
                    i,
                    name.to_string(),
                    ext.to_string(),
                    semantic_id.to_string(),
                    entif,
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

impl InstRelOut {
    fn from(v: &InstRelation, iif: &RootInterfaces<Institutions>, gets: &Getters) -> Self {
        let iid = v.inst.to_usize();
        let inst_name = iif.names.0.get(iid).unwrap().clone();
        let mut inst_sem_id = iif.sem_ids.0.get(iid).unwrap().clone();

        let i_sr = SearchResult::new(
            iid,
            inst_name.to_string(),
            "".to_string(),
            inst_sem_id.to_string(),
            iif,
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
    let static_att_union: Arc<Mutex<AttributeLabelUnion>> = Arc::new(Mutex::new(HashMap::new()));
    let mut ei_ns_map = HashMap::new();
    let cv_pair = AcTuple::<Option<f64>>::init_empty();

    //TODO: make this a macro
    add_thread::<Institutions>(&gets, &static_att_union, &cv_pair, &mut ei_ns_map);
    add_thread::<Authors>(&gets, &static_att_union, &cv_pair, &mut ei_ns_map);
    add_thread::<Subfields>(&gets, &static_att_union, &cv_pair, &mut ei_ns_map);
    add_thread::<Countries>(&gets, &static_att_union, &cv_pair, &mut ei_ns_map);
    add_thread::<Sources>(&gets, &static_att_union, &cv_pair, &mut ei_ns_map);

    let ccount = gets.total_cite_count();
    set_and_notify(cv_pair, Some(ccount));
    NodeInterfaces::<Topics>::new(&gets.stowage)
        .update_stats(&mut static_att_union.lock().unwrap(), ccount);
    NodeInterfaces::<Qs>::new(&gets.stowage)
        .update_stats(&mut static_att_union.lock().unwrap(), ccount);

    let mut ns_map: NameStateMap = HashMap::new();
    let mut tops = Vec::new();
    let mut descriptions = Vec::new();

    for (name, handle) in ei_ns_map.into_iter() {
        let (nstate, tr, ed) = handle.join().expect(&format!("{name} state thread"));
        tops.push(tr);
        descriptions.push(ed);
        ns_map.insert(name, nstate);
    }
    let satts = Arc::new(
        Arc::into_inner(static_att_union)
            .unwrap()
            .into_inner()
            .unwrap(),
    );
    let tm: Arc<InstTrm> = TreeRunManager::new(gets, satts.clone(), N_THREADS);
    (ns_map, satts, tm, descriptions, tops)
}

fn wait_for_data<T>(cvp: AcTuple<Option<T>>) -> T
where
    T: Copy,
{
    let (lock, cvar) = &*cvp;
    let mut data = lock.lock().unwrap();
    while data.is_none() {
        data = cvar.wait(data).unwrap();
    }
    *data.as_ref().unwrap()
}

fn add_thread<E>(
    gets: &Arc<Getters>,
    atts: &Arc<Mutex<AttributeLabelUnion>>,
    cv_pair: &AcTuple<Option<f64>>,
    ei_ns_map: &mut HashMap<&'static str, JoinHandle<(NameState, TopResult, EntityDescription)>>,
) where
    E: RootInterfaceable + PrepFilter + MainEntity + NamespacedEntity,
{
    let gets_clone = Arc::clone(gets);
    let au_clone = Arc::clone(atts);
    let shared_cvp = Arc::clone(cv_pair);
    let thread = std::thread::spawn(move || {
        let name = E::NAME.to_string();
        let ent_intf = RootInterfaces::<E>::new(&gets_clone.stowage);
        let nstate = NameState::new::<E>(&ent_intf, &gets_clone);
        let ccount = wait_for_data(shared_cvp);
        ent_intf.update_stats(&mut au_clone.lock().unwrap(), ccount);
        let entities = nstate
            .responses
            .iter()
            .filter(|e| <E as PrepFilter>::is_top(e))
            .map(|e| e.clone())
            .collect();
        let tr = TopResult { name, entities };
        let ed = EntityDescription::new::<E>(nstate.responses.len());
        (nstate, tr, ed)
    });
    ei_ns_map.insert(<E>::NAME, thread);
}

#[tokio::main(worker_threads = 16)]
async fn main() {
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
        .with_state((ns_map_arc.clone(), satts.clone()));

    let count_api = static_router(&entity_descriptions);
    let specs_api = static_router(&tree_manager.specs);

    let tops_api = Router::new()
        .route("/", get(tops_get))
        .with_state(Arc::new(tops));

    let tree_api = Router::new()
        .route("/:root_type/:semantic_id", get(tree_get))
        .with_state((tree_manager.clone(), ns_map_arc.clone()));

    let api = Router::new()
        .nest("/", response_api)
        .nest("/trees", tree_api)
        .nest("/counts", count_api)
        .nest("/specs", specs_api)
        .nest("/tops", tops_api);

    let app = Router::new().nest("/v1", api);

    let loc_addr = SocketAddr::from(([127, 0, 0, 1], PORT));
    println!("{loc_addr} set-up in {} ttcpl", now.elapsed().as_secs());

    let socket = Socket::new(Domain::IPV4, Type::STREAM, None).unwrap();
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
    axum::serve(listener, app.clone().into_make_service())
        .tcp_nodelay(true)
        .await
        .unwrap()
}

async fn slice_get(
    Path((etype, pstart, pend)): Path<(String, usize, usize)>,
    states: State<(Arc<NameStateMap>, Arc<AttributeLabelUnion>)>,
) -> Response<Body> {
    const MAX_SLICE: usize = 1000;
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
    states: State<(Arc<InstTrm>, Arc<NameStateMap>)>,
) -> (HeaderMap, Json<Option<TreeResponse>>) {
    let mut tq = tree_q.0;
    let (tm, ns_map) = states.0;
    if let Some(nstate) = ns_map.get(root_type.as_str()) {
        if let Some(sval) = nstate.semantic_id_map.get(&semantic_id) {
            let ncite = nstate.responses[sval.result_id].citations;
            tq.cacheable = Some(ncite >= CACHEABLE_FROM);
            let resp = Json(tm.get_resp(tq, &root_type, sval.dm_id));
            return (cache_header(60), resp);
        }
    }
    (cache_header(0), None.into())
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
    states: State<(Arc<NameStateMap>, Arc<AttributeLabelUnion>)>,
) -> Json<Option<ViewResult>> {
    let satts = states.0 .1;
    let mut out = None;
    if let Some(state) = states.0 .0.get(etype.as_str()) {
        if let Some(sem_val) = state.semantic_id_map.get(&semantic_id) {
            let i = sem_val.result_id;
            let srs = &state.responses[i];
            let ext = &state.exts[i];
            let query = get_query_arr(&srs, &state);
            let n_close = min(state.responses.len() / 20, 500);
            let mut closes = state.query_tree.nearests(&query, n_close);
            closes.shuffle(&mut rand::thread_rng());
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
                prep_ext: state.prep_exts[i].to_post(&satts, &states.0 .0),
            };
            out = Some(vr)
        };
    }
    Json(out)
}

async fn sem_id_get(
    Path((etype, oa_id)): Path<(String, usize)>,
    states: State<(Arc<NameStateMap>, Arc<AttributeLabelUnion>)>,
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
    states: State<(Arc<NameStateMap>, Arc<AttributeLabelUnion>)>,
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

fn tree_from_iter(v: Vec<[f64; 2]>) -> KdTree<KDItem> {
    KdTree::build_by_ordered_float(
        v.into_iter()
            .enumerate()
            .map(|(id, point)| KDItem { id, point })
            .collect(),
    )
}
