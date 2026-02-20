# Reproduction Eval Report

**2026-02-20 15:52** | 20 comparisons, 12 errors

## Summary

| Metric | Value |
|--------|-------|
| n_comparisons | 20 |
| n_errors | 12 |
| total_flask_time | 38.3s |
| total_rs_time | 0.6s |
| total_duration_ratio | 62.6x |
| mean_pearson_lc | 0.989 |
| mean_pearson_sc | 0.986 |
| mean_relerr_lc | 0.5% |
| mean_relerr_sc | 0.4% |
| total_n_missing | 33 |
| mean_ts_id_match | 85.8% |
| mean_ts_link_relerr | 0.3% |

## By root type x breakdown

| Root | Breakdown | N | PG/RS | r(LC) | r(SC) | err(LC) | err(SC) | Miss | TopID% | TopLnkErr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| institutions | subfields-S;subfields-T;topics-T | 2 | 43.4x | 1.000 | 1.000 | 0.0% | 0.0% | 0 | 83% | 0.0% |
| subfields | countries-S | 2 | 43.8x | 1.000 | 1.000 | 0.0% | 0.0% | 0 | 100% | 0.0% |
| institutions | countries-T;institutions-T;subfields-T;topics-T | 2 | 82.2x | 1.000 | 1.000 | 0.0% | 0.0% | 0 | 72% | 0.0% |
| subfields | countries-T;subfields-T;topics-T | 2 | 117.5x | 1.000 | 1.000 | 0.0% | 0.0% | 0 | 63% | 0.0% |
| subfields | subfields-T | 2 | 15.1x | 1.000 | 1.000 | 0.0% | 0.0% | 0 | 89% | 0.0% |
| institutions | subfields-S;countries-T;institutions-T;subfields-T | 2 | 47.5x | 1.000 | 1.000 | 0.1% | 0.1% | 14 | 81% | 0.0% |
| sources | countries-S;institutions-S;subfields-S | 2 | 30.2x | 1.000 | 1.000 | 0.0% | 0.1% | 0 | 98% | 0.0% |
| subfields | topics-S;countries-S;institutions-S | 2 | 62.6x | 1.000 | 1.000 | 0.4% | 0.4% | 9 | 95% | 0.0% |
| institutions | countries-S;subfields-S;institutions-S | 2 | 54.2x | 0.938 | 0.916 | 0.4% | 0.4% | 0 | 97% | 0.1% |
| institutions | subfields-S;countries-T;institutions-T;sources-T | 1 | 83.8x | 0.952 | 0.955 | 3.3% | 2.3% | 10 | 83% | 2.3% |
| sources | subfields-S;countries-T;institutions-T;sources-T | 1 | 80.0x | 0.949 | 0.939 | 4.2% | 3.3% | 0 | 79% | 2.9% |

## Timing

| Backend | Total (s) |
|---------|-----------|
| Flask (PG) | 38.3 |
| Rust | 0.6 |
| Ratio (PG/RS) | 62.6x |

