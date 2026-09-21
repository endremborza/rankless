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

/// The impact score: hit papers over the paper count raised to `IMPACT_BETA`. A hit paper is one
/// of the entity's own, so the score is bounded by `papers^(1 - IMPACT_BETA)` — an entity cannot
/// outrank one many times its size on a single lucky paper, which is why this score needs no
/// cohort constant and no floor under the divisor.
pub fn impact_score(hit_papers: u32, papers: u32) -> f32 {
    (hit_papers as f64 / (papers.max(1) as f64).powf(IMPACT_BETA)) as f32
}

/// The one size divisor behind every specialization score: `(size + mean_size)^beta`. Adding the
/// cohort mean flattens the divisor for anything far below average size, so a three-paper entity
/// (or a thousand-paper field) ranks by count where the exponent alone would let a tiny divisor
/// dominate; far above the mean it converges to the plain `size^beta`.
pub fn dampened_size(size: f64, mean_size: f64, beta: f64) -> f64 {
    (size + mean_size).powf(beta)
}

/// Entity-in-field score: the citations one field sends, over the entity's dampened paper count.
/// Ranks the entities of a cohort inside that field. A citation count is unbounded by the
/// entity's own size, so unlike the impact score this one needs the dampener.
pub fn field_score(field_citations: u32, papers: u32, mean_papers: f64) -> f32 {
    (field_citations as f64 / dampened_size(papers as f64, mean_papers, FIELD_SCORE_BETA)) as f32
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

    // (name, papers, hit papers) as the production root held them, so the anchors below are the
    // real thing and not an illustration. An entity whose standing is not in dispute has to come
    // out where it belongs, and the two ways a size-adjusted score goes wrong each have their own
    // anchors: mega-journals and umbrella organisations pull the exponent down, review venues and
    // tiny elite institutes pull it up.
    const SOURCE_ANCHORS: &[(&str, u32, u32)] = &[
        ("Nature", 158_633, 11_033),
        ("Science", 115_327, 10_019),
        ("Cell", 20_401, 4_200),
        ("New England Journal of Medicine", 42_063, 4_743),
        ("PNAS", 146_995, 6_245),
        ("Chemical Reviews", 7_738, 2_645),
        ("The Lancet", 76_706, 3_243),
        ("Journal of the American Chemical Society", 172_960, 3_853),
        ("Physiological Reviews", 2_096, 645),
        ("Annual Review of Immunology", 1_385, 346),
        ("Lecture notes in computer science", 466_699, 1_259),
        ("PLoS ONE", 304_585, 1_078),
        ("Scientific Reports", 250_792, 846),
        ("IEEE Access", 95_474, 662),
    ];

    const INSTITUTION_ANCHORS: &[(&str, u32, u32)] = &[
        ("Harvard University", 496_227, 12_487),
        ("Stanford University", 330_892, 8_252),
        ("Howard Hughes Medical Institute", 75_477, 5_421),
        ("Massachusetts Institute of Technology", 228_538, 6_373),
        ("Chinese Academy of Sciences", 743_610, 6_527),
        ("University of Oxford", 282_010, 4_608),
        (
            "Centre National de la Recherche Scientifique",
            966_536,
            6_115,
        ),
        ("Whitehead Institute for Biomedical Research", 5_488, 595),
        ("American Cancer Society", 5_017, 248),
        ("Cochrane", 371, 7),
    ];

    // Of the assertions below only two can fail for a non-negative exponent, and together they pin
    // it to [0.20, 0.44]: Cell above PNAS from 0.20 (the `order[..3]` check) and Harvard above
    // HHMI up to 0.44 (the `order[0]` check). The trap groups never bind — a mega-journal's
    // crossover with Nature is negative, a review annual's is above 0.65, a small specialist's
    // above 0.63 — and that inertness is the point: it is the hit-paper numerator, not the choice
    // of anchors, that removed both traps. They are kept as the record of what was checked.
    const APEX: &[&str] = &["Nature", "Science", "Cell"];
    const MEGA_JOURNALS: &[&str] = &[
        "Lecture notes in computer science",
        "PLoS ONE",
        "Scientific Reports",
        "IEEE Access",
    ];
    const REVIEW_VENUES: &[&str] = &["Physiological Reviews", "Annual Review of Immunology"];
    const ELITE_INSTITUTIONS: &[&str] = &[
        "Harvard University",
        "Stanford University",
        "Howard Hughes Medical Institute",
        "Massachusetts Institute of Technology",
    ];
    const UMBRELLA_ORGS: &[&str] = &[
        "Chinese Academy of Sciences",
        "Centre National de la Recherche Scientifique",
    ];
    const SMALL_SPECIALISTS: &[&str] = &[
        "Whitehead Institute for Biomedical Research",
        "American Cancer Society",
        "Cochrane",
    ];

    fn ranked(anchors: &[(&'static str, u32, u32)]) -> Vec<&'static str> {
        let mut v: Vec<_> = anchors
            .iter()
            .map(|&(name, p, h)| (impact_score(h, p), name))
            .collect();
        v.sort_by(|a, b| b.0.total_cmp(&a.0));
        v.into_iter().map(|(_, name)| name).collect()
    }

    fn position(order: &[&str], name: &str) -> usize {
        order.iter().position(|n| *n == name).unwrap()
    }

    #[test]
    fn the_apex_journals_win() {
        let order = ranked(SOURCE_ANCHORS);
        assert_eq!(&order[..3], APEX);
        for lower in MEGA_JOURNALS.iter().chain(REVIEW_VENUES) {
            for apex in APEX {
                assert!(
                    position(&order, apex) < position(&order, lower),
                    "{apex} must outrank {lower}"
                );
            }
        }
    }

    #[test]
    fn neither_volume_nor_rate_alone_carries_an_institution() {
        let order = ranked(INSTITUTION_ANCHORS);
        assert_eq!(order[0], "Harvard University");
        for elite in ELITE_INSTITUTIONS {
            for lower in UMBRELLA_ORGS.iter().chain(SMALL_SPECIALISTS) {
                assert!(
                    position(&order, elite) < position(&order, lower),
                    "{elite} must outrank {lower}"
                );
            }
        }
    }

    #[test]
    fn a_small_entity_cannot_outrank_a_large_one_on_one_paper() {
        // Every paper a hit is the best an entity of its size can do, and that ceiling grows with
        // size: no floor under the divisor is needed to keep a three-paper entity out of the top.
        let perfect_but_tiny = impact_score(3, 3);
        assert!(perfect_but_tiny < impact_score(4_200, 20_401));
        assert!(impact_score(10, 10) < impact_score(100, 100));
        assert_eq!(impact_score(0, 500), 0.0);
        // Papers below one would divide by zero; an entity with a hit has at least one paper.
        assert_eq!(impact_score(1, 0), 1.0);
    }

    #[test]
    fn the_impact_score_is_a_weighted_geometric_mean_of_count_and_rate() {
        let (hits, papers) = (4_200u32, 20_401u32);
        let rate = hits as f64 / papers as f64;
        let blended = (hits as f64).powf(1.0 - IMPACT_BETA) * rate.powf(IMPACT_BETA);
        // The score is an f32, so the identity holds to that precision, not to f64's.
        assert!((impact_score(hits, papers) as f64 / blended - 1.0).abs() < 1e-6);
    }

    fn rank_fields(counts: &[(usize, u32)], sizes: &[f64], mean: f64) -> Vec<usize> {
        let mut v: Vec<(usize, f64)> = counts
            .iter()
            .map(|&(s, c)| {
                (
                    s,
                    c as f64 / dampened_size(sizes[s], mean, FIELD_SCORE_BETA),
                )
            })
            .collect();
        v.sort_by(|a, b| b.1.total_cmp(&a.1));
        v.into_iter().map(|(s, _)| s).collect()
    }

    #[test]
    fn three_papers_in_a_tiny_field_do_not_outrank_three_hundred_in_a_big_one() {
        let sizes: [f64; 2] = [1_000.0, 1_000_000.0];
        let mean = 300_000.0;
        // The plain field-size divisor is what the dampening replaces: under it the tiny field wins.
        let raw = |s: usize, c: u32| c as f64 / sizes[s].powf(FIELD_SCORE_BETA);
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
        let big_uni = field_score(50_000, 100_000, mean);
        let institute = field_score(20_000, 2_000, mean);
        assert!(institute > big_uni);
        let one_hit = field_score(300, 3, mean);
        let productive = field_score(3_000, 300, mean);
        assert!(productive > one_hit);
        let mega_hit = field_score(30_000, 3, mean);
        assert!(mega_hit > productive);
    }

    #[test]
    fn hand_computed_fixture() {
        let mean = 20.0;
        let expected = 3_000.0 / (320.0f64).powf(FIELD_SCORE_BETA);
        assert!((field_score(3_000, 300, mean) as f64 - expected).abs() < 1e-3);
        assert_eq!(field_score(0, 300, mean), 0.0);
        assert!((mean_of([10, 20, 30].into_iter()) - 20.0).abs() < f64::EPSILON);
        assert_eq!(mean_of(std::iter::empty()), 0.0);
    }

    #[test]
    fn a_level_names_its_entity_and_side() {
        assert_eq!(Level::citing("countries").to_string(), "countries-citing");
        assert_eq!(Level::refed("sources").to_string(), "sources-refed");
    }
}
