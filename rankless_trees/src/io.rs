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
    metrics::Level,
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
    prune::MAX_WIDE,
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
type BasisQuElem = (Option<FullTreeQuery>, ResCvp);
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

// A resolved query: the tree (`ck`), what its first level profiles, the since-period, and what to
// do with it. `cacheable` is the caller's call — the handler knows the entity's citation count.
#[derive(Clone)]
pub struct FullTreeQuery {
    pub ck: CacheKey,
    pub level: Level,
    pub period: u8,
    pub name: String,
    pub cacheable: bool,
    pub command: Command,
}

// A tree's first level as a profile of the root: its links over one attribute entity. `complete`
// says whether every entity with links is present or the level is a top-`MAX_WIDE` cut.
pub struct FirstLevel {
    pub node: CollapsedNode,
    pub leaves: HashMap<u32, CollapsedNode>,
    pub complete: bool,
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

// The HTTP query of `/trees`; `make_fq` folds its flags into a `Command`.
#[derive(Deserialize, Clone)]
pub struct TreeQ {
    pub year: Option<u16>,
    pub tid: Option<u8>,
    pub big_prep: Option<bool>,
    pub big_read: Option<bool>,
    pub shallow: Option<u8>,
    pub wide: Option<bool>,
    pub cacheable: Option<bool>,
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
    #[serde(flatten)]
    pub level: Level,
    // How many levels up the specialization denominator sits: a country -> institution level
    // shares its parent's resolver.
    #[serde(rename = "specDenomInd")]
    pub spec_denom_ind: u8,
    #[serde(skip)]
    pub n_entities: usize,
}

pub struct SCIter<'a> {
    children: &'a BufSerChildren,
    key_iter: vec::IntoIter<&'a u32>,
}

// What a query asks of the tree: a served shape, or one of the two disk-staged compute commands
// of the cache warmer, which never serve from cache.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Command {
    Serve(Serve),
    BigPrep,
    BigRead,
}

// `Pruned` is the tree the FE explores, top children per level, cut to `shallow` levels when it
// is big; `Wide` is the first level with labels (flat-out, tiles); `Profile` is the first level raw.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Serve {
    Pruned { shallow: Option<u8> },
    Wide,
    Profile,
}

pub enum AnyResponse {
    Tree(TreeResponse),
    Profile(FirstLevel),
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
            "{}({}:{}/p{} {:?})",
            self.name, self.ck.eid, self.ck.tid, self.period, self.command
        )
    }
}

impl FullTreeQuery {
    pub fn serve(&self) -> Option<Serve> {
        match self.command {
            Command::Serve(s) => Some(s),
            _ => None,
        }
    }
}

impl FirstLevel {
    pub fn from_wide(tree: BufSerTree, n_entities: usize) -> Self {
        let leaves = match *tree.children {
            BufSerChildren::Leaves(leaves) => leaves,
            BufSerChildren::Nodes(_) => panic!("a profile is one level deep"),
        };
        // A cut level keeps at least MAX_WIDE keys, so fewer means nothing was cut.
        let complete = leaves.len() < MAX_WIDE || n_entities <= MAX_WIDE;
        Self {
            node: tree.node,
            leaves,
            complete,
        }
    }

