use core::panic;
use std::{
    collections::VecDeque,
    fmt::Display,
    marker::PhantomData,
    panic::{catch_unwind, AssertUnwindSafe},
    path::PathBuf,
    sync::{Arc, Mutex},
    thread::JoinHandle,
    vec,
};

use dmove_macro::impl_subs;
use hashbrown::HashMap;
use serde::{Deserialize, Serialize};

use rankless_rs::{
    env_consts::START_YEAR,
    gen::{a1_entity_mapping::Works, a2_init_atts::WorksNames},
    steps::{
        a1_entity_mapping::{POSSIBLE_YEAR_FILTERS, YBT},
        derive_links1::WorkPeriods,
    },
};

use dmove::{
    para::AcTuple, BigId, Entity, NamespacedEntity, VarSizedAttributeElement, VattReadingArcMap, ET,
};

use crate::{
    instances::TreeGetter,
    interfacing::{Getters, LocatorsFromMemory},
    part_iterator::TreeMakingParams,
    AttributeLabelUnion,
};

const MAX_QUEUE_LEN: usize = 2048;

pub type WT = ET<Works>;
pub type WorkCiteT = u32;

pub type TreeSpecMap = HashMap<String, Vec<TreeSpec>>;
pub type AttributeLabels = HashMap<String, HashMap<usize, AttributeLabelOut>>;
pub type EntityAttsForLinks = HashMap<String, HashMap<usize, AttributeLabel>>;
pub type CollapsedNode = CollapsedNodeGen<WT>;
pub type CollapsedNodeJson = CollapsedNodeGen<Option<BigId>>;
pub type InProgressMap = HashMap<CacheKey, BoolCvp>;
pub type ManFileHandle = VattReadingArcMap<WorksNames>;

pub type ResCvp = AcTuple<Option<AnyResponse>>;
pub type BoolCvp = AcTuple<Option<()>>;
type BasisQuElem = (Option<AnyQuery>, ResCvp);
type BasisCvp = AcTuple<VecDeque<BasisQuElem>>;

pub struct TreeBasisState {
    pub gets: Getters,
    pub att_union: Arc<AttributeLabelUnion>,
    pub in_progress: Mutex<InProgressMap>,
}

pub struct TreeRunManager<T> {
    pub state: Arc<TreeBasisState>,
    pub specs: TreeSpecs,
    thread_pool: Vec<JoinHandle<()>>,
    cv_pair: BasisCvp,
    p: PhantomData<T>,
}

#[derive(Eq, Hash, PartialEq, Clone)]
pub struct CacheKey {
    pub etype: u8,
    pub eid: usize,
    pub tid: u8,
}

#[derive(Clone)]
pub struct FullTreeQuery {
    pub q: TreeQ,
    pub ck: CacheKey,
    pub period: u8,
    pub name: String,
}

#[derive(Clone)]
pub struct FullMultiTreeQuery {
    pub sq: ShallowQ,
    pub act_fq: FullTreeQuery,
    pub act_ind: usize,
}

#[derive(Clone, Copy, Default)]
pub struct WorkWInd(pub WT, pub WorkCiteT);

#[derive(Serialize, Clone)]
pub struct AttributeLabel {
    pub name: Arc<str>,
    pub semantic_id: Arc<str>,
    pub spec_baseline: f64,
}

#[derive(Serialize, Clone)]
pub struct AttributeLabelOut {
    pub name: String,
    #[serde(rename = "specBaseline")]
    pub spec_baseline: f64,
    #[serde(skip_serializing_if = "Option::is_none", rename = "oaId")]
    pub oa_id: Option<BigId>,
}

#[derive(Deserialize, Clone)]
pub struct TreeQ {
    pub year: Option<u16>,
    pub tid: Option<u8>,
    pub connections: Option<String>,
    pub big_prep: Option<bool>,
    pub big_read: Option<bool>,
    pub shallow: Option<u8>,
    pub wide: Option<bool>,
    pub cacheable: Option<bool>,
}

#[derive(Deserialize, Clone)]
pub struct ShallowQ {
    pub ids: Vec<usize>,
    pub year: Option<u16>,
    pub tid: Option<u8>,
    pub filter: Option<Vec<usize>>,
    pub satts: Option<bool>,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, Default)]
