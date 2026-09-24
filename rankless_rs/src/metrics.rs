use std::fmt::Display;

use serde::Serialize;

use crate::env_consts::{
    FINAL_YEAR, MIN_AUTHOR_CITE_COUNT, MIN_AUTHOR_WORK_COUNT, MIN_PAPERS_FOR_INST,
    MIN_PAPERS_FOR_SOURCE, START_YEAR,
};

// Exponent of the entity-size divisor under the field score. Equal to `peers::SPEC_BETA` today and
// free to move without it: that one divides by a field's size, this one by an entity's.
pub const FIELD_SCORE_BETA: f64 = 0.75;

// The paper score and the work screen, stated once: the pipeline steps and `filter` read these
// values, `/v1/methodology` serves them, and every text about them is a template `fill` completes
// from them, so no text restates a number.
pub const PAPER_SCORE: PaperScore = {
    let w_sf = 0.005;
    let w_year = 0.1;
    PaperScore {
        top_share: 0.01,
        w_sf,
        w_year,
        w_sf_year: 1.0 - w_sf - w_year,
        sf_year_min_papers: 400,
        hit_multiple: 1.5,
        bar_scale: 4,
    }
};

// Papers a root type's Top-N mean averages over, keyed by entity name: this module compiles with
// every pipeline step, before the entity types are generated.
pub const TOP_N: &[(&str, usize)] = &[
    ("sources", 1000),
    ("institutions", 2000),
    ("countries", 2000),
    ("authors", 20),
];

// Publication years the recent h-indices count from.
pub const H_SINCE: [u16; 2] = [2010, 2020];

// The last publication year with paper scores: in the final year, when a paper appeared would
// weigh more than how it is cited.
pub const LAST_SCORED_YEAR: u16 = FINAL_YEAR - 1;

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
    // Year index 0 is START_YEAR and stands for an unknown year, so the screen opens after it.
    first_year: START_YEAR + 1,
    final_year: FINAL_YEAR,
    min_papers_for_institution: MIN_PAPERS_FOR_INST,
    min_papers_for_source: MIN_PAPERS_FOR_SOURCE,
    min_author_papers: MIN_AUTHOR_WORK_COUNT,
    min_author_citations: MIN_AUTHOR_CITE_COUNT,
};

pub const PAPER_SCORE_TEXTS: Texts = Texts {
    id: "paper_score",
    label: "Paper score",
    meaning: "A paper's citations measured against the top-{top_share} bar of its own field and year: the square root of citations ÷ bar, so 1 means right at the bar and 2 means four times its citations. The bar blends the citation counts that enter the top {top_share} of the paper's subfields in its year (weighted {w_sf_year}), of those subfields over all years ({w_sf}) and of its year across all fields ({w_year}); a subfield and year with fewer than {sf_year_min_papers} papers takes its year's bar. Papers from {final_year} are not scored yet: in an unfinished year, when a paper appeared matters more than how it is cited.",
    rationale: Some("Citation counts differ by field and grow with a paper's age, so a paper is read against papers of its own field and year. {w_year} of the bar comes from the year across all fields, which keeps some of the difference between fields on purpose."),
};

pub const HIT_PAPER_TEXTS: Texts = Texts {
    id: "hit_paper",
    label: "Hit paper",
    meaning: "A paper cited at least {hit_multiple}× the top-{top_share} bar of its field and year: a paper score of at least √{hit_multiple}.",
    rationale: Some("A threshold on the paper score alone, so a hit paper means the same in every field and year."),
};

pub const METHODOLOGY: Methodology = Methodology {
    work_screen: WORK_SCREEN,
    paper_score: PAPER_SCORE,
    top_n: TOP_N,
    h_since: H_SINCE,
};

// A bar as stored: whole units of `1 / bar_scale` citations, 0 for a paper without a score.
pub type EncodedBar = u16;