    // The leaf's share of the root's links; zero is only asserted for a complete level, an absent
    // leaf of a cut level is unknown, as is any share of a root without links.
    pub fn share(&self, key: u32) -> Option<f64> {
        if self.node.link_count == 0 {
            return None;
        }
        let total = self.node.link_count as f64;
        match self.leaves.get(&key) {
            Some(leaf) => Some(leaf.link_count as f64 / total),
            None if self.complete => Some(0.0),
            None => None,
        }
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

    pub fn first_level(&self, root_type: &str, tid: u8) -> Option<&BreakdownSpec> {
        self.specs
            .get(root_type)?
            .get(tid as usize)?
            .breakdowns
            .first()
    }

    pub fn has_level(&self, root_type: &str, level: Level) -> bool {
        self.profile_tid(root_type, level).is_some()
    }

    // The tree that yields a level's profile cheapest: the fewest levels, the lowest id on a tie.
    pub fn profile_tid(&self, root_type: &str, level: Level) -> Option<u8> {
        self.specs
            .get(root_type)?
            .iter()
            .enumerate()
            .filter(|(_, spec)| spec.breakdowns.first().is_some_and(|b| b.level == level))
            .min_by_key(|(_, spec)| spec.breakdowns.len())
            .map(|(i, _)| i as u8)
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
        match Self::wait(self.enqueue(fq)?)? {
            AnyResponse::Tree(resp) => Some(resp),
            _ => None,
        }
    }

    // One profile per entity, each its own pool job, gathered once all are in. Entities the pool
    // rejects or whose compute fails are absent. Empty when no tree of the root yields the level.
    pub fn first_levels(
        &self,
        root_type: &str,
        level: Level,
        year: Option<u16>,
        ids: impl IntoIterator<Item = (usize, bool)>,
    ) -> HashMap<usize, FirstLevel> {
        let Some(tid) = self.specs.profile_tid(root_type, level) else {
            return HashMap::new();
        };
        let pending: Vec<(usize, ResCvp)> = ids
            .into_iter()
            .filter_map(|(eid, cacheable)| {
                let fq = FullTreeQuery {
                    ck: self.specs.to_ck(tid, &root_type.to_string(), eid)?,
                    level,
                    period: WorkPeriods::from_year(year.unwrap_or(START_YEAR)),
                    name: root_type.to_string(),
                    cacheable,
                    command: Command::Serve(Serve::Profile),
                };
                Some((eid, self.enqueue(fq)?))
            })
            .collect();
        pending
            .into_iter()
            .filter_map(|(eid, cvp)| match Self::wait(cvp)? {
                AnyResponse::Profile(fl) => Some((eid, fl)),
                _ => None,
            })
            .collect()
    }

    fn enqueue(&self, fq: FullTreeQuery) -> Option<ResCvp> {
        let res_cvp = ResCvp::default();
        if !self.add_to_queue(Some(fq), res_cvp.clone()) {
            println!("queue full, rejecting query");
            return None;
        }
        Some(res_cvp)
    }

    fn wait(res_cvp: ResCvp) -> Option<AnyResponse> {
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

    fn add_to_queue(&self, fq: Option<FullTreeQuery>, res_cvp: ResCvp) -> bool {
        let (lock, cvar) = &*self.cv_pair;
        let mut data = lock.lock().unwrap();
        // the kill sentinel (None) must always get through
        if fq.is_some() && data.len() >= MAX_QUEUE_LEN {
            return false;
        }
        data.push_back((fq, res_cvp));
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
                    Some(fq) => {
                        let panic_cvp = res_cvp.clone();
                        let run = catch_unwind(AssertUnwindSafe(|| {
                            let params =
                                TreeMakingParams::new(&shared_state, &mut thread_fh, fq, res_cvp);
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

    pub fn pruned_cache_file_period(&self, fq: &FullTreeQuery, period: u8) -> PathBuf {
        self.tree_dir(fq).join(format!("{period}.zst"))
    }

    pub fn shallow_cache_file_period(&self, fq: &FullTreeQuery, depth: u8, period: u8) -> PathBuf {
        self.tree_dir(fq)
            .join(format!("shallow{depth}-{period}.zst"))
    }

    // The profile is keyed by the level, so every tree opening with it reads and writes one file.
    pub fn profile_cache_file_period(&self, fq: &FullTreeQuery, period: u8) -> PathBuf {
        self.entity_dir(fq)
            .join("first")
            .join(fq.level.to_string())
            .join(format!("{period}.zst"))
    }

    pub fn fake() -> Self {
        Self {
            in_progress: Mutex::new(HashMap::new()),
            gets: Getters::fake(),
            att_union: Arc::new(HashMap::new()),
        }
    }

    fn entity_dir(&self, fq: &FullTreeQuery) -> PathBuf {
        self.gets
            .stowage
            .paths
            .cache
            .join(&fq.name)
            .join(fq.ck.eid.to_string())
    }

    fn tree_dir(&self, fq: &FullTreeQuery) -> PathBuf {
        self.entity_dir(fq).join(fq.ck.tid.to_string())
    }
}

fn make_fq(q: TreeQ, eid: usize, root_type: &String, specs: &TreeSpecs) -> Option<FullTreeQuery> {
    let tid = q.tid.unwrap_or(0);
    let flag = |o: Option<bool>| o.unwrap_or(false);
    let command = if flag(q.big_read) {
        Command::BigRead
    } else if flag(q.big_prep) {
        Command::BigPrep
    } else if flag(q.wide) {
        Command::Serve(Serve::Wide)
    } else {
        Command::Serve(Serve::Pruned { shallow: q.shallow })
    };
    Some(FullTreeQuery {
        ck: specs.to_ck(tid, root_type, eid)?,
        level: specs.first_level(root_type, tid)?.level,
        period: WorkPeriods::from_year(q.year.unwrap_or(START_YEAR)),
        name: root_type.to_string(),
        cacheable: q.cacheable.unwrap_or(true),
        command,
    })
}

fn oaify(node: CollapsedNode, gets: &Getters) -> CollapsedNodeJson {
    CollapsedNodeGen {
        top_source: gets.work_oa.get(node.top_source as usize).copied(),
        link_count: node.link_count,
        source_count: node.source_count,
        top_cite_count: node.top_cite_count,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn wide(n_leaves: u32, total: u32) -> BufSerTree {
        let leaf = |lc| CollapsedNode {
            link_count: lc,
            ..Default::default()
        };
        BufSerTree {
            node: leaf(total),
            children: BufSerChildren::Leaves((1..=n_leaves).map(|k| (k, leaf(1))).collect()).into(),
        }
    }

    #[test]
    fn a_cut_level_does_not_assert_zero_for_an_absent_leaf() {
        let small_level = FirstLevel::from_wide(wide(MAX_WIDE as u32, 1000), MAX_WIDE);
        assert!(small_level.complete);
        assert_eq!(small_level.share(1), Some(0.001));
        assert_eq!(small_level.share(9999), Some(0.0));

        let cut = FirstLevel::from_wide(wide(MAX_WIDE as u32, 1000), 100_000);
        assert!(!cut.complete);
        assert_eq!(cut.share(1), Some(0.001));
        assert_eq!(cut.share(9999), None);

        // fewer keys than the cut keeps means nothing was cut, whatever the entity count
        let sparse = FirstLevel::from_wide(wide(3, 10), 100_000);
        assert!(sparse.complete);
        assert_eq!(sparse.share(9999), Some(0.0));

        assert_eq!(FirstLevel::from_wide(wide(0, 0), 10).share(1), None);
    }

    // The frontend's `BreakdownSpec` type reads exactly these three keys.
    #[test]
    fn a_breakdown_spec_serializes_as_the_frontend_reads_it() {
        let bd = BreakdownSpec {
            level: Level::citing("countries"),
            spec_denom_ind: 1,
            n_entities: 200,
        };
        let json = serde_json::to_value(&bd).unwrap();
        assert_eq!(
            json,
            serde_json::json!({"attributeType": "countries", "sourceSide": false, "specDenomInd": 1})
        );
    }
}
