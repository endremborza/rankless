// Citation-rank breakpoint ladder layout (one row per subfield, one table per cohort entity type):
//   [0..LADDER_LEN] = citation value at each percentile band (LADDER_PCT_BANDS), computed over the
//                     cohort of entities active in that subfield.
// u32::MAX in any slot means "not applicable" (cohort empty in that subfield).
pub const LADDER_PCT_BANDS: [f64; 11] = [
    0.20, 0.10, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001, 0.0005, 0.0002, 0.0001,
];
pub const LADDER_LEN: usize = LADDER_PCT_BANDS.len();

/// For each subfield, the citation-value thresholds at the configured percentile bands, computed
/// over the cohort of entities active in that subfield (nonzero count).
/// Returns one row per subfield index (`D` == `Subfields::N`).
pub fn compute_cit_rank_ladder<const D: usize>(cit_sfs: &[[u32; D]]) -> Vec<[u32; LADDER_LEN]> {
    let mut out = Vec::with_capacity(D);
    let mut buf: Vec<u32> = Vec::new();
    for s in 0..D {
        buf.clear();
        buf.extend(cit_sfs.iter().map(|row| row[s]).filter(|&c| c > 0));
        buf.sort_unstable_by(|a, b| b.cmp(a)); // descending
        let n_s = buf.len();
        let mut row = [u32::MAX; LADDER_LEN];
        if n_s > 0 {
            for (k, &p) in LADDER_PCT_BANDS.iter().enumerate() {
                let rank = ((p * n_s as f64).ceil() as usize).clamp(1, n_s);
                row[k] = buf[rank - 1];
            }
        }
        out.push(row);
    }
    out
}