pub struct CollapsedNodeGen<T: Default> {
    #[serde(rename = "linkCount")]
    pub link_count: u32,
    #[serde(rename = "sourceCount")]
    pub source_count: u32,
    #[serde(rename = "topSourceId")]
    pub top_source: T,
    #[serde(rename = "topSourceLinks")]
    pub top_cite_count: u32,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct BufSerTree {
    pub node: CollapsedNode,
    pub children: Box<BufSerChildren>,
}

#[derive(Serialize, Clone)]
pub struct JsSerTree {
    #[serde(flatten)]
    pub node: CollapsedNodeJson,
    pub children: Box<JsSerChildren>,
}

#[derive(Serialize)]
pub struct TreeResponse {
    pub tree: JsSerTree,
    pub atts: AttributeLabels,
    pub shallowed: bool,
}

#[derive(Serialize)]
pub struct ShallowTreesResponse {
    pub trees: HashMap<usize, JsSerTree>,
    pub atts: AttributeLabels,
}

#[derive(Serialize)]
pub struct TreeSpecs {
    #[serde(skip_serializing)]
    root_types: Vec<String>,
    specs: TreeSpecMap,
    #[serde(rename = "yearBreaks")]
    year_breaks: YBT,
}

#[derive(Serialize)]
pub struct TreeSpec {
    #[serde(rename = "rootType")]
    pub root_type: String,
    pub breakdowns: Vec<BreakdownSpec>,
    #[serde(rename = "defaultIsSpec")]
    pub is_spec: bool,
    #[serde(rename = "allowSpec")]
    pub allow_spec: bool,
    #[serde(rename = "defaultYear")]
    pub default_partition: u16,
}

#[derive(Serialize)]
pub struct BreakdownSpec {
    #[serde(rename = "attributeType")]
    pub attribute_type: String,
    #[serde(rename = "specDenomInd")] //this is to know how deep to go back for spec calculation
    //e.g a country->inst is the same resolver
    pub spec_denom_ind: u8,
    // description: String, // used to be for spec calculation -> separate for different kinds of
    // breakdowns
    #[serde(rename = "sourceSide")]
    pub source_side: bool,
}

pub struct SCIter<'a> {
    children: &'a BufSerChildren,
    key_iter: vec::IntoIter<&'a u32>,
}

pub enum AnyQuery {
    Single(FullTreeQuery),
    Shallows(FullMultiTreeQuery),
}

pub enum AnyResponse {
    Single(TreeResponse),
    Shallows(ShallowTreesResponse),
    Failed,
}

#[derive(Serialize, Deserialize, Clone)]
pub enum BufSerChildren {
    Leaves(HashMap<u32, CollapsedNode>),
    Nodes(HashMap<u32, BufSerTree>),
}

#[derive(Serialize, Clone)]
#[serde(untagged)]
pub enum JsSerChildren {
    Leaves(HashMap<u32, CollapsedNodeJson>),
    Nodes(HashMap<u32, JsSerTree>),
}

impl PartialEq for WorkWInd {
    fn eq(&self, other: &Self) -> bool {
        self.0.eq(&other.0)
    }
}

impl PartialOrd for WorkWInd {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        self.0.partial_cmp(&other.0)
    }
}

impl<'a> Iterator for SCIter<'a> {
    type Item = (&'a u32, &'a CollapsedNode);
    fn next(&mut self) -> Option<Self::Item> {
        match self.key_iter.next() {
            Some(k) => {
                let v = match self.children {
                    BufSerChildren::Nodes(nodes) => &nodes[k].node,
                    BufSerChildren::Leaves(leaves) => &leaves[k],
                };
                Some((k, v))
            }
            None => None,
        }
    }
}

impl Display for FullTreeQuery {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "{}({}:{}/{:?})",
            self.name, self.ck.eid, self.ck.tid, self.q.year
        )
    }
}

impl TreeResponse {
    pub fn empty() -> Self {
        Self {
            tree: JsSerTree {
                node: CollapsedNodeGen::default(),
                children: JsSerChildren::Leaves(HashMap::new()).into(),
            },
            atts: HashMap::new(),
            shallowed: false,
        }
    }
}

