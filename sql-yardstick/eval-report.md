# Reproduction Eval Report

**2026-02-21 15:14** | 163 comparisons, 0 errors

## Summary

| Metric | Value |
|--------|-------|
| n_comparisons | 163 |
| n_errors | 0 |
| total_flask_time | 1145.0s |
| total_rs_time | 25.1s |
| total_duration_ratio | 45.7x |
| mean_pearson_lc | 0.997 |
| mean_pearson_sc | 0.996 |
| mean_relerr_lc | 0.3% |
| mean_relerr_sc | 0.2% |
| total_n_missing | 784 |
| mean_ts_id_match | 83.7% |
| mean_ts_link_relerr | 0.1% |

## By root type x breakdown

| Root | Breakdown | N | PG/RS | r(LC) | r(SC) | err(LC) | err(SC) | Miss | TopID% | TopLnkErr |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| institutions | countries-T;institutions-T;subfields-T;topics-T | 13 | 58.4x | 1.000 | 1.000 | 0.0% | 0.0% | 0 | 63% | 0.0% |
| countries | countries-T;subfields-T;institutions-T | 10 | 32.0x | 1.000 | 1.000 | 0.0% | 0.0% | 0 | 65% | 0.0% |
| countries | subfields-T | 10 | 10.3x | 1.000 | 1.000 | 0.0% | 0.0% | 0 | 93% | 0.0% |
| institutions | subfields-S;countries-T;institutions-T;subfields-T | 13 | 34.2x | 1.000 | 1.000 | 0.0% | 0.0% | 14 | 74% | 0.0% |
| sources | countries-S;institutions-S;subfields-S | 7 | 34.8x | 1.000 | 1.000 | 0.0% | 0.0% | 0 | 98% | 0.0% |
| subfields | countries-T;subfields-T;topics-T | 13 | 95.8x | 1.000 | 1.000 | 0.0% | 0.0% | 0 | 64% | 0.0% |
| institutions | subfields-S;subfields-T;topics-T | 13 | 24.4x | 1.000 | 1.000 | 0.0% | 0.0% | 0 | 79% | 0.0% |
| subfields | subfields-T | 13 | 9.5x | 1.000 | 1.000 | 0.0% | 0.0% | 0 | 95% | 0.0% |
| subfields | countries-S | 13 | 43.5x | 1.000 | 1.000 | 0.0% | 0.1% | 0 | 98% | 0.0% |
| countries | subfields-S | 10 | 10.0x | 1.000 | 1.000 | 0.0% | 0.1% | 0 | 97% | 0.0% |
| subfields | topics-S;countries-S;institutions-S | 13 | 56.8x | 1.000 | 1.000 | 0.1% | 0.1% | 17 | 96% | 0.0% |
| institutions | countries-S;subfields-S;institutions-S | 13 | 51.6x | 0.979 | 0.979 | 0.2% | 0.3% | 0 | 96% | 0.1% |
| countries | institutions-S;subfields-S;countries-T;institutions-T | 10 | 55.4x | 1.000 | 1.000 | 0.6% | 0.6% | 687 | 85% | 0.0% |
| subfields | sources-S;countries-S;institutions-S | 3 | 85.4x | 1.000 | 1.000 | 1.1% | 1.1% | 34 | 97% | 0.0% |
| institutions | subfields-T;sources-T;topics-T | 1 | 20.0x | 0.995 | 0.997 | 1.6% | 1.4% | 0 | 44% | 1.0% |
| sources | sources-T;countries-T;subfields-T | 1 | 68.9x | 1.000 | 1.000 | 1.7% | 1.7% | 22 | 57% | 0.1% |
| sources | subfields-S;countries-T;institutions-T;sources-T | 3 | 70.3x | 0.970 | 0.951 | 3.0% | 2.3% | 0 | 80% | 2.0% |
| institutions | subfields-S;countries-T;institutions-T;sources-T | 4 | 58.0x | 0.963 | 0.955 | 3.4% | 2.7% | 10 | 70% | 2.1% |

## Timing

| Backend | Total (s) |
|---------|-----------|
| Flask (PG) | 1145.0 |
| Rust | 25.1 |
| Ratio (PG/RS) | 45.7x |

![Response time scaling](timing-plot.png)

## Memory Usage

| Metric | Rust | Flask (PG) |
|--------|------|------------|
| Peak (MiB) | 768 | 3175 |
| Mean (MiB) | 528 | 945 |
| Samples | 505 | — |

![Memory usage over time](memory-plot.png)

