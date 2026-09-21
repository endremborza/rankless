//! The metrics: what can be computed from a root type's columns, each declared once with its
//! value type, its parameter, the columns it reads and the cost of one read. A root's registry —
//! which metrics exist for it and which are global — is derived from what its `RootColumns`
//! loaded: a metric exists where its columns do, and is global where those columns fit a
//! cohort-wide scan. Nothing about a root is typed here.

use dmove::UnsignedNumber;
use rankless_rs::{
    gen::a1_entity_mapping::{Cities, Countries, Institutions, Subfields},
    metrics::{field_score, Level},
    steps::{
        a1_entity_mapping::{RawYear, YearInterface, Years},
        derive_links2::{EraRec, MAX_YEAR, MIN_YEAR},
    },
};
use serde::Serialize;

use crate::interfacing::{Getters, RootColumns};

use dmove::{Entity, ET};

// Bytes a cohort-wide evaluation may read per request; a metric over larger columns is intricate.
pub const SCAN_BUDGET_BYTES: usize = 512 << 20;
pub const N_AFF_COUNTRIES: usize = 3;

pub const CITATIONS: &str = "citations";
pub const PAPERS: &str = "papers";
pub const IMPACT_SCORE: &str = "impact_score";
pub const HIT_PAPERS: &str = "hit_papers";
pub const HIT_RATE: &str = "hit_rate";
pub const H_INDEX: &str = "h_index";
pub const YEAR_CENTROID: &str = "year_centroid";
pub const FIELD_CITATIONS: &str = "field_citations";
pub const FIELD_SCORE: &str = "field_score";
pub const FIELD_SHARE: &str = "field_share";
pub const WINDOW_PAPERS: &str = "window_papers";
pub const WINDOW_CITATIONS: &str = "window_citations";
pub const CITED_FROM: &str = "cited_from";
pub const COUNTRY: &str = "country";
pub const CITY: &str = "city";

const READ: &[Column] = &[];