impl TreeSpecs {
    pub fn new(spec_kvs: Vec<(String, Vec<TreeSpec>)>) -> Self {
        let root_types = spec_kvs.iter().map(|e| e.0.clone()).collect();
        let specs = HashMap::from_iter(spec_kvs.into_iter());
        Self {
            root_types,
            specs,
            year_breaks: POSSIBLE_YEAR_FILTERS,
        }
    }

    pub fn to_eid(&self, name: &String) -> Option<u8> {
        for (i, e) in self.root_types.iter().enumerate() {
            if name == e {
                return Some(i as u8);
            }
        }
        None
    }

    pub fn to_ck(&self, tid: u8, root_type: &String, eid: usize) -> Option<CacheKey> {
        let etype = self.to_eid(root_type)?;
        // Reject out-of-range tids: the generated `run_params` dispatch has no fallback arm.
        // eids are the handlers' responsibility: raw input is validated at the HTTP boundary
        if (tid as usize) >= self.specs.get(root_type)?.len() {
            return None;
        }
        Some(CacheKey { etype, tid, eid })
    }
}

impl CollapsedNode {
    pub fn ingest_disjunct(&mut self, o: &Self) {
        if o.top_cite_count > self.top_cite_count {
            self.top_source = o.top_source;
            self.top_cite_count = o.top_cite_count;
        }
        self.link_count += o.link_count;
        self.source_count += o.source_count;
    }

    pub fn update_with_wt(&mut self, wwind: &WorkWInd) {
        let ul = wwind.1;
        if ul > self.top_cite_count {
            self.top_source = wwind.0;
            self.top_cite_count = ul;
        }
        self.link_count += ul;
        self.source_count += 1;
    }
}

impl BufSerTree {
    pub fn ingest_disjunct(&mut self, other: Self) {
        use BufSerChildren::*;
        self.node.ingest_disjunct(&other.node);
        match self.children.as_mut() {
            Nodes(nodes) => match *other.children {
                Nodes(other_nodes) => {
                    for (ok, ov) in other_nodes {
                        match nodes.get_mut(&ok) {
                            Some(my_v) => my_v.ingest_disjunct(ov),
                            None => {
                                nodes.insert(ok, ov);
                            }
                        }
                    }
                }
                Leaves(_) => panic!("non matching trees"),
            },
            Leaves(leaves) => match *other.children {
                Leaves(other_leaves) => {
                    for (ok, ov) in other_leaves {
                        match leaves.get_mut(&ok) {
                            Some(my_v) => my_v.ingest_disjunct(&ov),
                            None => {
                                leaves.insert(ok, ov);
                            }
                        }
                    }
                }
                Nodes(_) => panic!("non matching trees"),
            },
        }
    }
}

impl BufSerChildren {
    pub fn iter_items<'a>(&'a self) -> SCIter<'a> {
        SCIter {
            children: self,
            key_iter: self.keys().into_iter(),
        }
    }

    pub fn len(&self) -> usize {
        match self {
            Self::Nodes(nodes) => nodes.len(),
            Self::Leaves(ls) => ls.len(),
        }
    }

    pub fn keys(&self) -> Vec<&u32> {
        match self {
            Self::Nodes(nodes) => nodes.keys().collect(),
            Self::Leaves(ls) => ls.keys().collect(),
        }
    }

    pub fn get_strict(&self, k: &u32) -> CollapsedNode {
        match self {
            Self::Nodes(nodes) => nodes[k].node.clone(),
            Self::Leaves(ls) => ls[k].clone(),
        }
    }
}

impl JsSerTree {
    pub fn from_buf(value: BufSerTree, gets: &Getters) -> Self {
        let children = JsSerChildren::from_buf(*value.children, gets);
        Self {
            node: oaify(value.node, gets),
            children: Box::new(children),
        }
    }
}

