use std::fmt::Display;

use serde::Serialize;

use crate::peers::SPEC_BETA;

// One breakdown level of a tree: the attribute entity and the side of the citation link it sits
// on. A tree's first level is a profile of the root entity, identified by this alone.
#[derive(Serialize, Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Level {
    #[serde(rename = "attributeType")]
    pub entity: &'static str,
    #[serde(rename = "sourceSide")]
    pub source_side: bool,
}

impl Level {
    pub const fn citing(entity: &'static str) -> Self {
        Self {
            entity,
            source_side: false,
        }
    }

    pub const fn refed(entity: &'static str) -> Self {
        Self {
            entity,
            source_side: true,
        }
    }
}

impl Display for Level {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let side = if self.source_side { "refed" } else { "citing" };
        write!(f, "{}-{side}", self.entity)
    }
}

/// The one size divisor behind every specialization score: `(size + mean_size)^SPEC_BETA`. Adding
/// the cohort mean flattens the divisor for anything far below average size, so a three-paper
/// entity (or a thousand-paper field) ranks by count where the exponent alone would let a tiny
/// divisor dominate; far above the mean it converges to the plain `size^SPEC_BETA`.
pub fn dampened_size(size: f64, mean_size: f64) -> f64 {
    (size + mean_size).powf(SPEC_BETA)
}

/// Entity-in-field (or entity-overall) score: citations over the entity's dampened paper count.
/// With every citation it is the impact score; with the citations from one field it ranks the
/// entities of a cohort inside that field.
pub fn size_adjusted_score(citations: u32, papers: u32, mean_papers: f64) -> f32 {
    (citations as f64 / dampened_size(papers as f64, mean_papers)) as f32
}

pub fn mean_of(counts: impl Iterator<Item = u32>) -> f64 {
    let (sum, n) = counts.fold((0u64, 0u64), |(s, n), c| (s + c as u64, n + 1));
    if n == 0 {
        0.0
    } else {
        sum as f64 / n as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rank_fields(counts: &[(usize, u32)], sizes: &[f64], mean: f64) -> Vec<usize> {
        let mut v: Vec<(usize, f64)> = counts
            .iter()
            .map(|&(s, c)| (s, c as f64 / dampened_size(sizes[s], mean)))
            .collect();
        v.sort_by(|a, b| b.1.total_cmp(&a.1));
        v.into_iter().map(|(s, _)| s).collect()
    }

    #[test]
    fn three_papers_in_a_tiny_field_do_not_outrank_three_hundred_in_a_big_one() {
        let sizes: [f64; 2] = [1_000.0, 1_000_000.0];
        let mean = 300_000.0;
        // The plain field-size divisor is what the dampening replaces: under it the tiny field wins.
        let raw = |s: usize, c: u32| c as f64 / sizes[s].powf(SPEC_BETA);
        assert!(raw(0, 3) > raw(1, 300));
        assert_eq!(rank_fields(&[(0, 3), (1, 300)], &sizes, mean), vec![1, 0]);
        // Real volume in the tiny field still ranks it first.
        assert_eq!(
            rank_fields(&[(0, 3_000), (1, 300)], &sizes, mean),
            vec![0, 1]
        );
    }

    #[test]
    fn field_score_is_size_adjusted_but_not_fooled_by_a_tiny_entity() {
        let mean = 20.0;
        let big_uni = size_adjusted_score(50_000, 100_000, mean);
        let institute = size_adjusted_score(20_000, 2_000, mean);
        assert!(institute > big_uni);
        let one_hit = size_adjusted_score(300, 3, mean);
        let productive = size_adjusted_score(3_000, 300, mean);
        assert!(productive > one_hit);
        let mega_hit = size_adjusted_score(30_000, 3, mean);
        assert!(mega_hit > productive);
    }

    #[test]
    fn hand_computed_fixture() {
        let mean = 20.0;
        let expected = 3_000.0 / (320.0f64).powf(SPEC_BETA);
        assert!((size_adjusted_score(3_000, 300, mean) as f64 - expected).abs() < 1e-3);
        assert_eq!(size_adjusted_score(0, 300, mean), 0.0);
        assert!((mean_of([10, 20, 30].into_iter()) - 20.0).abs() < f64::EPSILON);
        assert_eq!(mean_of(std::iter::empty()), 0.0);
    }

    #[test]
    fn a_level_names_its_entity_and_side() {
        assert_eq!(Level::citing("countries").to_string(), "countries-citing");
        assert_eq!(Level::refed("sources").to_string(), "sources-refed");
    }
}