// One declaration per metric, the single source of its label, meaning, value type, parameter and
// the columns behind it. `header` names a parameterized metric's column, `{param}` standing for
// the argument's name.
pub const METRICS: &[MetricDecl] = &[
    MetricDecl {
        id: CITATIONS,
        label: "Citations",
        header: None,
        meaning: "Citations received by the entity's indexed papers.",
        value: ValueType::Count,
        param: None,
        reads: &[Column::Citations],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: PAPERS,
        label: "Papers",
        header: None,
        meaning: "Indexed papers produced by the entity.",
        value: ValueType::Count,
        param: None,
        reads: &[Column::Papers],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: HIT_PAPERS,
        label: "Hit papers",
        header: None,
        meaning: "Papers of the entity that clear the citation benchmark for their field and year.",
        value: ValueType::Count,
        param: None,
        reads: &[Column::HitPapers],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: HIT_RATE,
        label: "Hit rate",
        header: None,
        meaning: "Share of the entity's papers that are hit papers. It reads the rate alone, so a small specialist can top it; the impact score is the reading that also counts how many.",
        value: ValueType::Share,
        param: None,
        reads: &[Column::HitPapers, Column::Papers],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: IMPACT_SCORE,
        label: "Impact score",
        header: None,
        meaning: "Hit papers weighed against output: hit papers ÷ papers^0.25, which is three parts how many hit papers the entity has and one part what share of its papers they are. Neither sheer volume nor a handful of strong papers carries it alone, and a hit paper is one of the entity's own, so no small entity can win on a lucky paper.",
        value: ValueType::Score,
        param: None,
        reads: &[Column::ImpactScore],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: H_INDEX,
        label: "h-index",
        header: None,
        meaning: "Largest h such that h of the author's papers have at least h citations each.",
        value: ValueType::Count,
        param: None,
        reads: &[Column::HIndex],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: YEAR_CENTROID,
        label: "Career centroid",
        header: None,
        meaning: "Mean publication year of the author's papers: where in time the career's output sits.",
        value: ValueType::Year,
        param: None,
        reads: &[Column::YearCentroid],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: FIELD_CITATIONS,
        label: "Field citations",
        header: Some("{subfield} citations"),
        meaning: "Citations from papers in the chosen field.",
        value: ValueType::Count,
        param: Some(Param::Subfield),
        reads: &[Column::SubfieldCiting],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: FIELD_SCORE,
        label: "Field score",
        header: Some("{subfield} score"),
        meaning: "Citations from papers in the chosen field, over the entity's paper count dampened by the average paper count of its kind. Ranks the entities of one field by the attention they draw from it for their size. An entity's own page ranks its fields the other way round, by the field's size.",
        value: ValueType::Score,
        param: Some(Param::Subfield),
        reads: &[Column::SubfieldCiting, Column::Papers],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: FIELD_SHARE,
        label: "Field share",
        header: Some("{subfield} share"),
        meaning: "Share of the entity's citations that come from papers in the chosen field: how concentrated its impact is in the field, whatever its size.",
        value: ValueType::Share,
        param: Some(Param::Subfield),
        reads: &[Column::SubfieldCiting, Column::Citations],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: WINDOW_PAPERS,
        label: "Papers in a year window",
        header: Some("Papers {window}"),
        meaning: "Indexed papers published in the year window. Yearly counts exist for recent years only, so an earlier start is moved up to the first counted year.",
        value: ValueType::Count,
        param: Some(Param::Window),
        reads: &[Column::YearlyPapers],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: WINDOW_CITATIONS,
        label: "Citations in a year window",
        header: Some("Citations {window}"),
        meaning: "Citations from papers published in the year window. Yearly counts exist for recent years only, so an earlier start is moved up to the first counted year.",
        value: ValueType::Count,
        param: Some(Param::Window),
        reads: &[Column::YearlyCites],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: CITED_FROM,
        label: "Share cited from a country",
        header: Some("Cited from {country}"),
        meaning: "Share of the entity's citations that come from papers with an author in the chosen country; a paper with authors in several countries counts once for each of them.",
        value: ValueType::Share,
        param: Some(Param::Country),
        reads: READ,
        cost: Cost::Walk,
        profile: Some(Level::citing(Countries::NAME)),
    },
    MetricDecl {
        id: COUNTRY,
        label: "Country",
        header: None,
        meaning: "An institution's country; for any other entity, up to three countries of the institutions on its papers, the most frequent first.",
        value: ValueType::Entities(Countries::NAME),
        param: None,
        reads: &[Column::Countries],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: CITY,
        label: "City",
        header: None,
        meaning: "The city of an institution.",
        value: ValueType::Entity(Cities::NAME),
        param: None,
        reads: &[Column::City],
        cost: Cost::Read,
        profile: None,
    },
];

#[derive(Serialize)]
pub struct MetricDecl {
    pub id: &'static str,
    pub label: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub header: Option<&'static str>,
    pub meaning: &'static str,
    pub value: ValueType,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub param: Option<Param>,
    #[serde(skip)]
    pub reads: &'static [Column],
    pub cost: Cost,
    #[serde(skip)]
    pub profile: Option<Level>,
}

// A bound argument: the parameter's value resolved to what the reader needs.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Arg {
    None,
    Subfield(usize),
    Country(usize),
    Window(Option<RawYear>, Option<RawYear>),
}

// What a read yields: a number, one entity id, or up to three entity ids (0 = absent).
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Value {
    Num(f64),
    Id(u32),
    Ids([u32; N_AFF_COUNTRIES]),
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Kind {
    Global,
    Intricate,
}

// One read per entity is a column access; a walk opens the entity's tree.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Cost {
    Read,
    Walk,
}

// How a value reads and which operators fit it: numbers compare, entity values match.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize)]
#[serde(rename_all = "lowercase", tag = "type", content = "entity")]
pub enum ValueType {
    Count,
    Score,
    Share,
    Year,
    Entity(&'static str),
    Entities(&'static str),
}

// The argument a parameterized metric takes.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Param {
    Subfield,
    Country,
    Window,
}

// The columns of `RootColumns` a metric reads, named so a root's availability and scan size can
// be asked of its loaded columns.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Column {
    Papers,
    Citations,
    HitPapers,
    ImpactScore,
    HIndex,
    YearCentroid,
    SubfieldCiting,
    YearlyPapers,
    YearlyCites,
    Countries,
    City,
}

