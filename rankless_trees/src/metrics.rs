//! The metrics: what can be computed from a root type's columns, each declared once with its
//! value type, its parameter, the columns it reads and the cost of one read. A root's registry —
//! which metrics exist for it and which are global — is derived from what its `RootColumns`
//! loaded: a metric exists where its columns do, and is global where those columns fit a
//! cohort-wide scan. Nothing about a root is typed here but its default ordering.

use dmove::UnsignedNumber;
use rankless_rs::{
    gen::{
        a1_entity_mapping::{Authors, Cities, Countries, Institutions, Sources, Subfields},
        derive_links3::HitPapers,
    },
    metrics::{
        field_score, fill, text_vars, top_n, Level, Texts, HIT_PAPER_TEXTS, H_SINCE,
        PAPER_SCORE_TEXTS,
    },
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
pub const HIT_PAPERS: &str = "hit_papers";
pub const HIT_RATE: &str = "hit_rate";
pub const WEIGHTED_PAPER_SCORE: &str = "weighted_paper_score";
pub const TOP_MEAN: &str = "top_mean";
pub const H_INDEX: &str = "h_index";
pub const H_INDEX_SINCE: [&str; H_SINCE.len()] = ["h_index_since_2010", "h_index_since_2020"];
pub const POPULATION: &str = "population";
pub const WEIGHTED_PAPER_SCORE_PER_CAPITA: &str = "weighted_paper_score_per_capita";
pub const HIT_PAPERS_PER_CAPITA: &str = "hit_papers_per_capita";
pub const PAPER_SCORE: &str = PAPER_SCORE_TEXTS.id;
pub const YEAR_CENTROID: &str = "year_centroid";
pub const FIELD_CITATIONS: &str = "field_citations";
pub const FIELD_SCORE: &str = "field_score";
pub const FIELD_SHARE: &str = "field_share";
pub const WINDOW_PAPERS: &str = "window_papers";
pub const WINDOW_CITATIONS: &str = "window_citations";
pub const CITED_FROM: &str = "cited_from";
pub const COUNTRY: &str = "country";
pub const CITY: &str = "city";

// The first and last year with yearly counts: the years a window can name.
pub const ERA: (RawYear, RawYear) = (
    YearInterface::reverse(MIN_YEAR as ET<Years>),
    YearInterface::reverse(MAX_YEAR as ET<Years>),
);

const READ: &[Column] = &[];

const H_INDEX_SINCE_DECL: MetricDecl = MetricDecl {
    id: H_INDEX_SINCE[0],
    label: "h-index since {since}",
    header: None,
    meaning: "The h-index over the entity's recent papers.",
    rationale: Some(
        "The all-time h-index leans toward older output; a recent window shows who leads now.",
    ),
    value: ValueType::Count,
    param: None,
    reads: &[Column::HIndexSince(0)],
    cost: Cost::Read,
    profile: None,
};

// One declaration per metric, the single source of its label, meaning, rationale, value type,
// parameter and the columns behind it. The texts are templates `texts` fills per root from the
// constants they name; `header` names a parameterized metric's column, `{param}` standing for the
// argument's name, which the client fills.
pub const METRICS: &[MetricDecl] = &[
    MetricDecl {
        id: CITATIONS,
        label: "Citations",
        header: None,
        meaning: "Citations received by the entity's indexed papers.",
        rationale: None,
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
        rationale: None,
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
        meaning: "Papers of the entity with a paper score of at least √{hit_multiple}: cited at least {hit_multiple}× the top-{top_share} bar of their field and year.",
        rationale: Some("How much top work the entity has, on a bar that means the same in every field and year."),
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
        meaning: "Share of the entity's scored papers that are hit papers.",
        rationale: Some("How often the entity's work reaches the top. It reads the rate alone, so a small specialist can top it: read it beside the paper count."),
        value: ValueType::Share,
        param: None,
        reads: &[Column::HitPapers, Column::ScoredPapers],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: WEIGHTED_PAPER_SCORE,
        label: "Weighted total paper score",
        header: None,
        meaning: "Sum of the paper scores of the entity's papers. A paper with several {members} counts for each of them on a softened scale: with n of them, each is credited 1 / (1 + ln n) of its score.",
        rationale: Some("Everything the entity amassed. A shared paper is divided on a softened scale, so large collaborations still count rather than being divided away."),
        value: ValueType::Score,
        param: None,
        reads: &[Column::WeightedPaperScore],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: TOP_MEAN,
        label: "Top-{n} mean",
        header: None,
        meaning: "Mean paper score of the entity's {n} best papers; with fewer than {n} papers the missing ones count as zero.",
        rationale: Some("How good the entity's best work is. The rest of its output neither helps nor hurts, and a small entity cannot rank on a handful of papers."),
        value: ValueType::Score,
        param: None,
        reads: &[Column::TopMean],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: H_INDEX,
        label: "h-index",
        header: None,
        meaning: "Largest h such that h of the entity's papers have at least h citations each. It counts raw citations, with no field or year adjustment.",
        rationale: Some("The familiar reading of citation depth. Raw citations favour older output and citation-dense fields; the paper-score metrics are the readings adjusted for field and year."),
        value: ValueType::Count,
        param: None,
        reads: &[Column::HIndex],
        cost: Cost::Read,
        profile: None,
    },
    H_INDEX_SINCE_DECL,
    MetricDecl {
        id: H_INDEX_SINCE[1],
        reads: &[Column::HIndexSince(1)],
        ..H_INDEX_SINCE_DECL
    },
    MetricDecl {
        id: POPULATION,
        label: "Population",
        header: None,
        meaning: "Inhabitants of the country, from the latest year with data.",
        rationale: None,
        value: ValueType::Count,
        param: None,
        reads: &[Column::Population],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: WEIGHTED_PAPER_SCORE_PER_CAPITA,
        label: "Weighted total paper score per capita",
        header: None,
        meaning: "The weighted total paper score per million inhabitants.",
        rationale: Some("Output for the size of the population."),
        value: ValueType::Score,
        param: None,
        reads: &[Column::WeightedPaperScore, Column::Population],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: HIT_PAPERS_PER_CAPITA,
        label: "Hit papers per capita",
        header: None,
        meaning: "Hit papers per million inhabitants.",
        rationale: Some("Top work for the size of the population."),
        value: ValueType::Score,
        param: None,
        reads: &[Column::HitPapers, Column::Population],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: PAPER_SCORE,
        label: PAPER_SCORE_TEXTS.label,
        header: None,
        meaning: PAPER_SCORE_TEXTS.meaning,
        rationale: PAPER_SCORE_TEXTS.rationale,
        value: ValueType::Score,
        param: None,
        reads: &[Column::PaperScore],
        cost: Cost::Read,
        profile: None,
    },
    MetricDecl {
        id: YEAR_CENTROID,
        label: "Career centroid",
        header: None,
        meaning: "Mean publication year of the author's papers: where in time the career's output sits.",
        rationale: None,
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
        rationale: None,
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
        rationale: None,
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
        rationale: None,
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
        meaning: "Indexed papers published in the year window.",
        rationale: None,
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
        meaning: "Citations from papers published in the year window.",
        rationale: None,
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
        rationale: None,
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
        rationale: None,
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
        rationale: None,
        value: ValueType::Entity(Cities::NAME),
        param: None,
        reads: &[Column::City],
        cost: Cost::Read,
        profile: None,
    },
];

pub struct MetricDecl {
    pub id: &'static str,
    pub label: &'static str,
    pub header: Option<&'static str>,
    pub meaning: &'static str,
    pub rationale: Option<&'static str>,
    pub value: ValueType,
    pub param: Option<Param>,
    pub reads: &'static [Column],
    pub cost: Cost,
    pub profile: Option<Level>,
}

// A methodology item's texts, every constant filled in.
#[derive(Serialize)]
pub struct ItemTexts {
    pub id: &'static str,
    #[serde(flatten)]
    pub texts: MetricTexts,
}

// A metric's texts as one root shows them, every constant filled in.
#[derive(Serialize)]
pub struct MetricTexts {
    pub label: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub header: Option<String>,
    pub meaning: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rationale: Option<String>,
}

// A bound argument: the parameter's value resolved to what the reader needs.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Arg {
    None,
    Subfield(usize),
    Country(usize),
    Window(RawYear, RawYear),
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

// The papers a column reads, by publication year, which a metric's meaning ends by stating.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Coverage {
    Indexed,
    // The indexed papers that have a paper score.
    Scored,
    // The indexed papers since the metric's recent h-index year.
    Since,
    // The years with yearly counts, which a window stays inside.
    Era,
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
    ScoredPapers,
    WeightedPaperScore,
    TopMean,
    HIndex,
    HIndexSince(usize),
    Population,
    PaperScore,
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
            (HIT_RATE, _) => num(match cols.scored_papers[dm] {
                0 => 0.0,
                p => cols.hit_counts[dm] as f64 / p as f64,
            }),
            (WEIGHTED_PAPER_SCORE, _) => num(cols.weighted_paper_scores.as_ref()?[dm] as f64),
            (TOP_MEAN, _) => num(cols.top_means.as_ref()?[dm] as f64),
            (H_INDEX, _) => num(cols.h_indices.as_ref()?[dm] as f64),
            (POPULATION, _) => num(cols.population.as_ref()?[dm] as f64),
            (WEIGHTED_PAPER_SCORE_PER_CAPITA, _) => num(per_million(
                cols.weighted_paper_scores.as_ref()?[dm] as f64,
                cols.population.as_ref()?[dm],
            )?),
            (HIT_PAPERS_PER_CAPITA, _) => num(per_million(
                cols.hit_counts[dm] as f64,
                cols.population.as_ref()?[dm],
            )?),
            (PAPER_SCORE, _) => num(cols.paper_scores.as_ref()?[dm] as f64),
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
            _ => match self.reads {
                [Column::HIndexSince(i)] => num(cols.h_since.as_ref()?[dm][*i] as f64),
                _ => None,
            },
        }
    }

    // The papers the metric reads: those of its first column that is a reading over papers, every
    // indexed paper for a walk; None for a metric that reads no paper set.
    pub fn covers(&self) -> Option<Coverage> {
        self.reads
            .iter()
            .find_map(|c| c.covers())
            .or(self.profile.map(|_| Coverage::Indexed))
    }

    // The texts as `root` shows them: the constants filled in, a header's parameter left for the
    // client.
    pub fn texts(&self, root: &str) -> MetricTexts {
        let mut vars = vars();
        vars.push(("members", root.to_string()));
        if let Some(n) = top_n(root) {
            vars.push(("n", n.to_string()));
        }
        if let [Column::HIndexSince(i)] = self.reads {
            vars.push(("since", H_SINCE[*i].to_string()));
        }
        let meaning = match self.covers() {
            Some(c) => format!("{} {}", self.meaning, c.text()),
            None => self.meaning.to_string(),
        };
        MetricTexts::fill(self.label, self.header, &meaning, self.rationale, &vars)
    }
}

