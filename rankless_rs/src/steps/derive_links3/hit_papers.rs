use dmove::{UnsignedNumber, ET, MAA};
use hashbrown::HashMap;

use crate::{
    common::init_empty_slice, gen::a1_entity_mapping::Works, metrics::PAPER_SCORE,
    steps::a1_entity_mapping::Years, CiteCountMarker,
};

pub(super) type CCUI = ET<MAA<Works, CiteCountMarker>>;

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
            let bm = if v.len() >= PAPER_SCORE.sf_year_min_papers {
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
    PAPER_SCORE.w_sf_year * sf_year_avg + PAPER_SCORE.w_sf * sf_avg + PAPER_SCORE.w_year * yr_bm
}

pub(super) fn top_pctile(ccs: &mut Vec<CCUI>) -> f64 {
    if ccs.is_empty() {
        return 0.0;
    }
    ccs.sort_unstable_by(|a, b| b.cmp(a));
    let top_n = ((ccs.len() as f64 * PAPER_SCORE.top_share).ceil() as usize)
        .max(1)
        .min(ccs.len());
    ccs[top_n - 1].to_usize() as f64
}
