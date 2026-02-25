use std::{
    fmt::Display,
    fs::{create_dir_all, remove_dir_all, File},
    io::{BufReader, BufWriter, Read, Write},
    marker::PhantomData,
    mem,
    os::linux::fs::MetadataExt,
    path::PathBuf,
    str::FromStr,
    sync::Mutex,
};

use crate::{
    components::{PartitionId, StackBasis, StackFr},
    ids::get_atts,
    instances::{CollT, Collapsing, FoldStackBase},
    interfacing::Getters,
    io::{
        AnyQuery, AnyResponse, BoolCvp, BufSerTree, CacheKey, CacheMap, CacheValue,
        FullMultiTreeQuery, FullTreeQuery, JsSerTree, ManFileHandle, ResCvp, ShallowTreesResponse,
        TreeBasisState, TreeResponse, TreeSpec, WT,
    },
    prune::{cut_tree, prune, prune_wide},
};
use dmove::{
    para::{set_and_notify, wait_for_data, wait_for_data_with_taker},
    ByteFixArrayInterface, Entity, UnsignedNumber,
};
use hashbrown::{hash_map::Entry, HashMap};
use rankless_rs::{
    agg_tree::{HeapIterator, MinHeap, SortedRecord, Updater},
    common::{read_buf_path, write_buf_path, NET},
    steps::{
        a1_entity_mapping::{YearInterface, N_PERS, POSSIBLE_YEAR_FILTERS},
        derive_links1::WorkPeriods,
    },
};
use serde::Serialize;

const MAX_PARTITIONS: usize = 16;
const MAX_BUFSIZE: usize = 512;
const SHALLOW_LIMIT: u64 = 50_000; // size (bytes) of file

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
    // Prune,
    Load,
}

pub struct TreeMakingRun<'a, TM> {
    params: TreeMakingParams<'a>,
    p: PhantomData<TM>,
}

pub struct TreeMakingParams<'a> {
    state: &'a TreeBasisState,
    fh: &'a mut ManFileHandle,
    pub fq: FullTreeQuery,
    res_cvp: ResCvp,
    fmqo: Option<FullMultiTreeQuery>,
}

pub trait CompleteTreeMaker<'a>: Sized + PartitioningIterator<'a> {
    type CT: Collapsing;
    type SR: SortedRecord;
}

