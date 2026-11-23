use std::{ops::Range, vec::IntoIter};

use crate::{
    components::{MinIntX, StackBasis, StackFr},
    interfacing::Getters,
    io::{TreeQ, WT},
    part_iterator::PartitioningIterator,
};
use dmove::{UnsignedNumber, ET};
use rankless_rs::gen::a1_entity_mapping::Institutions;

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
