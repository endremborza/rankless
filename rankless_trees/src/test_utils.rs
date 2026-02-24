use std::vec::IntoIter;

use crate::{
    components::{MinIntX, PartitionId, StackBasis, StackFr},
    interfacing::Getters,
    io::{TreeQ, WT},
    part_iterator::PartitioningIterator,
    path_finder::RefGraph,
};
use dmove::{ET, UnsignedNumber};
use hashbrown::HashMap;
use rankless_rs::{
    gen::a1_entity_mapping::Institutions,
    steps::a1_entity_mapping::N_PERS,
};

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
    fn get_pid(_v: &StackFr<Self::SB>) -> PartitionId {
        0
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
{
    type Root = MinIntX<Institutions>;
    type StackBasis = TSB::SB;
    const PARTITIONS: usize = N_PERS;

    fn new(id: ET<Institutions>, _gets: &Getters) -> Self {
        let viter = TSB::get_vec(id.to_usize()).into_iter();
        Self { viter }
    }
}

impl<TSB> Iterator for Tither<TSB>
where
    TSB: TestSB,
{
    type Item = (PartitionId, StackFr<TSB::SB>);

    fn next(&mut self) -> Option<Self::Item> {
        self.viter.next().map(|v| (TSB::get_pid(&v), v))
    }
}

pub fn test_q(i: u8) -> TreeQ {
    TreeQ {
        year: None,
        tid: Some(i),
        connections: None,
        big_prep: None,
        big_read: None,
        shallow: None,
        cacheable: None,
        wide: None,
    }
}