impl JsSerChildren {
    fn from_buf(value: BufSerChildren, gets: &Getters) -> Self {
        //TODO: this is wasteful
        match value {
            BufSerChildren::Nodes(nodes) => Self::Nodes(HashMap::from_iter(
                nodes
                    .into_iter()
                    .map(|(k, v)| (k, JsSerTree::from_buf(v, gets))),
            )),
            BufSerChildren::Leaves(leaves) => Self::Leaves(HashMap::from_iter(
                leaves.into_iter().map(|(k, v)| (k, oaify(v, gets))),
            )),
        }
    }
}

pub trait RunManagerSub {
    fn run_params(params: TreeMakingParams);
    fn get_specs() -> TreeSpecs;
}

// make this a derive trait for some struct
impl_subs!(6);
impl_subs!(2);

impl<T> TreeRunManager<T>
where
    T: RunManagerSub,
{
    pub fn new(gets: Arc<Getters>, atts: Arc<AttributeLabelUnion>, n: usize) -> Arc<Self> {
        let state = TreeBasisState::new(Arc::into_inner(gets).expect("gets for state"), atts);

        Arc::new(
            Self {
                state: Arc::new(state),
                thread_pool: Vec::new(),
                specs: T::get_specs(),
                cv_pair: BasisCvp::default(),
                p: PhantomData,
            }
            .fill_thread_pool(n),
        )
    }

    pub fn get_single_resp(
        &self,
        q: TreeQ,
        root_type: &String,
        eid: usize,
    ) -> Option<TreeResponse> {
        let fq = make_fq(q, eid, root_type, &self.specs)?;
        let aq = AnyQuery::Single(fq);
        match self.get_resp(aq)? {
            AnyResponse::Single(resp) => Some(resp),
            _ => None,
        }
    }

    pub fn get_shallows(&self, sq: ShallowQ, root_type: &String) -> Option<ShallowTreesResponse> {
        //TODO: this is incomplete
        let tq = TreeQ {
            year: sq.year,
            tid: sq.tid,
            connections: None,
            big_prep: None,
            big_read: None,
            shallow: Some(0),
            cacheable: None,
            wide: None,
        };
        let act_fq = make_fq(tq, *sq.ids.get(0)?, root_type, &self.specs)?;
        let fmq = FullMultiTreeQuery {
            act_fq,
            sq,
            act_ind: 0,
        };
        let aq = AnyQuery::Shallows(fmq);
        match self.get_resp(aq)? {
            AnyResponse::Shallows(resp) => Some(resp),
            _ => None,
        }
    }

    fn get_resp(&self, aq: AnyQuery) -> Option<AnyResponse> {
        let res_cvp = ResCvp::default();
        if !self.add_to_queue(Some(aq), res_cvp.clone()) {
            println!("queue full, rejecting query");
            return None;
        }
        let (lock, cvar) = &*res_cvp;
        let mut out = lock.lock().unwrap();
        while out.is_none() {
            out = cvar.wait(out).unwrap();
        }
        match out.take() {
            Some(AnyResponse::Failed) | None => None,
            resp => resp,
        }
    }

    pub fn join(self) {
        for _ in 0..self.thread_pool.len() {
            self.add_to_queue(None, ResCvp::default());
        }
        for t in self.thread_pool.into_iter() {
            t.join().unwrap();
        }
    }

    pub fn fake() -> Arc<Self> {
        let gets = Getters::fake();
        let atts = HashMap::new();
        Self::new(Arc::new(gets), atts.into(), 2)
    }

    pub fn get_file_handle<E>(&self) -> VattReadingArcMap<E>
    where
        E: NamespacedEntity,
        E: LocatorsFromMemory,
        ET<E>: VarSizedAttributeElement,
    {
        let parent = self
            .state
            .gets
            .stowage
            .path_from_ns(<E as NamespacedEntity>::NS);
        VattReadingArcMap::<E>::from_locator(
            <E as LocatorsFromMemory>::locs_from_ram(&self.state.gets),
            &parent,
        )
    }

    fn add_to_queue(&self, aq: Option<AnyQuery>, res_cvp: ResCvp) -> bool {
        let (lock, cvar) = &*self.cv_pair;
        let mut data = lock.lock().unwrap();
        // the kill sentinel (None) must always get through
        if aq.is_some() && data.len() >= MAX_QUEUE_LEN {
            return false;
        }
        data.push_back((aq, res_cvp));
        cvar.notify_all();
        true
    }

    fn fill_thread_pool(mut self, n: usize) -> Self {
        for i in 0..n {
            let shared_cvp = self.cv_pair.clone();
            let shared_state = self.state.clone();
            let mut thread_fh = self.get_file_handle();
            let thread = std::thread::spawn(move || loop {
                let (fqo, res_cvp) = Self::get_q_cvp(shared_cvp.clone());
                match fqo {
                    Some(aq) => {
                        let panic_cvp = res_cvp.clone();
                        let run = catch_unwind(AssertUnwindSafe(|| {
                            let params =
                                TreeMakingParams::new(&shared_state, &mut thread_fh, aq, res_cvp);
                            T::run_params(params);
                        }));
                        if run.is_err() {
                            println!("tree compute panicked on worker {i}");
                            let (lock, cvar) = &*panic_cvp;
                            let mut out = lock.lock().unwrap();
                            if out.is_none() {
                                *out = Some(AnyResponse::Failed);
                                cvar.notify_all();
                            }
                        }
                    }
                    None => {
                        println!("killing worker thread {i}");
                        break;
                    }
                }
            });
            self.thread_pool.push(thread);
        }
        self
    }

    fn get_q_cvp(shared_cvp: BasisCvp) -> BasisQuElem {
        let (lock, cvar) = &*shared_cvp;
        let mut data = lock.lock().unwrap();
        while data.len() == 0 {
            data = cvar.wait(data).unwrap();
        }
        return data.pop_front().unwrap();
    }
}