pub trait PartitioningIterator<'a>:
    Iterator<Item = (PartitionId, StackFr<Self::StackBasis>)> + Sized
{
    type Root: FoldStackBase<<Self::StackBasis as StackBasis>::TopTree>;
    type StackBasis: StackBasis;
    const PARTITIONS: usize;
    const IS_SPEC: bool = true;
    const DEFAULT_PARTITION: u8 = 0;

    fn new(id: NetRoot<'a, Self>, gets: &'a Getters) -> Self;

    fn get_spec() -> TreeSpec {
        let breakdowns = Self::StackBasis::get_bds();
        let root_type = IteratorRootEtype::<Self>::NAME.to_string();
        TreeSpec {
            root_type,
            breakdowns,
            is_spec: Self::IS_SPEC,
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

pub trait GetRefWork {
    fn rwid(&self) -> WT;
}

impl Progress {
    fn from_e(value: &Mutex<CacheMap>, fq: &FullTreeQuery) -> Self {
        //if any of the periods in progress, somehow queue this period too?
        //in full progress, vs in pruning progress
        match value.lock().unwrap().entry(fq.ck.clone()) {
            Entry::Vacant(e) => {
                e.insert(CacheValue::InProgress(BoolCvp::default()));
                Progress::Calculate
            }
            Entry::Occupied(cv) => match cv.get() {
                CacheValue::InProgress(cvp) => Progress::Wait(cvp.clone()),
                CacheValue::Done(done_periods) => {
                    if done_periods.contains(&fq.period) {
                        Progress::Load
                    } else {
                        println!("not implemented partial waiting");
                        Progress::Calculate
                    }
                }
            },
        }
    }
}

impl<'a> TreeMakingParams<'a> {
    pub fn new(
        state: &'a TreeBasisState,
        fh: &'a mut ManFileHandle,
        aq: AnyQuery,
        res_cvp: ResCvp,
    ) -> Self {
        let mut fmqo = None;
        let fq = match aq {
            AnyQuery::Single(fq) => fq,
            AnyQuery::Shallows(sq) => {
                fmqo = Some(sq.clone());
                sq.act_fq
            }
        };
        Self {
            state,
            fh,
            fq,
            res_cvp,
            fmqo,
        }
    }

    pub fn run<TMK>(self)
    where
        TMK: CompleteTreeMaker<'a>,
        StackFr<TMK::StackBasis>: Ord + Clone + GetRefWork + ByteFixArrayInterface,
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
    StackFr<TMK::StackBasis>: Ord + Clone + GetRefWork + ByteFixArrayInterface,
    TMK::Root: FoldStackBase<TMK::CT>,
    PartIteratorStackElement<'a, TMK>: Updater<TMK::CT>,
    CollT<PartIteratorStackElement<'a, TMK>>: Into<BufSerTree>,
    TMK::StackBasis: StackBasis<TopTree = TMK::CT, SortedRec = TMK::SR>,
{
    pub fn run(mut self) {
        match mem::replace(&mut self.params.fmqo, None) {
            Some(fmq) => {
                let outer_res_cvp = std::mem::replace(&mut self.params.res_cvp, ResCvp::default());
                let mut trees = HashMap::new();
                let atts = HashMap::new();
                for eid in &fmq.sq.ids {
                    self.params.fq.ck.eid = *eid;
                    self.run_single_tree();
                    let out = wait_for_data(std::mem::replace(
                        &mut self.params.res_cvp,
                        ResCvp::default(),
                    ));
                    if let AnyResponse::Single(tri) = out {
                        trees.insert(*eid, tri.tree);
                    }
                }
                let resp = ShallowTreesResponse { trees, atts };
                set_and_notify(outer_res_cvp, Some(AnyResponse::Shallows(resp)));
            }
            None => self.run_single_tree(),
        }
    }

    fn run_single_tree(&mut self) {
        println!("requested entity: {}", self.params.fq);
        let prog = Progress::from_e(&self.params.state.im_cache, &self.params.fq);
        //getting one of e(tid) might trigger all others
        match prog {
            Progress::Calculate => {
                return self.fill_calculate();
            }
            Progress::Wait(cvp) => wait_for_data_with_taker(cvp, |_| ()), //TODO make sure this
            //is tested
            Progress::Load => {}
        }
        let now = std::time::Instant::now();
        let resp_tree_path = self.params.state.resp_cache_file(&self.params.fq);
        let mut resp_tree: BufSerTree = match read_buf_path(&resp_tree_path) {
            Ok(pt) => pt,
            Err(_) => {
                self.log("failed load");
                return self.fill_calculate();
            }
        };
        let mut shallowed = false;
        if let Some(sh_depth) = self.params.fq.q.shallow {
            shallowed = true;
            if let Ok(md) = std::fs::metadata(resp_tree_path) {
                if md.st_size() < SHALLOW_LIMIT {
                    shallowed = false;
                }
            };
            if shallowed {
                resp_tree = cut_tree(&resp_tree, sh_depth);
            }
        }
        let resp = self.to_tree_resp(resp_tree, shallowed);
        self.tlog("loaded and sent cache", now);
        set_single_resp(self.params.res_cvp.clone(), resp);
    }

    fn fill_calculate(&mut self) {
        if self.is_cacheable() {
            let full_path = self.params.state.full_cache_file_period(&self.params.fq, 0);
            create_dir_all(full_path.parent().unwrap())
                .unwrap_or_else(|_| self.log("can't create directory for cache"));
        }
        let mut pids = Vec::new();
        let et_id = NET::<IteratorRootEtype<TMK>>::from_usize(self.params.fq.ck.eid);
        if self.params.fq.q.big_read.unwrap_or(false) {
            self.read_big_calculate(&mut pids);
            // clone could possibly be done better, but should not be big deal
            set_single_resp(self.params.res_cvp.clone(), TreeResponse::empty())
        } else if self.params.fq.q.big_prep.unwrap_or(false) {
            self.write_tmp_parts();
            pids.extend(0..N_PERS as u8);
            set_single_resp(self.params.res_cvp.clone(), TreeResponse::empty())
        } else {
            let heaps = self.fill_heaps(&et_id);
            let now = std::time::Instant::now();
            let mut roots = Vec::new();
            // This could be abstracted to StackBasis StackBasis::fold_into
            // as this is just an additional collapsed level based on years
            heaps.into_iter().take(TMK::PARTITIONS).for_each(|heap| {
                let hither_o: Option<HeapIterator<TMK::SR>> = heap.into();
                let mut part_root: PartIteratorStackElement<'a, TMK> = et_id.into();
                match hither_o {
                    Some(hither) => TMK::StackBasis::fold_into(&mut part_root, hither),
                    None => self.log(format!(
                        "parition-heap is none at roots len {}",
                        roots.len()
                    )),
                }
                roots.push(part_root.collapse());
            });
            self.tlog("got roots", now);

            let now = std::time::Instant::now();
            let mut ser_tree_o = None;
            for (pid, part_root) in roots.into_iter().enumerate().rev() {
                TMK::fold_tree(&mut ser_tree_o, part_root);
                let stref = ser_tree_o.as_ref().unwrap();
                self.check_w(pid, stref, Some(self.params.res_cvp.clone()), &mut pids);
                if !self.is_cacheable() & (pid as u8 == self.params.fq.period) {
                    break;
                }
            }
            self.tlog("converted, ingested and wrote trees", now);
        }
        let cv = CacheValue::Done(pids);
        let mut cache_map = self.params.state.im_cache.lock().unwrap();
        let bcvp = match cache_map.insert(self.params.fq.ck.clone(), cv).unwrap() {
            CacheValue::InProgress(cvp) => cvp,
            _ => {
                return self.log("non inprogress cache");
            }
        };
        set_and_notify(bcvp, Some(()))
    }

    fn fill_heaps(&self, et_id: &NetRoot<'a, TMK>) -> [SrHeap<'a, TMK>; MAX_PARTITIONS] {
        let mut heaps = [(); MAX_PARTITIONS].map(|_| SrHeap::<'a, TMK>::new());
        let now = std::time::Instant::now();
        let maker = TMK::new(*et_id, &self.params.state.gets);
        for (pid, rec) in maker {
            heaps[pid as usize].push(rec);
        }
        self.tlog("got heaps", now);
        heaps
    }

    fn check_w(&mut self, pid: usize, tree: &BufSerTree, cvp: Option<ResCvp>, pids: &mut Vec<u8>) {
        let pid8 = pid as u8;
        self.write_resp(&tree, cvp, pid8);
        pids.push(pid8);
    }

    fn write_tmp_parts(&self) {
        let et_id = NET::<IteratorRootEtype<TMK>>::from_usize(self.params.fq.ck.eid);
        let cache_root = tmp_part_cache_root(&self.params.fq.ck);
        let piter = TMK::new(et_id, &self.params.state.gets);
        let mut writers: Vec<BufWriter<File>> = YearInterface::iter()
            .map(|yp| {
                BufWriter::new(
                    File::create(cache_root.join(yp.to_string())).expect("create year cache file"),
                )
            })
            .collect();
        for e in piter {
            let frec = e.1;
            let rwid = frec.rwid();
            let y = self.params.state.gets.year(&rwid);
            writers[*y as usize]
                .write(&frec.to_fbytes())
                .expect("writing to cache");
        }
        for w in writers.iter_mut() {
            w.flush().expect("writing in full")
        }

        self.log("wrote tmp");
        set_single_resp(self.params.res_cvp.clone(), TreeResponse::empty());
    }

    fn read_big_calculate(&mut self, pids: &mut Vec<u8>) {
        let et_id = NetRoot::<'a, TMK>::from_usize(self.params.fq.ck.eid);
        let cache_root = tmp_part_cache_root(&self.params.fq.ck);
        let mut buf: [u8; MAX_BUFSIZE] = [0; MAX_BUFSIZE];
        let mut ser_tree_o = None;
        let mut year_bp_iter = POSSIBLE_YEAR_FILTERS.iter().rev();
        let mut next_bp_o = year_bp_iter.next();
        let bufr = &mut buf[..StackFr::<TMK::StackBasis>::S];
        for y in YearInterface::iter().rev() {
            let cache_fp = cache_root.join(y.to_string());
            let mut reader = BufReader::new(File::open(&cache_fp).expect("reading year cache"));
            let mut year_heap = MinHeap::new();
            while let Ok(_) = reader.read_exact(bufr) {
                let fr = StackFr::<TMK::StackBasis>::from_fbytes(bufr);
                year_heap.push(fr);
            }
            let hither_o: Option<HeapIterator<TMK::SR>> = year_heap.into();
            let mut part_root: PartIteratorStackElement<'a, TMK> = et_id.into();
            match hither_o {
                Some(hither) => TMK::StackBasis::fold_into(&mut part_root, hither),
                None => self.log(format!("nothing read at y{y} from {cache_fp:?}")),
            }
            TMK::fold_tree(&mut ser_tree_o, part_root.collapse());
            let y16 = YearInterface::reverse(y);
            if let Some(next_bp) = next_bp_o {
                if y16 == *next_bp {
                    let pid = WorkPeriods::from_year(y16);
                    self.check_w(pid.to_usize(), &ser_tree_o.as_ref().unwrap(), None, pids);
                    next_bp_o = year_bp_iter.next();
                }
            } else {
                println!("finished with bps");
            }
        }
        remove_dir_all(cache_root).expect("removing cache");
    }

    fn write_resp(&mut self, full_tree: &BufSerTree, res_cvp_o: Option<ResCvp>, pid: u8) {
        if !self.is_cacheable() & (pid != self.params.fq.period) {
            return;
        }
        let mut pruned_o = None;
        let mut wide_o = None;
        if let Some(res_cvp) = res_cvp_o {
            if pid == self.params.fq.period {
                self.set_tree_to_res_cvp(res_cvp, full_tree, &mut pruned_o, &mut wide_o);
            }
        }
        if self.is_cacheable() {
            self.cache_tree(
                pruned_o.unwrap_or_else(|| self.prune_tree(full_tree)),
                TreeBasisState::pruned_cache_file_period,
                pid,
            );
            self.cache_tree(
                wide_o.unwrap_or_else(|| self.to_wide_tree(full_tree)),
                TreeBasisState::wide_cache_file_period,
                pid,
            );
        }
    }

    fn set_tree_to_res_cvp(
        &mut self,
        res_cvp: ResCvp,
        full_tree: &BufSerTree,
        pruned_o: &mut Option<BufSerTree>,
        wide_o: &mut Option<BufSerTree>,
    ) {
        let (resp_base_tree, sh) = if !self.is_cacheable() {
            //non cacheable is not shallowed, unless wide
            if self.params.fq.q.wide.unwrap_or(false) {
                (self.to_wide_tree(full_tree), true)
            } else {
                (self.prune_tree(full_tree), false)
            }
        } else {
            if self.params.fq.q.wide.unwrap_or(false) {
                //don't allow too wide
                let wide_tree = self.to_wide_tree(full_tree);
                *wide_o = Some(wide_tree.clone());
                (wide_tree, true)
            } else {
                let pruned_tree = self.prune_tree(full_tree);
                *pruned_o = Some(pruned_tree.clone());
                if let Some(depth) = self.params.fq.q.shallow {
                    (cut_tree(&pruned_tree, depth), true)
                } else {
                    (pruned_tree, false)
                }
            }
        };
        set_single_resp(res_cvp, self.to_tree_resp(resp_base_tree, sh));
    }

    fn prune_tree(&self, full_tree: &BufSerTree) -> BufSerTree {
        let now = std::time::Instant::now();
        let bds = TMK::get_spec().breakdowns;
        let pruned_tree = prune(full_tree, &self.params.state.att_union, &bds);
        self.tlog("pruned", now);
        pruned_tree
    }

    fn to_wide_tree(&self, full_tree: &BufSerTree) -> BufSerTree {
        let now = std::time::Instant::now();
        let bds = TMK::get_spec().breakdowns;
        let wide_tree = prune_wide(full_tree, &self.params.state.att_union, &bds);
        self.tlog("wide cut", now);
        wide_tree
    }

    fn cache_tree<F, T>(&self, obj: T, f: F, pid: u8)
    where
        F: Fn(&TreeBasisState, &FullTreeQuery, u8) -> PathBuf,
        T: Serialize,
    {
        let pb = f(&self.params.state, &self.params.fq, pid);
        match write_buf_path(obj, &pb) {
            Ok(_) => self.log(format!("wrote to {pb:?}")),
            Err(_) => self.log(format!("failed to write to {pb:?}")),
        }
    }

    fn log<D: Display>(&self, s: D) {
        println!("{}: {}", self.params.fq, s)
    }

    fn tlog<D: Display>(&self, s: D, now: std::time::Instant) {
        self.log(format!("{} in {}ms", s, now.elapsed().as_millis()));
    }

    fn to_tree_resp(&mut self, pruned_tree: BufSerTree, shallowed: bool) -> TreeResponse {
        let now = std::time::Instant::now();
        let bds = TMK::get_spec().breakdowns;
        let atts = get_atts(
            &pruned_tree,
            &bds,
            self.params.state,
            self.params.fh,
            &self.params.fq,
        );
        self.tlog("got atts", now);

        let now = std::time::Instant::now();
        let tree = JsSerTree::from_buf(pruned_tree, &self.params.state.gets);
        self.tlog("converted", now);
        TreeResponse {
            tree,
            atts,
            shallowed,
        }
    }

    fn is_cacheable(&self) -> bool {
        self.params.fq.q.cacheable.unwrap_or(true)
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

impl<T1> GetRefWork for (T1, WT, WT) {
    fn rwid(&self) -> WT {
        self.1
    }
}

impl<T1, T2> GetRefWork for (T1, T2, WT, WT) {
    fn rwid(&self) -> WT {
        self.2
    }
}

impl<T1, T2, T3> GetRefWork for (T1, T2, T3, WT, WT) {
    fn rwid(&self) -> WT {
        self.3
    }
}

impl<T1, T2, T3, T4> GetRefWork for (T1, T2, T3, T4, WT, WT) {
    fn rwid(&self) -> WT {
        self.4
    }
}

fn set_single_resp(cvp: ResCvp, sresp: TreeResponse) {
    let val = Some(AnyResponse::Single(sresp));
    set_and_notify(cvp, val);
}

fn tmp_part_cache_root(ck: &CacheKey) -> PathBuf {
    let pstr = format!("/tmp/dmove-parts/{}/{}/{}", ck.etype, ck.tid, ck.eid);
    let cache_root = PathBuf::from_str(&pstr).expect("tmp path");
    create_dir_all(&cache_root).expect("making tmp dir");
    cache_root
}
