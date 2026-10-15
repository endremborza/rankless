use std::{
    fmt::Display,
    fs::{create_dir_all, rename},
    marker::PhantomData,
    ops::Range,
    os::linux::fs::MetadataExt,
    path::PathBuf,
    sync::{LazyLock, Mutex},
    time::{Duration, Instant},
};

use crate::{
    components::{StackBasis, StackFr},
    ids::get_atts,
    instances::{CollT, Collapsing, FoldStackBase},
    interfacing::Getters,
    io::{
        AnyResponse, BoolCvp, BufSerTree, CacheKey, FirstLevel, FullTreeQuery, InProgressMap,
        JsSerTree, ManFileHandle, ResCvp, Serve, TreeBasisState, TreeResponse, TreeSpec, WT,
    },
    prune::{cut_tree, prune, prune_wide},
};
use dmove::{
    para::{set_and_notify, wait_for_data_with_taker},
    Entity, UnsignedNumber,
};
use hashbrown::hash_map::Entry;
use rankless_rs::{
    agg_tree::{HeapIterator, MinHeap, SortedRecord, Updater},
    common::{read_buf_path, write_buf_path, NET},
    gen::a1_entity_mapping::{Sources, Subfields},
    steps::a1_entity_mapping::{YearInterface, N_PERS, POSSIBLE_YEAR_FILTERS},
};
use serde::Serialize;

// A run of years is folded once it holds this many records; a period's last run is folded at
// any size.
const RUN_RECORDS: usize = 1 << 25;
const SHALLOW_LIMIT: u64 = 50_000; // size (bytes) of file

// The FE's SSR fetch is always ?shallow=1 (entity +page.server.ts)
const PRECALC_SHALLOW_DEPTH: u8 = 1;
// Root types whose trees allow specialization but open without it.
const SPEC_OFF_BY_DEFAULT: [&str; 2] = [Sources::NAME, Subfields::NAME];

static DEBUG_LOG: LazyLock<bool> =
    LazyLock::new(|| std::env::var("RANKLESS_DEBUG_LOG").is_ok_and(|v| v != "0"));

pub type NetRoot<'a, Pit> = NET<IteratorRootEtype<'a, Pit>>;

pub type PartIteratorStackElement<'a, Pit> =
    <<Pit as PartitioningIterator<'a>>::Root as FoldStackBase<
        <<Pit as PartitioningIterator<'a>>::StackBasis as StackBasis>::TopTree,
    >>::StackElement;

pub type IteratorRootEtype<'a, Pit> = <<Pit as PartitioningIterator<'a>>::Root as FoldStackBase<
    <<Pit as PartitioningIterator<'a>>::StackBasis as StackBasis>::TopTree,
>>::LevelEntity;

type SrHeap<'a, S> = MinHeap<StackFr<<S as PartitioningIterator<'a>>::StackBasis>>;

enum Progress {
    Wait(BoolCvp),
    Calculate,
}

pub struct TreeMakingRun<'a, TM> {
    params: TreeMakingParams<'a>,
    p: PhantomData<TM>,
}

// Removes the in-progress entry and wakes waiters on all exits, including panics
struct InProgressGuard<'a> {
    map: &'a Mutex<InProgressMap>,
    ck: CacheKey,
}

// The records a build folded: in how many runs, and the largest run.
#[derive(Default)]
struct Runs {
    n: usize,
    records: usize,
    largest: usize,
    walk: Duration,
    fold: Duration,
}

pub struct TreeMakingParams<'a> {
    state: &'a TreeBasisState,
    fh: &'a mut ManFileHandle,
    pub fq: FullTreeQuery,
    res_cvp: ResCvp,
}

pub trait CompleteTreeMaker<'a>: Sized + PartitioningIterator<'a> {
    type CT: Collapsing;
    type SR: SortedRecord;
}

