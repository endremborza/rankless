use std::fmt::Display;

use dmove::Entity;
use serde::Serialize;

use crate::{gen::a1_entity_mapping::Countries, peers::SPEC_BETA};

pub const CITATIONS: &str = "citations";
pub const PAPERS: &str = "papers";
pub const IMPACT_SCORE: &str = "impact_score";
pub const H_INDEX: &str = "h_index";
pub const YEAR_CENTROID: &str = "year_centroid";
pub const FIELD_CITATIONS: &str = "field_citations";
pub const FIELD_SCORE: &str = "field_score";
pub const WINDOW_PAPERS: &str = "window_papers";
pub const WINDOW_CITATIONS: &str = "window_citations";
pub const CITING_COUNTRY_SHARE: &str = "citing_country_share";

pub const PARAM_SUBFIELD: &str = "subfield";
pub const PARAM_YEAR_FROM: &str = "year_from";
pub const PARAM_YEAR_TO: &str = "year_to";
pub const PARAM_COUNTRY: &str = "country";

const G: MetricKind = MetricKind::Global;
const I: MetricKind = MetricKind::Intricate;

// One declaration per metric, the single source of its label, meaning text, parameters and kind per
// root type. `kinds` names the root types the metric exists for; a global metric is one number per
// entity held for the whole cohort (the server orders and narrows by it), an intricate one is
// computed for a page of ids on request and never orders the cohort. A metric with parameters
// names its column by them in `header`, `{param}` standing for the chosen value. A metric read off
// a tree's first level names that level in `profile`, and exists only for the roots whose trees
// yield it.
pub const METRICS: &[MetricDecl] = &[
    MetricDecl {
        id: CITATIONS,
        label: "Citations",
        header: None,
        meaning: "Citations received by the entity's indexed papers.",
        kinds: MetricKinds::all(G),
        params: &[],
        profile: None,
    },
    MetricDecl {
        id: PAPERS,
        label: "Papers",
        header: None,
        meaning: "Indexed papers produced by the entity.",
        kinds: MetricKinds::all(G),
        params: &[],
        profile: None,
    },
    MetricDecl {
        id: IMPACT_SCORE,
        label: "Impact score",
        header: None,
        meaning: "Citations relative to size, with a floor under the size so that a few papers cannot outrank a large body of work: citations ÷ (papers + the average paper count of the entity's kind)^0.75. A high score means more impact than size alone predicts.",
        kinds: MetricKinds::all(G),
        params: &[],
        profile: None,
    },
    MetricDecl {
        id: H_INDEX,
        label: "h-index",
        header: None,
        meaning: "Largest h such that h of the author's papers have at least h citations each.",
        kinds: MetricKinds::authors_only(G),
        params: &[],
        profile: None,
    },
    MetricDecl {
        id: YEAR_CENTROID,
        label: "Career centroid",
        header: None,
        meaning: "Mean publication year of the author's papers: where in time the career's output sits.",
        kinds: MetricKinds::authors_only(G),
        params: &[],
        profile: None,
    },
    MetricDecl {
        id: FIELD_CITATIONS,
        label: "Field citations",
        header: Some("{subfield} citations"),
        meaning: "Citations from papers in the chosen field.",
        kinds: MetricKinds::profiled(G, I),
        params: &[PARAM_SUBFIELD],
        profile: None,
    },
    MetricDecl {
        id: FIELD_SCORE,
        label: "Field score",
        header: Some("{subfield} score"),
        meaning: "Citations from papers in the chosen field, over the same size term as the impact score. Ranks the entities of one field by the attention they draw from it for their size. An entity's own page ranks its fields the other way round, by the field's size.",
        kinds: MetricKinds::profiled(G, I),
        params: &[PARAM_SUBFIELD],
        profile: None,
    },
    MetricDecl {
        id: WINDOW_PAPERS,
        label: "Papers in a year window",
        header: Some("Papers {year_from}–{year_to}"),
        meaning: "Indexed papers published in the year window. Yearly counts exist for recent years only, so an earlier start is moved up to the first counted year.",
        kinds: MetricKinds::all(I),
        params: &[PARAM_YEAR_FROM, PARAM_YEAR_TO],
        profile: None,
    },
    MetricDecl {
        id: WINDOW_CITATIONS,
        label: "Citations in a year window",
        header: Some("Citations {year_from}–{year_to}"),
        meaning: "Citations from papers published in the year window. Yearly counts exist for recent years only, so an earlier start is moved up to the first counted year.",
        kinds: MetricKinds::all(I),
        params: &[PARAM_YEAR_FROM, PARAM_YEAR_TO],
        profile: None,
    },
    MetricDecl {
        id: CITING_COUNTRY_SHARE,
        label: "Share cited from a country",
        header: Some("Cited from {country}"),
        meaning: "Share of the entity's citations that come from papers with an author in the chosen country; a paper with authors in several countries counts once for each of them.",
        kinds: MetricKinds::all(I),
        params: &[PARAM_COUNTRY],
        profile: Some(Level::citing(Countries::NAME)),
    },
];

#[derive(Serialize)]
pub struct MetricDecl {
    pub id: &'static str,
    pub label: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub header: Option<&'static str>,
    pub meaning: &'static str,
    pub kinds: MetricKinds,
    pub params: &'static [&'static str],
    #[serde(skip)]
    pub profile: Option<Level>,
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