impl MetricDecl {
    // Global where every column it reads is loaded and their scan fits the budget, intricate where
    // they are loaded but too large or the read is a walk, absent otherwise. A walk metric's
    // availability is the tree specs' to settle, through `has_profile`.
    pub fn kind(&self, cols: &RootColumns, has_profile: impl Fn(Level) -> bool) -> Option<Kind> {
        if let Some(level) = self.profile {
            return has_profile(level).then_some(Kind::Intricate);
        }
        let mut bytes = 0usize;
        for &c in self.reads {
            bytes += cols.column_bytes(c)?;
        }
        Some(if self.cost == Cost::Read && bytes <= SCAN_BUDGET_BYTES {
            Kind::Global
        } else {
            Kind::Intricate
        })
    }

    pub fn is_entity_valued(&self) -> bool {
        matches!(self.value, ValueType::Entity(_) | ValueType::Entities(_))
    }

    // The metric's value for one entity of the root, None where the root lacks a column it reads.
    pub fn read(&self, cols: &RootColumns, gets: &Getters, dm: usize, arg: Arg) -> Option<Value> {
        let num = |v: f64| Some(Value::Num(v));
        match (self.id, arg) {
            (CITATIONS, _) => num(cols.citations[dm] as f64),
            (PAPERS, _) => num(cols.papers[dm] as f64),
            (HIT_PAPERS, _) => num(cols.hit_counts[dm] as f64),
            (HIT_RATE, _) => num(match cols.papers[dm] {
                0 => 0.0,
                p => cols.hit_counts[dm] as f64 / p as f64,
            }),
            (IMPACT_SCORE, _) => num(cols.impact_scores[dm] as f64),
            (H_INDEX, _) => num(cols.h_indices.as_ref()?[dm] as f64),
            (YEAR_CENTROID, _) => num(cols.year_centroids.as_ref()?[dm] as f64),
            (FIELD_CITATIONS, Arg::Subfield(sf)) => num(cols.field_citations(dm, sf)? as f64),
            (FIELD_SCORE, Arg::Subfield(sf)) => num(field_score(
                cols.field_citations(dm, sf)?,
                cols.papers[dm],
                cols.mean_papers,
            ) as f64),
            (FIELD_SHARE, Arg::Subfield(sf)) => {
                let fc = cols.field_citations(dm, sf)?;
                num(match cols.citations[dm] {
                    0 => 0.0,
                    c => fc as f64 / c as f64,
                })
            }
            (WINDOW_PAPERS, Arg::Window(from, to)) => num(cols.window_sums(dm, from, to).0 as f64),
            (WINDOW_CITATIONS, Arg::Window(from, to)) => {
                num(cols.window_sums(dm, from, to).1 as f64)
            }
            (COUNTRY, _) => {
                if cols.located {
                    return Some(Value::Id(gets.icountry(&dm).to_usize() as u32));
                }
                let row = cols.aff_countries.as_ref()?.row(dm);
                let mut ids = [0u32; N_AFF_COUNTRIES];
                for (slot, (n, c)) in ids.iter_mut().zip(row.iter()) {
                    if *n > 0 {
                        *slot = c.to_usize() as u32;
                    }
                }
                Some(Value::Ids(ids))
            }
            (CITY, _) if cols.located => Some(Value::Id(gets.icity(&dm).to_usize() as u32)),
            _ => None,
        }
    }
}

impl Param {
    // The entity type a slug argument names, None for a numeric window.
    pub fn entity(self) -> Option<&'static str> {
        match self {
            Self::Subfield => Some(Subfields::NAME),
            Self::Country => Some(Countries::NAME),
            Self::Window => None,
        }
    }
}

impl RootColumns {
    pub fn field_citations(&self, dm: usize, sf: usize) -> Option<u32> {
        Some(self.subfields.as_ref()?.citing.elem(dm, sf))
    }

    // The clamped window and the era records inside it. Hit papers declare their yearly papers
    // empty (`mark_empty!` in derive_links5) while their yearly citations are written in full, so
    // the paper side is looked up and the citation side indexed.
    pub fn era_slices(
        &self,
        dm: usize,
        from: Option<RawYear>,
        to: Option<RawYear>,
    ) -> (RawYear, RawYear, &[u32], &[u32]) {
        const EMPTY: &[u32] = &[];
        let (from, to) = clamp_window(from, to);
        match era_span(from, to) {
            Some((cf, ct)) => (
                from,
                to,
                self.yearly_papers.get(dm).map_or(EMPTY, |y| &y[cf..=ct]),
                &self.yearly_cites[dm][cf..=ct],
            ),
            None => (from, to, EMPTY, EMPTY),
        }
    }