impl TreeBasisState {
    pub fn new(gets: Getters, att_union: Arc<AttributeLabelUnion>) -> Self {
        Self {
            gets,
            att_union,
            in_progress: Mutex::new(HashMap::new()),
        }
    }

    pub fn full_cache_file_period(&self, fq: &FullTreeQuery, period: u8) -> PathBuf {
        self.cache_file(fq, period, Some("full"))
    }

    pub fn wide_cache_file_period(&self, fq: &FullTreeQuery, period: u8) -> PathBuf {
        self.cache_file(fq, period, Some("wide"))
    }

    pub fn pruned_cache_file_period(&self, fq: &FullTreeQuery, period: u8) -> PathBuf {
        self.cache_file(fq, period, None)
    }

    fn cache_file(&self, fq: &FullTreeQuery, period: u8, prefix: Option<&str>) -> PathBuf {
        let name = match prefix {
            Some(p) => format!("{}-{}.zst", p, period),
            None => format!("{}.zst", period),
        };
        self.cache_dir(fq).join(name)
    }

    pub fn resp_cache_file(&self, fq: &FullTreeQuery) -> PathBuf {
        if fq.q.wide.unwrap_or(false) {
            self.wide_cache_file_period(fq, fq.period)
        } else {
            self.pruned_cache_file_period(fq, fq.period)
        }
    }

    pub fn fake() -> Self {
        Self {
            in_progress: Mutex::new(HashMap::new()),
            gets: Getters::fake(),
            att_union: Arc::new(HashMap::new()),
        }
    }

    fn cache_dir(&self, fq: &FullTreeQuery) -> PathBuf {
        self.gets
            .stowage
            .paths
            .cache
            .join(&fq.name)
            .join(fq.ck.eid.to_string())
            .join(fq.ck.tid.to_string())
    }
}

fn make_fq(q: TreeQ, eid: usize, root_type: &String, specs: &TreeSpecs) -> Option<FullTreeQuery> {
    let fq = FullTreeQuery {
        ck: specs.to_ck(q.tid.unwrap_or(0), root_type, eid)?,
        period: WorkPeriods::from_year(q.year.unwrap_or(START_YEAR)),
        q,
        name: root_type.to_string(),
    };
    Some(fq)
}

fn oaify(node: CollapsedNode, gets: &Getters) -> CollapsedNodeJson {
    CollapsedNodeGen {
        top_source: gets.work_oa.get(node.top_source as usize).copied(),
        link_count: node.link_count,
        source_count: node.source_count,
        top_cite_count: node.top_cite_count,
    }
}