// What a paper's score measures it against, and the score that makes it a hit paper.
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PaperScore {
    // The bar is the citation count that enters this top share of a group.
    pub top_share: f64,
    // Weights of the subfield, the year and the subfield-year bars blended into a paper's.
    pub w_sf: f64,
    pub w_year: f64,
    pub w_sf_year: f64,
    // A subfield-year group smaller than this has no bar of its own and takes the year's.
    pub sf_year_min_papers: usize,
    // Multiple of its bar a paper's citations reach to make it a hit paper.
    pub hit_multiple: f64,
    // A stored bar counts citations in units of 1 / this.
    pub bar_scale: u16,
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
    pub first_year: u16,
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
    pub paper_score: PaperScore,
    pub top_n: &'static [(&'static str, usize)],
    pub h_since: [u16; H_SINCE.len()],
}

// What one published item means and why it is defined that way, as templates over the constants.
#[derive(Clone, Copy)]
pub struct Texts {
    pub id: &'static str,
    pub label: &'static str,
    pub meaning: &'static str,
    pub rationale: Option<&'static str>,
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

// One paper as the score-based metrics read it. `team` counts the paper's members of the kind
// being scored: its authors, institutions or countries.
#[derive(Clone, Copy)]
pub struct Paper {
    pub citations: u32,
    pub bar: EncodedBar,
    pub year: u16,
    pub team: usize,
}

// What the score-based metrics read from a set of papers.
pub struct PaperSetSummary {
    pub scored: u32,
    pub weighted: f64,
    pub top_mean: f64,
    pub h_index: u32,
    pub h_since: [u32; H_SINCE.len()],
}

impl WorkScreen {
    // The year and retraction screen. A pinned owner's œuvre rides through the kind screen below
    // but not through this one.
    pub fn admits_publication(&self, retracted: bool, year: u16) -> bool {
        !retracted && (self.first_year..=self.final_year).contains(&year)
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

pub fn is_scored(year: u16) -> bool {
    (WORK_SCREEN.first_year..=LAST_SCORED_YEAR).contains(&year)
}

/// Fails the build on a bar the encoding cannot hold rather than clipping it.
pub fn encode_bar(bar: f64) -> EncodedBar {
    let units = (bar * PAPER_SCORE.bar_scale as f64).round();
    assert!(
        units >= 0.0 && units <= EncodedBar::MAX as f64,
        "bar {bar} outside the encoding"
    );
    units as EncodedBar
}

pub fn decode_bar(bar: EncodedBar) -> f64 {
    bar as f64 / PAPER_SCORE.bar_scale as f64
}

/// `√(citations / bar)`, None for an unscored paper.
pub fn paper_score(citations: u32, bar: EncodedBar) -> Option<f64> {
    (bar != 0).then(|| (citations as f64 / decode_bar(bar)).sqrt())
}

pub fn is_hit(score: f64) -> bool {
    score >= PAPER_SCORE.hit_multiple.sqrt()
}

/// The part of a paper's score each of its `n` members is credited with: shared, but on a softened
/// scale so large collaborations are not divided away.
pub fn team_share(n: usize) -> f64 {
    1.0 / (1.0 + (n.max(1) as f64).ln())
}

pub fn top_n(root: &str) -> Option<usize> {
    TOP_N.iter().find(|(r, _)| *r == root).map(|(_, n)| *n)
}

/// Mean of the `n` best scores, missing papers counting as zero.
pub fn top_n_mean(scores: &mut [f64], n: usize) -> f64 {
    if n == 0 {
        return 0.0;
    }
    let k = n.min(scores.len());
    if k < scores.len() {
        scores.select_nth_unstable_by(k, |a, b| b.total_cmp(a));
    }
    scores[..k].iter().sum::<f64>() / n as f64
}

/// Largest h such that h of the papers have at least h citations each.
pub fn h_index(citations: &mut [u32]) -> u32 {
    citations.sort_unstable_by(|a, b| b.cmp(a));
    h_of_sorted(citations.iter().copied())
}

/// One pass over a set of papers for every score-based metric; `n` is the Top-N mean's N (0 for a
/// root without one).
pub fn summarize(papers: impl Iterator<Item = Paper>, n: usize) -> PaperSetSummary {
    let (mut scored, mut weighted) = (0, 0.0);
    let mut scores = Vec::new();
    let mut cites = Vec::new();
    for p in papers {
        cites.push((p.year, p.citations));
        if let Some(s) = paper_score(p.citations, p.bar) {
            scored += 1;
            weighted += s * team_share(p.team);
            scores.push(s);
        }
    }
    cites.sort_unstable_by(|a, b| b.1.cmp(&a.1));
    let since = |from: u16| h_of_sorted(cites.iter().filter(|(y, _)| *y >= from).map(|(_, c)| *c));
    PaperSetSummary {
        scored,
        weighted,
        top_mean: top_n_mean(&mut scores, n),
        h_index: h_of_sorted(cites.iter().map(|(_, c)| *c)),
        h_since: H_SINCE.map(since),
    }
}

/// The values a text template names as `{name}`, formatted as the texts show them.
pub fn text_vars() -> Vec<(&'static str, String)> {
    let p = &PAPER_SCORE;
    vec![
        ("top_share", percent(p.top_share)),
        ("w_sf_year", percent(p.w_sf_year)),
        ("w_sf", percent(p.w_sf)),
        ("w_year", percent(p.w_year)),
        ("sf_year_min_papers", p.sf_year_min_papers.to_string()),
        ("hit_multiple", decimal(p.hit_multiple)),
        ("first_year", WORK_SCREEN.first_year.to_string()),
        ("final_year", WORK_SCREEN.final_year.to_string()),
        ("last_scored_year", LAST_SCORED_YEAR.to_string()),
    ]
}

/// The template with every `{name}` it has a value for replaced; any other brace is left for the
/// client, which fills a parameterized header's argument.
pub fn fill(template: &str, vars: &[(&str, String)]) -> String {
    let mut out = String::with_capacity(template.len());
    let mut rest = template;
    while let Some(open) = rest.find('{') {
        out.push_str(&rest[..open]);
        let tail = &rest[open + 1..];
        let value = tail.find('}').and_then(|close| {
            let name = &tail[..close];
            vars.iter()
                .find(|(k, _)| *k == name)
                .map(|(_, v)| (v, close))
        });
        match value {
            Some((v, close)) => {
                out.push_str(v);
                rest = &tail[close + 1..];
            }
            None => {
                out.push('{');
                rest = tail;
            }
        }
    }
    out.push_str(rest);
    out
}

// The h-index of citations already in descending order; a filtered prefix stays descending.
fn h_of_sorted(descending: impl Iterator<Item = u32>) -> u32 {
    descending
        .enumerate()
        .take_while(|&(i, c)| c as usize > i)
        .count() as u32
}

fn decimal(x: f64) -> String {
    let s = format!("{:.4}", x);
    s.trim_end_matches('0').trim_end_matches('.').to_string()
}

fn percent(x: f64) -> String {
    format!("{}%", decimal(x * 100.0))
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
/// entity's own size, so this score needs the dampener.
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

    #[test]
    fn the_bar_round_trips_to_its_unit_and_overflow_fails() {
        assert_eq!(decode_bar(encode_bar(6.6)), 6.5);
        assert_eq!(decode_bar(encode_bar(6.7)), 6.75);
        assert_eq!(decode_bar(encode_bar(1788.0)), 1788.0);
        let max = EncodedBar::MAX as f64 / PAPER_SCORE.bar_scale as f64;
        assert_eq!(decode_bar(encode_bar(max)), max);
        assert!(std::panic::catch_unwind(|| encode_bar(max + 1.0)).is_err());
    }

    #[test]
    fn only_finished_years_inside_the_screen_are_scored() {
        assert!(!is_scored(WORK_SCREEN.first_year - 1));
        assert!(is_scored(WORK_SCREEN.first_year));
        assert!(is_scored(WORK_SCREEN.final_year - 1));
        assert!(!is_scored(WORK_SCREEN.final_year));
    }

    #[test]
    fn the_score_is_the_root_of_citations_over_the_bar() {
        assert_eq!(paper_score(400, encode_bar(100.0)), Some(2.0));
        assert_eq!(paper_score(100, encode_bar(100.0)), Some(1.0));
        assert_eq!(paper_score(0, encode_bar(100.0)), Some(0.0));
        assert_eq!(paper_score(100, 0), None);
    }

    #[test]
    fn a_hit_is_at_least_the_multiple_of_the_bar() {
        let bar = encode_bar(4.0);
        assert!(is_hit(paper_score(6, bar).unwrap()));
        assert!(!is_hit(paper_score(5, bar).unwrap()));
        let quarter = encode_bar(6.75);
        let at = (6.75 * PAPER_SCORE.hit_multiple).ceil() as u32;
        assert!(is_hit(paper_score(at, quarter).unwrap()));
        assert!(!is_hit(paper_score(at - 1, quarter).unwrap()));
    }

    #[test]
    fn a_single_member_keeps_the_whole_score() {
        assert_eq!(team_share(1), 1.0);
        assert_eq!(team_share(0), 1.0);
        assert!((team_share(3) - 1.0 / (1.0 + 3f64.ln())).abs() < 1e-12);
    }

    #[test]
    fn missing_papers_count_as_zero_in_the_top_mean() {
        assert_eq!(top_n_mean(&mut [4.0, 2.0], 4), 1.5);
        assert_eq!(top_n_mean(&mut [1.0, 5.0, 3.0, 2.0], 2), 4.0);
        assert_eq!(top_n_mean(&mut [], 20), 0.0);
        assert_eq!(top_n_mean(&mut [3.0], 0), 0.0);
    }

    #[test]
    fn h_counts_papers_cited_at_least_their_rank() {
        assert_eq!(h_index(&mut [3, 3, 2]), 2);
        assert_eq!(h_index(&mut [0]), 0);
        assert_eq!(h_index(&mut []), 0);
        assert_eq!(h_index(&mut [1]), 1);
        assert_eq!(h_index(&mut [10, 8, 5, 4, 3]), 4);
        assert_eq!(h_index(&mut [25, 8, 5, 3, 3]), 3);
    }

    #[test]
    fn a_summary_reads_every_metric_in_one_pass() {
        let bar = encode_bar(100.0);
        let papers = [
            Paper {
                citations: 400,
                bar,
                year: 2015,
                team: 1,
            },
            Paper {
                citations: 100,
                bar,
                year: 2005,
                team: 3,
            },
            Paper {
                citations: 150,
                bar,
                year: 2021,
                team: 1,
            },
            Paper {
                citations: 9,
                bar: 0,
                year: WORK_SCREEN.final_year,
                team: 1,
            },
        ];
        let s = summarize(papers.into_iter(), 2);
        let s150 = 1.5f64.sqrt();
        assert_eq!(s.scored, 3);
        assert!((s.weighted - (2.0 + team_share(3) + s150)).abs() < 1e-12);
        assert!((s.top_mean - (2.0 + s150) / 2.0).abs() < 1e-12);
        assert_eq!(s.h_index, 4);
        assert_eq!(s.h_since, [3, 2]);
    }

    #[test]
    fn a_template_takes_the_constants_and_leaves_a_parameter() {
        let vars = text_vars();
        assert_eq!(
            fill("{hit_multiple}× the top {top_share}", &vars),
            "1.5× the top 1%"
        );
        assert_eq!(fill("{subfield} score", &vars), "{subfield} score");
        assert_eq!(fill("{w_sf_year} {w_year}", &vars), "89.5% 10%");
        assert_eq!(fill("a { b", &vars), "a { b");
    }

    #[test]
    fn the_methodology_texts_resolve_every_placeholder() {
        let vars = text_vars();
        for t in [PAPER_SCORE_TEXTS, HIT_PAPER_TEXTS] {
            for text in [t.label, t.meaning, t.rationale.unwrap_or("")] {
                assert!(!fill(text, &vars).contains('{'), "{}: {text}", t.id);
            }
        }
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