impl MetricTexts {
    fn fill(
        label: &str,
        header: Option<&str>,
        meaning: &str,
        rationale: Option<&str>,
        vars: &[(&str, String)],
    ) -> Self {
        let fill = |s: &str| fill(s, vars);
        Self {
            label: fill(label),
            header: header.map(fill),
            meaning: fill(meaning),
            rationale: rationale.map(fill),
        }
    }
}

impl Coverage {
    fn text(self) -> &'static str {
        match self {
            Self::Indexed => "Covers papers published {first_year}–{final_year}.",
            Self::Scored => {
                "Covers papers published {first_year}–{last_scored_year}, the years with paper scores."
            }
            Self::Since => "Covers papers published {since}–{final_year}.",
            Self::Era => "Yearly counts cover {era_from}–{final_year}.",
        }
    }
}

impl Column {
    fn covers(self) -> Option<Coverage> {
        Some(match self {
            Self::Papers | Self::Citations | Self::HIndex | Self::YearCentroid => Coverage::Indexed,
            Self::SubfieldCiting => Coverage::Indexed,
            Self::HitPapers | Self::ScoredPapers | Self::WeightedPaperScore | Self::TopMean => {
                Coverage::Scored
            }
            Self::HIndexSince(_) => Coverage::Since,
            Self::YearlyPapers | Self::YearlyCites => Coverage::Era,
            Self::Population | Self::PaperScore | Self::Countries | Self::City => return None,
        })
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

    // The era records of a window inside `ERA`, empty when it ends before it starts. Hit papers
    // declare their yearly papers empty (`mark_empty!` in derive_links5) while their yearly
    // citations are written in full, so the paper side is looked up and the citation side indexed.
    pub fn era_slices(&self, dm: usize, from: RawYear, to: RawYear) -> (&[u32], &[u32]) {
        const EMPTY: &[u32] = &[];
        if from > to {
            return (EMPTY, EMPTY);
        }
        let (cf, ct) = ((from - ERA.0) as usize, (to - ERA.0) as usize);
        (
            self.yearly_papers.get(dm).map_or(EMPTY, |y| &y[cf..=ct]),
            &self.yearly_cites[dm][cf..=ct],
        )
    }

    // (papers, citations) in the window, without the yearly series.
    pub fn window_sums(&self, dm: usize, from: RawYear, to: RawYear) -> (u32, u32) {
        let (papers, cites) = self.era_slices(dm, from, to);
        (papers.iter().sum(), cites.iter().sum())
    }

    // Bytes a scan of the column over the whole root reads, None where the root lacks it.
    pub fn column_bytes(&self, c: Column) -> Option<usize> {
        let n = self.papers.len();
        Some(match c {
            Column::Papers | Column::Citations | Column::HitPapers | Column::ScoredPapers => n * 4,
            Column::WeightedPaperScore => self.weighted_paper_scores.as_ref()?.len() * 4,
            Column::TopMean => self.top_means.as_ref()?.len() * 4,
            Column::HIndex => self.h_indices.as_ref()?.len() * 4,
            Column::HIndexSince(_) => {
                self.h_since.as_ref()?.len() * std::mem::size_of::<[u32; H_SINCE.len()]>()
            }
            Column::Population => self.population.as_ref()?.len() * 4,
            Column::PaperScore => self.paper_scores.as_ref()?.len() * 4,
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

// The metric a root's table is ordered by until the reader picks another: the root's primary
// performance reading, or its citations where the portfolio gives it none.
pub fn default_sort(root: &str) -> &'static str {
    match root {
        r if r == Sources::NAME => TOP_MEAN,
        r if r == Authors::NAME || r == Institutions::NAME || r == Countries::NAME => {
            WEIGHTED_PAPER_SCORE
        }
        r if r == HitPapers::NAME => PAPER_SCORE,
        _ => CITATIONS,
    }
}

pub fn methodology_texts() -> Vec<ItemTexts> {
    let vars = vars();
    [PAPER_SCORE_TEXTS, HIT_PAPER_TEXTS]
        .iter()
        .map(|t: &Texts| ItemTexts {
            id: t.id,
            texts: MetricTexts::fill(t.label, None, t.meaning, t.rationale, &vars),
        })
        .collect()
}

fn per_million(value: f64, population: u32) -> Option<f64> {
    (population > 0).then(|| value / (population as f64 / 1e6))
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
    use rankless_rs::metrics::TOP_N;

    use super::*;

    const ROOTS: &[&str] = &[
        Authors::NAME,
        Institutions::NAME,
        Countries::NAME,
        Sources::NAME,
        Subfields::NAME,
        HitPapers::NAME,
    ];

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

    // A text names constants, never states them, so every placeholder must resolve on every root
    // the metric can exist on: a Top-N mean only where the root has an N.
    #[test]
    fn every_text_resolves_its_constants() {
        for m in METRICS {
            let roots = ROOTS
                .iter()
                .filter(|r| !m.reads.contains(&Column::TopMean) || top_n(r).is_some());
            for root in roots {
                let t = m.texts(root);
                for text in [
                    &t.label,
                    &t.meaning,
                    t.rationale.as_ref().unwrap_or(&t.label),
                ] {
                    assert!(!text.contains('{'), "{} on {root}: {text}", m.id);
                }
            }
        }
    }

    #[test]
    fn the_recent_h_indices_follow_their_years() {
        for (i, id) in H_INDEX_SINCE.iter().enumerate() {
            assert_eq!(*id, format!("h_index_since_{}", H_SINCE[i]));
            let decl = metric(id).unwrap();
            assert_eq!(decl.reads, &[Column::HIndexSince(i)]);
            assert!(decl
                .texts(Sources::NAME)
                .label
                .ends_with(&H_SINCE[i].to_string()));
        }
    }

    #[test]
    fn the_top_n_roots_are_entity_names() {
        let named = [
            Sources::NAME,
            Institutions::NAME,
            Countries::NAME,
            Authors::NAME,
        ];
        for (root, _) in TOP_N {
            assert!(named.contains(root), "{root}");
        }
        assert_eq!(
            metric(TOP_MEAN).unwrap().texts(Authors::NAME).label,
            "Top-20 mean"
        );
    }

    #[test]
    fn coverage_follows_the_columns_read() {
        let covers = |id: &str| metric(id).unwrap().covers();
        assert_eq!(covers(PAPERS), Some(Coverage::Indexed));
        assert_eq!(covers(HIT_RATE), Some(Coverage::Scored));
        assert_eq!(
            covers(WEIGHTED_PAPER_SCORE_PER_CAPITA),
            Some(Coverage::Scored)
        );
        assert_eq!(covers(H_INDEX_SINCE[0]), Some(Coverage::Since));
        assert_eq!(covers(WINDOW_PAPERS), Some(Coverage::Era));
        assert_eq!(covers(CITED_FROM), Some(Coverage::Indexed));
        assert_eq!(covers(POPULATION), None);
        assert_eq!(covers(COUNTRY), None);
    }

    #[test]
    fn every_default_sort_is_a_metric() {
        for root in ROOTS {
            assert!(metric(default_sort(root)).is_some(), "{root}");
        }
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
