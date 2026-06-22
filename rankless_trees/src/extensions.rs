use dmove::{Entity, UnsignedNumber};
use rankless_rs::{
    common::init_empty_slice,
    gen::a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields},
    gen::derive_links3::HitPapers,
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

    // Total (unfiltered OpenAlex) citation count per entity for the search subtitle. Only authors
    // carry a value; every other type returns all-None, so the field drops from their payload.
    fn get_raw_cites_arr(_rif: &RootInterfaces<Self>, _gets: &Getters) -> Box<[Option<u32>]> {
        init_empty_slice::<Self, _>()
    }
}

impl DistinctionText for Countries {}
impl DistinctionText for Subfields {}
impl DistinctionText for Sources {}
impl DistinctionText for HitPapers {}

impl DistinctionText for Authors {
    fn get_raw_cites_arr(_rif: &RootInterfaces<Self>, gets: &Getters) -> Box<[Option<u32>]> {
        (0..(Self::N + 1))
            .map(|aid| Some(gets.raw_cites(&aid).to_usize() as u32))
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
