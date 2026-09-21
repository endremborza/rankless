use std::fmt::Display;

use serde::Serialize;

use crate::env_consts::{
    FINAL_YEAR, MIN_AUTHOR_CITE_COUNT, MIN_AUTHOR_WORK_COUNT, MIN_PAPERS_FOR_INST,
    MIN_PAPERS_FOR_SOURCE, START_YEAR,
};

// Exponent of the paper-count divisor under the impact score. The score is a weighted geometric
// mean of an entity's hit-paper count and its hit rate, three parts the count to one part the
// rate; the exponent is the rate's weight.
pub const IMPACT_BETA: f64 = 0.25;

// Exponent of the entity-size divisor under the field score. Equal to `peers::SPEC_BETA` today and
// free to move without it: that one divides by a field's size, this one by an entity's.
pub const FIELD_SCORE_BETA: f64 = 0.75;

// The hit-paper rule and the work screen, stated once: `steps::derive_links3` and `filter` read
// these values, `/v1/methodology` serves them, and the site and the MCP render what is served.
pub const HIT_RULE: HitRule = {
    let w_sf = 0.005;
    let w_year = 0.12;
    HitRule {
        min_needed: 10,
        min_universal: 500,
        top_topic: 3,
        top_pctile: 0.01,
        score_threshold: 1.5,
        nobel_multiplier: 2.0,
        w_sf,
        w_year,
        w_sf_year: 1.0 - w_sf - w_year,
        sf_year_min_papers: 400,
        creator_cutoff_year: 2000,
        min_creator_citations: 50,
    }
};

pub const WORK_SCREEN: WorkScreen = WorkScreen {
    kinds: &[
        "article",
        "book",
        "review",
        // Proceedings series carry both labels, depending on snapshot vintage.
        "book-chapter",
        "conference-paper",
    ],
    min_citations: 1,
    max_authors: 20,
    start_year: START_YEAR,
    final_year: FINAL_YEAR,
    min_papers_for_institution: MIN_PAPERS_FOR_INST,
    min_papers_for_source: MIN_PAPERS_FOR_SOURCE,
    min_author_papers: MIN_AUTHOR_WORK_COUNT,
    min_author_citations: MIN_AUTHOR_CITE_COUNT,
};

pub const METHODOLOGY: Methodology = Methodology {
    work_screen: WORK_SCREEN,
    hit_rule: HIT_RULE,
};

// What admits one of an entity's papers as a hit paper, and so the definition behind the
// hit-paper count, the hit rate and the impact score.
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HitRule {
    // Citations every hit paper has, whichever way it qualifies.
    pub min_needed: usize,
    // Citations that qualify a paper on their own.
    pub min_universal: usize,
    // A paper among this many most cited of one of its topics qualifies.
    pub top_topic: usize,
    // The benchmark is the citation count that enters this top share of a group.
    pub top_pctile: f64,
    // Multiple of its benchmark that qualifies a paper.
    pub score_threshold: f64,
    // Applied to a paper's multiple when it is no later than a Nobel year of one of its authors.
    pub nobel_multiplier: f64,
    // Weights of the subfield, the year and the subfield-year benchmarks blended into a paper's.
    pub w_sf: f64,
    pub w_year: f64,
    pub w_sf_year: f64,
    // A subfield-year group smaller than this has no benchmark of its own and takes the year's.
    pub sf_year_min_papers: usize,
    // A topic's earliest paper qualifies as its creator only for a topic first seen in this year
    // or later: the start of the data would otherwise manufacture originators for old topics.
    pub creator_cutoff_year: u16,
    // Citations a creator needs: below the benchmark bar so genuine originators are admitted,
    // above `min_needed`.
    pub min_creator_citations: usize,
}

// The screen that decides which papers enter the data at all. A citation is indexed exactly when
// the citing paper is, so one object answers both. The year window and the per-entity minimums are
// `env_consts`, generated per build environment, which is why no text can state them without
// reading them.
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkScreen {
    pub kinds: &'static [&'static str],
    pub min_citations: usize,
    pub max_authors: usize,
    pub start_year: u16,
    pub final_year: u16,
    pub min_papers_for_institution: u16,
    pub min_papers_for_source: u16,
    pub min_author_papers: u16,
    pub min_author_citations: u16,
}

// Every definition the site publishes about how its numbers are made, in one payload.
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct Methodology {
    pub work_screen: WorkScreen,
    pub hit_rule: HitRule,
}

// One breakdown level of a tree: the attribute entity and the side of the citation link it sits
// on. A tree's first level is a profile of the root entity, identified by this alone.
#[derive(Serialize, Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Level {
    #[serde(rename = "attributeType")]
    pub entity: &'static str,
    #[serde(rename = "sourceSide")]
    pub source_side: bool,
}

impl WorkScreen {
    // The year and retraction screen. A pinned owner's œuvre rides through the kind screen below
    // but not through this one. `>` on the start year because 0 is "unknown".
    pub fn admits_publication(&self, retracted: bool, year: u16) -> bool {
        !retracted && year > self.start_year && year <= self.final_year
    }

    pub fn admits_kind(&self, kind: Option<&str>) -> bool {
        self.kinds.contains(&kind.unwrap_or(""))
    }

    pub fn admits_authorship(&self, authors: usize) -> bool {
        authors <= self.max_authors
    }
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
