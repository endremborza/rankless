use std::{ops::Range, vec::IntoIter};

use crate::{
    components::{MinIntX, StackBasis, StackFr},
    interfacing::Getters,
    io::{TreeQ, WT},
    part_iterator::PartitioningIterator,
    path_finder::RefGraph,
};
use dmove::{UnsignedNumber, ET};
use hashbrown::HashMap;
use rankless_rs::gen::a1_entity_mapping::Institutions;

// ---- Graph access mock ----

pub struct TestGraph {
    refs: HashMap<WT, Vec<WT>>,
    cites: HashMap<WT, Vec<WT>>,
}

impl TestGraph {
    pub fn new() -> Self {
        Self {
            refs: HashMap::new(),
            cites: HashMap::new(),
        }
    }

    /// Add refs for wid and automatically build the inverse cites entries.
    pub fn with_refs(mut self, wid: WT, refs: Vec<WT>) -> Self {
        for &r in &refs {
            self.cites.entry(r).or_default().push(wid);
        }
        self.refs.insert(wid, refs);
        self
    }
}

impl RefGraph for TestGraph {
    fn get_refs(&self, wid: WT) -> &[WT] {
        self.refs.get(&wid).map(|v| v.as_slice()).unwrap_or(&[])
    }

    fn get_cites(&self, wid: WT) -> &[WT] {
        self.cites.get(&wid).map(|v| v.as_slice()).unwrap_or(&[])
    }
}

// ---- Tree-building test infrastructure ----

pub trait TestSB {
    type SB: StackBasis;
    fn get_vec(id: usize) -> Vec<StackFr<Self::SB>>;
}

// A flat record's cited work: the second to last of its fields.
pub trait GetRefWork {
    fn rwid(&self) -> WT;
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

pub struct Tither<TSB>
where
    TSB: TestSB,
{
    viter: IntoIter<StackFr<TSB::SB>>,
}

impl<TSB> PartitioningIterator<'_> for Tither<TSB>
where
    TSB: TestSB,
    TSB::SB: StackBasis,
    StackFr<TSB::SB>: GetRefWork,
{
    type Root = MinIntX<Institutions>;
    type StackBasis = TSB::SB;

    fn new(id: ET<Institutions>, _gets: &Getters, works: Range<WT>) -> Self {
        let recs = TSB::get_vec(id.to_usize()).into_iter();
        let viter: Vec<_> = recs.filter(|r| works.contains(&r.rwid())).collect();
        Self {
            viter: viter.into_iter(),
        }
    }
}

impl<TSB> Iterator for Tither<TSB>
where
    TSB: TestSB,
{
    type Item = StackFr<TSB::SB>;

    fn next(&mut self) -> Option<Self::Item> {
        self.viter.next()
    }
}

pub fn test_q(i: u8) -> TreeQ {
    TreeQ {
        year: None,
        tid: Some(i),
        shallow: None,
        cacheable: None,
        wide: None,
    }
}
