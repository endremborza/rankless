use std::collections::BinaryHeap;

use dmove::{BigId, ByteFixArrayInterface, CompactEntity, Entity, MarkedAttribute, NamespacedEntity, UnsignedNumber, ET, MAA};
use hashbrown::HashMap;
use hashbrown::HashSet;

use crate::{
    common::{init_empty_slice, MainWorkMarker},
    gen::{
        a1_entity_mapping::{Authors, Works},
        a2_init_atts::{AuthorNobels, WorkYears},
        derive_links1::WorkFilteredAuthors,
    },
    steps::a1_entity_mapping::Years,
    CiteCountMarker, QuickestBox, ReadIter, Stowage,
};

pub(super) const MIN_UNIVERSAL: usize = 500;
pub(super) const MIN_NEEDED: usize = 10;
pub(super) const TOP_TOPIC: usize = 3;
pub(super) const TOP_PCTILE: f64 = 0.01;
pub(super) const SF_YEAR_MIN_PAPERS: usize = 400;
pub(super) const W_SF: f64 = 0.005;
pub(super) const W_YEAR: f64 = 0.12;
pub(super) const W_SF_YEAR: f64 = 1.0 - W_SF - W_YEAR;
pub(super) const SCORE_THRESHOLD: f64 = 1.5;
pub(super) const NOBEL_MULTIPLIER: f64 = 2.0;

pub(super) type CCUI = ET<MAA<Works, CiteCountMarker>>;

pub fn get_nobeled_works(stowage: &Stowage, w_years: &[ET<Years>]) -> HashSet<ET<Works>> {
    let author_nobels = stowage.get_entity_interface::<AuthorNobels, QuickestBox>();
    let mut nobeled_works = HashSet::new();
    for (wid, w_aids) in stowage
        .get_entity_interface::<WorkFilteredAuthors, ReadIter>()
        .enumerate()
    {
        let wyear = w_years[wid];
        for aid in w_aids {
            let anobely = author_nobels[aid.to_usize()].1;
            if anobely >= wyear {
                nobeled_works.insert(ET::<Works>::from_usize(wid));
            }
        }
    }
    nobeled_works
}

pub(super) fn compute_year_bms(w_years: &[ET<Years>], ccs: &[CCUI]) -> Box<[f64]> {
    let mut groups = init_empty_slice::<Years, Vec<CCUI>>();
    for (wid, yr) in w_years.iter().enumerate() {
        groups[yr.to_usize()].push(ccs[wid]);
    }
    groups
        .iter_mut()
        .map(|g| top_pctile(g))
        .collect::<Vec<_>>()
        .into()
}

pub(super) fn compute_sf_year_bms(
    w_sfs: &[Box<[ET<crate::gen::a1_entity_mapping::Subfields>]>],
    w_years: &[ET<Years>],
    ccs: &[CCUI],
    year_bms: &[f64],
) -> HashMap<(usize, usize), f64> {
    let mut groups: HashMap<(usize, usize), Vec<CCUI>> = HashMap::new();
    for (wid, sfs) in w_sfs.iter().enumerate() {
        let yr = w_years[wid].to_usize();
        let cc = ccs[wid];
        for sf in sfs.iter() {
            groups.entry((sf.to_usize(), yr)).or_default().push(cc);
        }
    }
    groups
        .into_iter()
        .map(|((sf, yr), mut v)| {
            let bm = if v.len() >= SF_YEAR_MIN_PAPERS {
                top_pctile(&mut v)
            } else {
                year_bms[yr]
            };
            ((sf, yr), bm)
        })
        .collect()
}

pub(super) fn compute_sf_bms(
    w_sfs: &[Box<[ET<crate::gen::a1_entity_mapping::Subfields>]>],
    ccs: &[CCUI],
) -> HashMap<usize, f64> {
    let mut groups: HashMap<usize, Vec<CCUI>> = HashMap::new();
    for (wid, sfs) in w_sfs.iter().enumerate() {
        for sf in sfs.iter() {
            groups.entry(sf.to_usize()).or_default().push(ccs[wid]);
        }
    }
    groups
        .into_iter()
        .map(|(sf, mut v)| (sf, top_pctile(&mut v)))
        .collect()
}

pub(super) fn paper_bm(
    sfs: &[ET<crate::gen::a1_entity_mapping::Subfields>],
    year: usize,
    sf_year_bms: &HashMap<(usize, usize), f64>,
    sf_bms: &HashMap<usize, f64>,
    year_bms: &[f64],
) -> f64 {
    if sfs.is_empty() {
        return year_bms[year];
    }
    let n = sfs.len() as f64;
    let yr_bm = year_bms[year];
    let sf_year_avg = sfs
        .iter()
        .map(|sf| *sf_year_bms.get(&(sf.to_usize(), year)).unwrap_or(&yr_bm))
        .sum::<f64>()
        / n;
    let sf_avg = sfs
        .iter()
        .map(|sf| *sf_bms.get(&sf.to_usize()).unwrap_or(&yr_bm))
        .sum::<f64>()
        / n;
    W_SF_YEAR * sf_year_avg + W_SF * sf_avg + W_YEAR * yr_bm
}

pub(super) fn get_limits<E, I, I2, U>(n: usize, it: I, ccs: &Box<[CCUI]>) -> Box<[CCUI]>
where
    E: Entity,
    I: Iterator<Item = I2>,
    I2: Iterator<Item = U>,
    U: UnsignedNumber,
{
    let mut count_heaps = init_empty_slice::<E, BinaryHeap<CCUI>>();
    it.enumerate().for_each(|(wid, atts)| {
        atts.for_each(|a| count_heaps[a.to_usize()].push(ccs[wid]));
    });
    count_heaps
        .to_vec()
        .into_iter()
        .map(|e| topn(e, n))
        .collect::<Vec<CCUI>>()
        .into()
}

fn topn(mut h: BinaryHeap<CCUI>, n: usize) -> CCUI {
    let mut out = CCUI::MAX;
    for _ in 0..n {
        match h.pop() {
            Some(e) => out = e,
            None => break,
        }
    }
    out
}

pub(super) fn top_pctile(ccs: &mut Vec<CCUI>) -> f64 {
    if ccs.is_empty() {
        return 0.0;
    }
    ccs.sort_unstable_by(|a, b| b.cmp(a));
    let top_n = ((ccs.len() as f64 * TOP_PCTILE).ceil() as usize)
        .max(1)
        .min(ccs.len());
    ccs[top_n - 1].to_usize() as f64
}