#[derive(Serialize)]
pub struct MetricKinds {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub authors: Option<MetricKind>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub institutions: Option<MetricKind>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sources: Option<MetricKind>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub countries: Option<MetricKind>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub subfields: Option<MetricKind>,
    #[serde(rename = "hit-papers", skip_serializing_if = "Option::is_none")]
    pub hit_papers: Option<MetricKind>,
}

#[derive(Serialize, Clone, Copy, PartialEq, Eq, Debug)]
#[serde(rename_all = "lowercase")]
pub enum MetricKind {
    Global,
    Intricate,
}

impl MetricDecl {
    pub fn kind_for(&self, root_type: &str) -> Option<MetricKind> {
        self.kinds.for_root(root_type)
    }

    // The declared kind, withheld where the root has no tree yielding the metric's profile.
    pub fn kind_if(
        &self,
        root_type: &str,
        has_level: impl Fn(&str, Level) -> bool,
    ) -> Option<MetricKind> {
        self.kind_for(root_type)
            .filter(|_| self.profile.is_none_or(|l| has_level(root_type, l)))
    }

    // The declaration with its kinds resolved against the trees that exist, what `/v1/metrics` serves.
    pub fn resolved(&self, has_level: impl Fn(&str, Level) -> bool) -> Self {
        Self {
            kinds: self
                .kinds
                .map(|root, kind| kind.filter(|_| self.profile.is_none_or(|l| has_level(root, l)))),
            ..*self
        }
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

impl MetricKinds {
    pub fn map(&self, f: impl Fn(&str, Option<MetricKind>) -> Option<MetricKind>) -> Self {
        Self {
            authors: f("authors", self.authors),
            institutions: f("institutions", self.institutions),
            sources: f("sources", self.sources),
            countries: f("countries", self.countries),
            subfields: f("subfields", self.subfields),
            hit_papers: f("hit-papers", self.hit_papers),
        }
    }

    pub fn for_root(&self, root_type: &str) -> Option<MetricKind> {
        match root_type {
            "authors" => self.authors,
            "institutions" => self.institutions,
            "sources" => self.sources,
            "countries" => self.countries,
            "subfields" => self.subfields,
            "hit-papers" => self.hit_papers,
            _ => None,
        }
    }

    const fn all(k: MetricKind) -> Self {
        Self {
            authors: Some(k),
            institutions: Some(k),
            sources: Some(k),
            countries: Some(k),
            subfields: Some(k),
            hit_papers: Some(k),
        }
    }

    const fn authors_only(k: MetricKind) -> Self {
        Self {
            authors: Some(k),
            institutions: None,
            sources: None,
            countries: None,
            subfields: None,
            hit_papers: None,
        }
    }

    // Root types with a resident per-subfield citation profile; the author cohort is too large for
    // a per-request scan of it, so an author's field metrics are page-local.
    const fn profiled(others: MetricKind, authors: MetricKind) -> Self {
        Self {
            authors: Some(authors),
            institutions: Some(others),
            sources: Some(others),
            countries: Some(others),
            subfields: None,
            hit_papers: None,
        }
    }
}

pub fn metric(id: &str) -> Option<&'static MetricDecl> {
    METRICS.iter().find(|m| m.id == id)
}

pub fn metric_kind(id: &str, root_type: &str) -> Option<MetricKind> {
    metric(id).and_then(|m| m.kind_for(root_type))
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
    fn registry_kinds_are_declared_per_root() {
        assert_eq!(
            metric_kind(FIELD_SCORE, "authors"),
            Some(MetricKind::Intricate)
        );
        assert_eq!(
            metric_kind(FIELD_SCORE, "institutions"),
            Some(MetricKind::Global)
        );
        assert_eq!(metric_kind(FIELD_SCORE, "subfields"), None);
        assert_eq!(metric_kind(H_INDEX, "sources"), None);
        // Every root type the server keeps a cohort for is ordered by citations, hit papers included.
        assert_eq!(
            metric_kind(CITATIONS, "hit-papers"),
            Some(MetricKind::Global)
        );
        assert_eq!(metric_kind(FIELD_SCORE, "hit-papers"), None);
        assert_eq!(metric_kind(CITATIONS, "works"), None);
        for m in METRICS {
            assert!(!m.meaning.is_empty(), "{} has no meaning text", m.id);
        }
    }

    #[test]
    fn a_header_template_names_only_the_metric_s_parameters() {
        for m in METRICS {
            assert_eq!(m.header.is_some(), !m.params.is_empty(), "{}", m.id);
            for part in m.header.unwrap_or("").split('{').skip(1) {
                let (param, _) = part.split_once('}').expect("unclosed placeholder");
                assert!(m.params.contains(&param), "{}: {param}", m.id);
            }
        }
    }

    #[test]
    fn profile_metrics_exist_only_where_a_tree_yields_the_level() {
        let share = metric(CITING_COUNTRY_SHARE).unwrap();
        let level = share.profile.unwrap();
        assert_eq!(level.to_string(), "countries-citing");
        let has = |root: &str, l: Level| l == level && root != "sources";
        assert_eq!(share.kind_if("authors", has), Some(MetricKind::Intricate));
        assert_eq!(share.kind_if("sources", has), None);
        let resolved = share.resolved(has);
        assert_eq!(resolved.kinds.sources, None);
        assert_eq!(resolved.kinds.countries, Some(MetricKind::Intricate));
        // A metric without a profile is untouched by the predicate.
        let cit = metric(CITATIONS).unwrap();
        assert_eq!(
            cit.kind_if("sources", |_, _| false),
            Some(MetricKind::Global)
        );
    }
}