// A tree's records, from the root's works whose ids fall in `works`.
pub trait PartitioningIterator<'a>: Iterator<Item = StackFr<Self::StackBasis>> + Sized {
    type Root: FoldStackBase<<Self::StackBasis as StackBasis>::TopTree>;
    type StackBasis: StackBasis;
    const IS_SPEC: bool = true;
    const DEFAULT_PARTITION: u8 = 0;

    fn new(id: NetRoot<'a, Self>, gets: &'a Getters, works: Range<WT>) -> Self;

    fn get_spec() -> TreeSpec {
        let breakdowns = Self::StackBasis::get_bds();
        let root_type = IteratorRootEtype::<Self>::NAME.to_string();
        TreeSpec {
            is_spec: Self::IS_SPEC && !SPEC_OFF_BY_DEFAULT.contains(&root_type.as_str()),
            root_type,
            breakdowns,
            allow_spec: Self::IS_SPEC,
            default_partition: POSSIBLE_YEAR_FILTERS[Self::DEFAULT_PARTITION as usize],
        }
    }

    fn fold_tree<R>(ser_tree_o: &mut Option<BufSerTree>, part_root: R)
    where
        R: Into<BufSerTree>,
    {
        let part_ser: BufSerTree = part_root.into();
        match ser_tree_o {
            Some(ser_tree) => ser_tree.ingest_disjunct(part_ser),
            None => *ser_tree_o = Some(part_ser),
        };
    }
}

impl Progress {
    fn from_e(value: &Mutex<InProgressMap>, fq: &FullTreeQuery) -> Self {
        match value.lock().unwrap().entry(fq.ck.clone()) {
            Entry::Vacant(e) => {
                e.insert(BoolCvp::default());
                Progress::Calculate
            }
            Entry::Occupied(cv) => Progress::Wait(cv.get().clone()),
        }
    }
}

impl Drop for InProgressGuard<'_> {
    fn drop(&mut self) {
        if let Some(cvp) = self.map.lock().unwrap().remove(&self.ck) {
            set_and_notify(cvp, Some(()));
        }
    }
}

impl<'a> TreeMakingParams<'a> {
    pub fn new(
        state: &'a TreeBasisState,
        fh: &'a mut ManFileHandle,
        fq: FullTreeQuery,
        res_cvp: ResCvp,
    ) -> Self {
        Self {
            state,
            fh,
            fq,
            res_cvp,
        }
    }

    pub fn run<TMK>(self)
    where
        TMK: CompleteTreeMaker<'a>,
        StackFr<TMK::StackBasis>: Ord + Clone,
        TMK::Root: FoldStackBase<TMK::CT>,
        PartIteratorStackElement<'a, TMK>: Updater<TMK::CT>,
        CollT<PartIteratorStackElement<'a, TMK>>: Into<BufSerTree>,
        TMK::StackBasis: StackBasis<TopTree = TMK::CT, SortedRec = TMK::SR>,
    {
        TreeMakingRun {
            params: self,
            p: PhantomData::<TMK>,
        }
        .run()
    }
}

