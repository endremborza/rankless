use std::ops::AddAssign;

use dmove::Entity;
use hashbrown::HashMap;
use rankless_rs::{
    common::init_empty_slice,
    gen::a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields},
};

use crate::interfacing::{Getters, RootInterfaceable, RootInterfaces};

const FLAG_BASE: [u8; 8] = [240, 159, 135, 101, 240, 159, 135, 101];

pub trait DistinctionText: RootInterfaceable + Sized {
    fn get_distinction_text_arr(
        _rif: &RootInterfaces<Self>,
        _gets: &Getters,
    ) -> Box<[Option<String>]> {
        init_empty_slice::<Self, _>()
    }
}

impl DistinctionText for Countries {}
impl DistinctionText for Subfields {}
impl DistinctionText for Sources {}

impl DistinctionText for Authors {
    fn get_distinction_text_arr(
        rif: &RootInterfaces<Self>,
        gets: &Getters,
    ) -> Box<[Option<String>]> {
        (0..(Self::N + 1))
            .map(|aid| {
                let mut ccs = HashMap::new();
                for irel in rif.inst_rels[aid].iter() {
                    let cid = gets.icountry(&irel.inst);
                    if *cid > 0 {
                        let cc = gets.ccodes(cid);
                        let entry = ccs.entry(cc.clone()).or_insert(0);
                        entry.add_assign(irel.papers);
                    }
                }
                let mut kvs: Vec<([u8; 2], u16)> = ccs.into_iter().collect();
                if kvs.len() > 0 {
                    kvs.sort_by(|l, r| r.1.cmp(&l.1));
                    let s = kvs
                        .iter()
                        .map(|e| cc_to_flag(&e.0))
                        .take(4)
                        .collect::<Vec<String>>()
                        .join(", ");
                    Some(s)
                } else {
                    None
                }
            })
            .collect()
    }
}

impl DistinctionText for Institutions {
    fn get_distinction_text_arr(
        _rif: &RootInterfaces<Self>,
        gets: &Getters,
    ) -> Box<[Option<String>]> {
        (0..(Self::N + 1))
            .map(|iid| {
                let cid = gets.icity(&iid);
                let coid = gets.icountry(&iid);
                let cc = gets.ccodes(coid);
                if *coid == 0 {
                    None
                } else {
                    // let cotxt = String::from_utf8(cc.into()).unwrap();
                    let cotxt = cc_to_flag(cc);
                    if *cid > 0 {
                        let city = String::from_utf8(gets.cinames(*cid).into()).unwrap();
                        Some(format!("{city}, {cotxt}"))
                    } else {
                        Some(cotxt)
                    }
                }
            })
            .collect()
    }
}

fn cc_to_flag(cc: &[u8; 2]) -> String {
    let mut fc = FLAG_BASE.clone();
    fc[3] += cc[0];
    fc[7] += cc[1];
    String::from_utf8(fc.into()).unwrap()
}
