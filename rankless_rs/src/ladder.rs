// Citation-rank breakpoint ladder layout (one row per subfield, one table per cohort entity type):
//   [0..8]  = citation value at each percentile band (LADDER_PCT_BANDS)
//   [8..11] = citation value at each absolute rank (LADDER_ABS_RANKS), only when that rank is more
//             selective than the finest band (0.1%); otherwise u32::MAX.
// u32::MAX in any slot means "not applicable" (cohort too small for that band/rank).
pub const LADDER_PCT_BANDS: [f64; 8] = [0.20, 0.10, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001];
pub const LADDER_ABS_RANKS: [usize; 3] = [1000, 100, 10];
pub const LADDER_LEN: usize = LADDER_PCT_BANDS.len() + LADDER_ABS_RANKS.len();

/// For each subfield, the citation-value thresholds at the configured percentile bands and
/// absolute ranks, computed over the cohort of entities active in that subfield (nonzero count).
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
        for (k, &p) in LADDER_PCT_BANDS.iter().enumerate() {
            if n_s > 0 {
                let rank = ((p * n_s as f64).ceil() as usize).clamp(1, n_s);
                row[k] = buf[rank - 1];
            }
        }
        // Absolute ranks only when strictly more selective than the finest band (0.1%).
        let finest = *LADDER_PCT_BANDS.last().unwrap();
        for (k, &r) in LADDER_ABS_RANKS.iter().enumerate() {
            if (r as f64) < finest * n_s as f64 {
                row[LADDER_PCT_BANDS.len() + k] = buf[r - 1];
            }
        }
        out.push(row);
    }
    out
}