impl<'a, TMK> TreeMakingRun<'a, TMK>
where
    TMK: CompleteTreeMaker<'a>,
    StackFr<TMK::StackBasis>: Ord + Clone,
    TMK::Root: FoldStackBase<TMK::CT>,
    PartIteratorStackElement<'a, TMK>: Updater<TMK::CT>,
    CollT<PartIteratorStackElement<'a, TMK>>: Into<BufSerTree>,
    TMK::StackBasis: StackBasis<TopTree = TMK::CT, SortedRec = TMK::SR>,
{
    pub fn run(mut self) {
        println!("requested entity: {}", self.params.fq);
        loop {
            let now = Instant::now();
            if let Some(resp) = self.load_cached(self.params.fq.serve) {
                self.tlog("loaded and sent cache", now.elapsed());
                set_and_notify(self.params.res_cvp.clone(), Some(resp));
                return;
            }
            if !self.is_cacheable() {
                // no file will ever appear, so waiting on an in-progress compute is pointless
                return self.fill_by_years();
            }
            match Progress::from_e(&self.params.state.in_progress, &self.params.fq) {
                Progress::Calculate => {
                    let _guard = InProgressGuard {
                        map: &self.params.state.in_progress,
                        ck: self.params.fq.ck.clone(),
                    };
                    return self.fill_by_years();
                }
                Progress::Wait(cvp) => wait_for_data_with_taker(cvp, |_| ()),
            }
        }
    }

    fn load_cached(&mut self, serve: Serve) -> Option<AnyResponse> {
        let period = self.params.fq.period;
        match serve {
            Serve::Pruned { shallow } => self.load_pruned(shallow, period).map(AnyResponse::Tree),
            Serve::Wide | Serve::Profile => {
                let path = self
                    .params
                    .state
                    .profile_cache_file_period(&self.params.fq, period);
                let wide = read_buf_path::<BufSerTree, _>(&path).ok()?;
                Some(self.first_level_resp(serve, wide))
            }
        }
    }

    fn load_pruned(&mut self, shallow: Option<u8>, period: u8) -> Option<TreeResponse> {
        let state = self.params.state;
        let sh_path =
            shallow.map(|depth| state.shallow_cache_file_period(&self.params.fq, depth, period));
        if let Some(sh_tree) = sh_path
            .as_ref()
            .and_then(|p| read_buf_path::<BufSerTree, _>(p).ok())
        {
            return Some(self.to_tree_resp(sh_tree, true));
        }
        let path = state.pruned_cache_file_period(&self.params.fq, period);
        let mut tree = read_buf_path::<BufSerTree, _>(&path).ok()?;
        // a small tree is served whole whatever the depth asked
        let big = std::fs::metadata(&path).is_ok_and(|md| md.st_size() >= SHALLOW_LIMIT);
        let shallowed = match (shallow, sh_path) {
            (Some(depth), Some(sh_path)) if big => {
                tree = cut_tree(&tree, depth);
                self.cache_tree(&tree, sh_path);
                true
            }
            _ => false,
        };
        Some(self.to_tree_resp(tree, shallowed))
    }

    fn fill_by_years(&mut self) {
        let et_id = NetRoot::<'a, TMK>::from_usize(self.params.fq.ck.eid);
        let state: &'a TreeBasisState = self.params.state;
        let mut write = Duration::ZERO;
        let runs = Self::walk_years(et_id, &state.gets, RUN_RECORDS, |pid, tree| {
            let now = Instant::now();
            self.write_resp(tree, pid);
            write += now.elapsed();
            self.is_cacheable() | (pid != self.params.fq.period)
        });
        self.dtlog("got heaps", runs.walk);
        self.dtlog("got roots", runs.fold);
        self.tlog("converted, ingested and wrote trees", write);
        self.log(format!(
            "{} records in {} runs, the largest {}",
            runs.records, runs.n, runs.largest
        ));
    }

    // Walks the root's works a publication year at a time, newest period first, so only one run
    // of years' records is held: a run is folded once it holds `run_records`, and at its
    // period's end. A cited work's records all fall in its year, and the trees of disjoint cited
    // works add up (`ingest_disjunct`), so however a period splits into runs, merging them oldest
    // first builds the tree one fold of the period would. Each period's cumulative tree goes to
    // `period_done`, which says whether to go on.
    fn walk_years(
        et_id: NetRoot<'a, TMK>,
        gets: &'a Getters,
        run_records: usize,
        mut period_done: impl FnMut(u8, &BufSerTree) -> bool,
    ) -> Runs {
        let mut runs = Runs::default();
        let mut tree = None;
        for pid in (0..N_PERS).rev() {
            let mut heap = SrHeap::<'a, TMK>::new();
            for year in period_years(pid) {
                let now = Instant::now();
                for rec in TMK::new(et_id, gets, gets.year_works(year)) {
                    heap.push(rec);
                }
                runs.walk += now.elapsed();
                if heap.len() >= run_records {
                    let full = std::mem::replace(&mut heap, SrHeap::<'a, TMK>::new());
                    Self::fold_run(et_id, &mut tree, full, &mut runs);
                }
            }
            Self::fold_run(et_id, &mut tree, heap, &mut runs);
            if !period_done(pid as u8, tree.as_ref().unwrap()) {
                break;
            }
        }
        runs
    }

    fn fold_run(
        et_id: NetRoot<'a, TMK>,
        tree: &mut Option<BufSerTree>,
        heap: SrHeap<'a, TMK>,
        runs: &mut Runs,
    ) {
        let now = Instant::now();
        runs.n += 1;
        runs.records += heap.len();
        runs.largest = runs.largest.max(heap.len());
        let mut part_root: PartIteratorStackElement<'a, TMK> = et_id.into();
        if let Some(hither) = Option::<HeapIterator<TMK::SR>>::from(heap) {
            TMK::StackBasis::fold_into(&mut part_root, hither);
        }
        TMK::fold_tree(tree, part_root.collapse());
        runs.fold += now.elapsed();
    }

    fn write_resp(&mut self, full_tree: &BufSerTree, pid: u8) {
        if !self.is_cacheable() & (pid != self.params.fq.period) {
            return;
        }
        let mut pruned_o = None;
        let mut wide_o = None;
        if pid == self.params.fq.period {
            self.set_tree_to_res_cvp(full_tree, &mut pruned_o, &mut wide_o);
        }
        if self.is_cacheable() {
            let state = self.params.state;
            let pruned = pruned_o.unwrap_or_else(|| self.prune_tree(full_tree));
            self.cache_tree(
                &pruned,
                state.pruned_cache_file_period(&self.params.fq, pid),
            );
            self.cache_shallow(&pruned, pid);
            let wide = wide_o.unwrap_or_else(|| self.to_wide_tree(full_tree));
            self.cache_tree(wide, state.profile_cache_file_period(&self.params.fq, pid));
        }
    }

    // Preserves SHALLOW_LIMIT semantics: small entities get no shallow file
    // and keep being served whole (unshallowed) from the pruned cache.
    fn cache_shallow(&self, pruned: &BufSerTree, pid: u8) {
        let state = self.params.state;
        let pruned_path = state.pruned_cache_file_period(&self.params.fq, pid);
        if std::fs::metadata(&pruned_path).is_ok_and(|md| md.st_size() >= SHALLOW_LIMIT) {
            let depth = PRECALC_SHALLOW_DEPTH;
            let sh_path = state.shallow_cache_file_period(&self.params.fq, depth, pid);
            self.cache_tree(cut_tree(pruned, depth), sh_path);
        }
    }

    // Answers the query from the full tree and hands back what the cache can keep of it: a
    // non-cacheable tree is small, so it is served whole whatever depth was asked.
    fn set_tree_to_res_cvp(
        &mut self,
        full_tree: &BufSerTree,
        pruned_o: &mut Option<BufSerTree>,
        wide_o: &mut Option<BufSerTree>,
    ) {
        let serve = self.params.fq.serve;
        let cacheable = self.is_cacheable();
        let resp = match serve {
            Serve::Wide | Serve::Profile => {
                let wide = self.to_wide_tree(full_tree);
                if cacheable {
                    *wide_o = Some(wide.clone());
                }
                self.first_level_resp(serve, wide)
            }
            Serve::Pruned { shallow } => {
                let pruned = self.prune_tree(full_tree);
                let (tree, shallowed) = match (shallow, cacheable) {
                    (Some(depth), true) => {
                        let cut = cut_tree(&pruned, depth);
                        *pruned_o = Some(pruned);
                        (cut, true)
                    }
                    (None, true) => {
                        *pruned_o = Some(pruned.clone());
                        (pruned, false)
                    }
                    (_, false) => (pruned, false),
                };
                AnyResponse::Tree(self.to_tree_resp(tree, shallowed))
            }
        };
        set_and_notify(self.params.res_cvp.clone(), Some(resp));
    }

    fn first_level_resp(&mut self, serve: Serve, wide: BufSerTree) -> AnyResponse {
        match serve {
            Serve::Profile => {
                let n_entities = TMK::get_spec().breakdowns[0].n_entities;
                AnyResponse::Profile(FirstLevel::from_wide(wide, n_entities))
            }
            _ => AnyResponse::Tree(self.to_tree_resp(wide, true)),
        }
    }

    fn prune_tree(&self, full_tree: &BufSerTree) -> BufSerTree {
        let now = Instant::now();
        let bds = TMK::get_spec().breakdowns;
        let pruned_tree = prune(full_tree, &self.params.state.att_union, &bds);
        self.dtlog("pruned", now.elapsed());
        pruned_tree
    }

    fn to_wide_tree(&self, full_tree: &BufSerTree) -> BufSerTree {
        let now = Instant::now();
        let bds = TMK::get_spec().breakdowns;
        let wide_tree = prune_wide(full_tree, &self.params.state.att_union, &bds);
        self.dtlog("wide cut", now.elapsed());
        wide_tree
    }

    // Written beside the target and renamed into place, so a reader never sees a partial file and
    // two builds sharing one profile path never interleave.
    fn cache_tree<T: Serialize>(&self, obj: T, path: PathBuf) {
        let written = path.parent().map_or(Ok(()), create_dir_all).and_then(|_| {
            let tmp = path.with_extension(format!("{:x}.tmp", rand::random::<u64>()));
            write_buf_path(obj, &tmp)?;
            rename(&tmp, &path)
        });
        match written {
            Ok(_) => self.dlog(format!("wrote to {path:?}")),
            Err(_) => self.log(format!("failed to write to {path:?}")),
        }
    }

    fn log<D: Display>(&self, s: D) {
        println!("{}: {}", self.params.fq, s)
    }

    fn tlog<D: Display>(&self, s: D, took: Duration) {
        self.log(format!("{} in {}ms", s, took.as_millis()));
    }

    fn dlog<D: Display>(&self, s: D) {
        if *DEBUG_LOG {
            self.log(s)
        }
    }

    fn dtlog<D: Display>(&self, s: D, took: Duration) {
        if *DEBUG_LOG {
            self.tlog(s, took)
        }
    }

    fn to_tree_resp(&mut self, pruned_tree: BufSerTree, shallowed: bool) -> TreeResponse {
        let now = Instant::now();
        let bds = TMK::get_spec().breakdowns;
        let atts = get_atts(
            &pruned_tree,
            &bds,
            self.params.state,
            self.params.fh,
            &self.params.fq,
        );
        self.dtlog("got atts", now.elapsed());

        let now = Instant::now();
        let tree = JsSerTree::from_buf(pruned_tree, &self.params.state.gets);
        self.dtlog("converted", now.elapsed());
        TreeResponse {
            tree,
            atts,
            shallowed,
        }
    }

    fn is_cacheable(&self) -> bool {
        self.params.fq.cacheable
    }
}

impl<'a, T> CompleteTreeMaker<'a> for T
where
    T: PartitioningIterator<'a>,
    <T::StackBasis as StackBasis>::TopTree: Collapsing,
    <T::StackBasis as StackBasis>::SortedRec: SortedRecord,
{
    type CT = <T::StackBasis as StackBasis>::TopTree;
    type SR = <T::StackBasis as StackBasis>::SortedRec;
}

// The year ids of period `pid`: from its start year to the next period's.
fn period_years(pid: usize) -> Range<u8> {
    let start = YearInterface::parse(POSSIBLE_YEAR_FILTERS[pid]);
    let end = POSSIBLE_YEAR_FILTERS
        .get(pid + 1)
        .map_or(YearInterface::iter().end, |&y| YearInterface::parse(y));
    start..end
}

#[cfg(test)]
mod tests {
    use rand::{rngs::StdRng, Rng, SeedableRng};
    use rankless_rs::gen::a1_entity_mapping::Works;

    use super::*;
    use crate::{
        components::IntX,
        test_utils::{TestSB, Tither},
    };

    // Cited works spread over every year, several citing works and subfield ids each, so runs of
    // one year differ from runs of a period.
    struct Spread;

    impl TestSB for Spread {
        type SB = (IntX<Subfields, 0, true>, IntX<Works, 0, true>);
        fn get_vec(_id: usize) -> Vec<StackFr<Self::SB>> {
            let mut rng = StdRng::seed_from_u64(7);
            let n_years = YearInterface::iter().len() as WT;
            (0..4096)
                .map(|_| {
                    let rwid = rng.gen::<WT>() % n_years;
                    (rng.gen::<u8>() % 5, rwid, rwid, rng.gen::<WT>() % 9)
                })
                .collect()
        }
    }

    #[test]
    fn year_runs_merge_into_the_period_trees() {
        let state = TreeBasisState::fake();
        let periods = |run_records| {
            let mut trees = Vec::new();
            TreeMakingRun::<Tither<Spread>>::walk_years(0, &state.gets, run_records, |pid, t| {
                trees.push((pid, serde_json::to_value(t).unwrap()));
                true
            });
            trees
        };
        let by_period = periods(usize::MAX);
        assert_eq!(by_period.len(), N_PERS);
        assert_eq!(periods(1), by_period);
    }
}