    // (papers, citations) in the window, without the yearly series.
    pub fn window_sums(&self, dm: usize, from: Option<RawYear>, to: Option<RawYear>) -> (u32, u32) {
        let (_, _, papers, cites) = self.era_slices(dm, from, to);
        (papers.iter().sum(), cites.iter().sum())
    }

    // Bytes a scan of the column over the whole root reads, None where the root lacks it.
    pub fn column_bytes(&self, c: Column) -> Option<usize> {
        let n = self.papers.len();
        Some(match c {
            Column::Papers | Column::Citations | Column::HitPapers | Column::ImpactScore => n * 4,
            Column::HIndex => self.h_indices.as_ref()?.len() * 4,
            Column::YearCentroid => self.year_centroids.as_ref()?.len() * 4,
            Column::SubfieldCiting => {
                let s = self.subfields.as_ref()?;
                s.citing.len() * std::mem::size_of::<[u32; Subfields::N]>()
            }
            Column::YearlyPapers | Column::YearlyCites => n * std::mem::size_of::<EraRec>(),
            Column::Countries => {
                if self.located {
                    n * std::mem::size_of::<ET<Institutions>>()
                } else {
                    self.aff_countries.as_ref()?.len() * 4 * N_AFF_COUNTRIES * 2
                }
            }
            Column::City => {
                if self.located {
                    n * 2
                } else {
                    return None;
                }
            }
        })
    }
}

pub fn metric(id: &str) -> Option<&'static MetricDecl> {
    METRICS.iter().find(|m| m.id == id)
}

pub fn era_bounds() -> (RawYear, RawYear) {
    (
        YearInterface::reverse(MIN_YEAR as ET<Years>),
        YearInterface::reverse(MAX_YEAR as ET<Years>),
    )
}

// A year window moved into the recorded era; an absent bound is the era's.
pub fn clamp_window(year_from: Option<RawYear>, year_to: Option<RawYear>) -> (RawYear, RawYear) {
    let (era_from, era_to) = era_bounds();
    (
        year_from.unwrap_or(era_from).max(era_from),
        year_to.unwrap_or(era_to).min(era_to),
    )
}

// Inclusive era-record indices of a clamped window; None once the window is empty.
pub fn era_span(from: RawYear, to: RawYear) -> Option<(usize, usize)> {
    let (era_from, _) = era_bounds();
    (from <= to).then(|| ((from - era_from) as usize, (to - era_from) as usize))
}

#[cfg(test)]
mod tests {
    use rankless_rs::metrics::IMPACT_BETA;

    use super::*;

    #[test]
    fn every_metric_names_its_reads_or_its_profile() {
        for m in METRICS {
            assert!(!m.meaning.is_empty(), "{}", m.id);
            assert_eq!(m.reads.is_empty(), m.profile.is_some(), "{}", m.id);
            assert_eq!(m.cost == Cost::Walk, m.profile.is_some(), "{}", m.id);
            assert_eq!(m.header.is_some(), m.param.is_some(), "{}", m.id);
        }
        assert!(METRICS
            .iter()
            .all(|m| METRICS.iter().filter(|o| o.id == m.id).count() == 1));
    }

    // The exponent is stated in prose exactly once, in the meaning the site and the MCP both
    // read; this keeps that prose honest about the constant it describes.
    #[test]
    fn the_impact_meaning_states_the_live_exponent() {
        let decl = metric(IMPACT_SCORE).unwrap();
        assert!(
            decl.meaning.contains(&format!("papers^{IMPACT_BETA}")),
            "{}",
            decl.meaning
        );
    }

    #[test]
    fn a_header_names_only_its_parameter() {
        for m in METRICS {
            for part in m.header.unwrap_or("").split('{').skip(1) {
                let (name, _) = part.split_once('}').expect("unclosed placeholder");
                let expected = match m.param {
                    Some(Param::Subfield) => "subfield",
                    Some(Param::Country) => "country",
                    Some(Param::Window) => "window",
                    None => "",
                };
                assert_eq!(name, expected, "{}", m.id);
            }
        }
    }
}
