use dmove::{UnsignedNumber, ET, MAA};
use hashbrown::HashMap;

use crate::{
    common::init_empty_slice,
    gen::a1_entity_mapping::{Subfields, Works},
    metrics::PAPER_SCORE,
    steps::a1_entity_mapping::Years,
    CiteCountMarker,
};

pub(super) type CCUI = ET<MAA<Works, CiteCountMarker>>;

pub(super) fn year_bars(w_years: &[ET<Years>], ccs: &[CCUI]) -> Box<[f64]> {
    let mut groups = init_empty_slice::<Years, Vec<CCUI>>();
    for (wid, yr) in w_years.iter().enumerate() {
        groups[yr.to_usize()].push(ccs[wid]);
    }
    groups
        .iter_mut()
        .map(|g| top_share_bar(g))
        .collect::<Vec<_>>()
        .into()
}

// A subfield-year with fewer papers than `sf_year_min_papers` takes its year's bar.
pub(super) fn sf_year_bars(
    w_sfs: &[Box<[ET<Subfields>]>],
    w_years: &[ET<Years>],
    ccs: &[CCUI],
    year_bars: &[f64],
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
            let bar = if v.len() >= PAPER_SCORE.sf_year_min_papers {
                top_share_bar(&mut v)
            } else {
                year_bars[yr]
            };
            ((sf, yr), bar)
        })
        .collect()
}

pub(super) fn sf_bars(w_sfs: &[Box<[ET<Subfields>]>], ccs: &[CCUI]) -> HashMap<usize, f64> {
    let mut groups: HashMap<usize, Vec<CCUI>> = HashMap::new();
    for (wid, sfs) in w_sfs.iter().enumerate() {
        for sf in sfs.iter() {
            groups.entry(sf.to_usize()).or_default().push(ccs[wid]);
        }
    }
    groups
        .into_iter()
        .map(|(sf, mut v)| (sf, top_share_bar(&mut v)))
        .collect()
}

// The blend of the paper's subfield-year, subfield and year bars, the first two averaged over its
// subfields; a paper with no subfield takes its year's bar alone.
pub(super) fn paper_bar(
    sfs: &[ET<Subfields>],
    year: usize,
    sf_year_bars: &HashMap<(usize, usize), f64>,
    sf_bars: &HashMap<usize, f64>,
    year_bars: &[f64],
) -> f64 {
    let year_bar = year_bars[year];
    if sfs.is_empty() {
        return year_bar;
    }
    let mean = |bar: &dyn Fn(usize) -> f64| {
        sfs.iter().map(|sf| bar(sf.to_usize())).sum::<f64>() / sfs.len() as f64
    };
    PAPER_SCORE.w_sf_year * mean(&|sf| sf_year_bars[&(sf, year)])
        + PAPER_SCORE.w_sf * mean(&|sf| sf_bars[&sf])
        + PAPER_SCORE.w_year * year_bar
}

// The citation count that enters the group's top share, 0 for an empty group.
pub(super) fn top_share_bar(ccs: &mut Vec<CCUI>) -> f64 {
    if ccs.is_empty() {
        return 0.0;
    }
    ccs.sort_unstable_by(|a, b| b.cmp(a));
    let top_n = ((ccs.len() as f64 * PAPER_SCORE.top_share).ceil() as usize)
        .max(1)
        .min(ccs.len());
    ccs[top_n - 1].to_usize() as f64
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cites(n: usize) -> Vec<CCUI> {
        (1..=n).map(|c| c as CCUI).collect()
    }

    #[test]
    fn the_bar_is_the_count_entering_the_top_share() {
        assert_eq!(top_share_bar(&mut cites(100)), 100.0);
        assert_eq!(top_share_bar(&mut cites(250)), 248.0);
        assert_eq!(top_share_bar(&mut cites(3)), 3.0);
        assert_eq!(top_share_bar(&mut Vec::new()), 0.0);
    }

    #[test]
    fn a_sparse_subfield_year_takes_its_years_bar() {
        let full = PAPER_SCORE.sf_year_min_papers;
        let sparse = 3;
        let sf = |id: ET<Subfields>| -> Box<[ET<Subfields>]> { Box::new([id]) };
        let mut w_sfs = vec![sf(1); full];
        w_sfs.extend(vec![sf(2); sparse]);
        let w_years: Vec<ET<Years>> = vec![1; full + sparse];
        let ccs = cites(full + sparse);
        let years = year_bars(&w_years, &ccs);
        let by_sf_year = sf_year_bars(&w_sfs, &w_years, &ccs, &years);
        assert_eq!(years[1], top_share_bar(&mut cites(full + sparse)));
        assert_eq!(by_sf_year[&(1, 1)], top_share_bar(&mut cites(full)));
        assert_eq!(by_sf_year[&(2, 1)], years[1]);
    }

    #[test]
    fn a_papers_bar_blends_its_groups_and_falls_back_to_its_year() {
        let sf_year = HashMap::from([((1, 2), 10.0), ((3, 2), 20.0)]);
        let sf = HashMap::from([(1, 4.0), (3, 8.0)]);
        let years = [0.0, 0.0, 2.0];
        let p = &PAPER_SCORE;
        assert!((p.w_sf_year + p.w_sf + p.w_year - 1.0).abs() < 1e-12);
        let one = paper_bar(&[1], 2, &sf_year, &sf, &years);
        assert!((one - (p.w_sf_year * 10.0 + p.w_sf * 4.0 + p.w_year * 2.0)).abs() < 1e-12);
        let two = paper_bar(&[1, 3], 2, &sf_year, &sf, &years);
        assert!((two - (p.w_sf_year * 15.0 + p.w_sf * 6.0 + p.w_year * 2.0)).abs() < 1e-12);
        assert_eq!(paper_bar(&[], 2, &sf_year, &sf, &years), 2.0);
    }
}
