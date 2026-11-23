use std::{cmp::Reverse, sync::OnceLock, time::Instant};

use dmove::{reverse_prefixed_n, Entity, UnsignedNumber, VaST, ET};
use hashbrown::{HashMap, HashSet};
use serde::Serialize;
use wiretypes::wire;

use rankless_rs::{
    fixed_heap::FixedHeap,
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields},
        a2_init_atts::{AuthorNobels, WorkAnyAuthorships},
    },
    ladder::LADDER_LEN,
    metrics::{is_hit, paper_score},
};
use rankless_trees::{
    interfacing::{Getters, RootColumns, ServerGetters},
    io::WT,
    metrics::TOP_MEAN,
    AttributeLabelUnion,
};

use crate::responses::PaperSetResp;
use crate::state::NameStateMap;

// A list shows `shown` highlights at most. A citing paper in one of the `apex_journals` journals
// ranked highest by Top-N mean, review journals left out, is an apex citation; an institution among
// the `elite_institutions` ranked highest is elite, and badges one citing paper of its once it is on
// `min_institution_papers` independent citing papers; a star is looked for in the author's
// `star_fields` most citing fields; a citing paper with more than `max_citing_refs` references
// reads as a review and earns no hit or apex badge; each pick multiplies the worth of every facet
// it covers by `decay`.
#[wire]
pub(crate) const HIGHLIGHT_RULES: HighlightRules = HighlightRules {
    shown: 10,
    apex_journals: 10,
    elite_institutions: 50,
    min_institution_papers: 2,
    star_fields: 3,
    max_citing_refs: 100,
    decay: 0.5,
};

// The best candidates of each kind that enter the selection.
const PER_KIND: usize = HIGHLIGHT_RULES.shown;
// The most authors in the sample a highlight's rarity is measured against, taken evenly along the
// authors' citation order.
const REFERENCE_SAMPLE: usize = 10_000;
// A journal whose name holds one of these phrases as whole words publishes reviews, which cite
// hundreds of papers. The singular "review" also names research journals (Physical Review Letters,
// American Economic Review), whose review papers the reference count screens instead.
const REVIEW_JOURNAL_PHRASES: [&[&str]; 4] = [
    &["reviews"],
    &["annual", "review"],
    &["trends", "in"],
    &["current", "opinion"],
];
const KINDS: [HighlightKind; 5] = [
    HighlightKind::Hit,
    HighlightKind::Apex,
    HighlightKind::Laureate,
    HighlightKind::Star,
    HighlightKind::Institution,
];

type AuthorId = ET<Authors>;
type InstId = ET<Institutions>;
type Prize = ET<AuthorNobels>;
// The best `PER_KIND` papers by (strength, citations).
type PaperHeap = FixedHeap<Reverse<((f64, u32), WT)>, PER_KIND>;
// Per subfield, the authors whose citations from it reach its star band, with those citations, by
// author.
type Stars = Box<[Box<[(AuthorId, u32)]>]>;

#[wire]
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct HighlightRules {
    pub shown: usize,
    pub apex_journals: usize,
    pub elite_institutions: usize,
    pub min_institution_papers: u32,
    pub star_fields: usize,
    pub max_citing_refs: usize,
    pub decay: f64,
}

// Counts over the author's independent citing papers; `citing_papers` counts every citing paper
// of their team works, `independent` those the highlights are drawn from.
#[wire]
#[derive(Serialize, Default, Debug)]
#[serde(rename_all = "camelCase")]
pub(crate) struct HighlightTotals {
    pub citing_papers: u32,
    pub independent: u32,
    pub hits: u32,
    pub apex: u32,
    pub laureates: u32,
    pub stars: u32,
    pub institutions: u32,
}

#[wire]
#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct ImpactHighlightsResp {
    pub highlights: Vec<Highlight>,
    pub totals: HighlightTotals,
    // The papers of the paper highlights and the author's papers they cite.
    pub papers: PaperSetResp,
    // The apex journals by dm id, best first.
    pub apex_sources: Vec<usize>,
}

// The global pools, by dm id, and the star table and rarity reference, built once in the
// background.
pub(crate) struct Highlighter {
    apex: Box<[usize]>,
    apex_rank: Box<[Option<u16>]>,
    elite_rank: Box<[Option<u16>]>,
    elite: Box<[usize]>,
    // Journals whose name says they publish reviews, which make no paper highlight.
    review_source: Box<[bool]>,
    stars: OnceLock<Stars>,
    reference: OnceLock<Reference>,
}

pub(crate) struct Found {
    pub highlights: Vec<Highlight>,
    pub totals: HighlightTotals,
}

// Each kind's best strength per sampled author, ascending, and the sample's size.
struct Reference {
    size: usize,
    strengths: [Vec<f64>; KINDS.len()],
}

struct Ctx<'a> {
    hl: &'a Highlighter,
    gets: &'a Getters,
    server: &'a ServerGetters,
    authors: &'a RootColumns,
    stars: &'a Stars,
}

struct Subject {
    aid: AuthorId,
    coauthors: HashSet<AuthorId>,
    own_insts: HashSet<InstId>,
    prize: Prize,
    // The author's most citing fields with their tightest ladder band.
    star_fields: Vec<(usize, u32)>,
}

struct Star {
    ratio: f64,
    field: usize,
    citations: u32,
    wid: WT,
}

struct Scan {
    // (citing paper, the author's paper it cites), sorted.
    pairs: Vec<(WT, WT)>,
    totals: HighlightTotals,
    hits: Vec<(f64, WT)>,
    apex: Vec<(f64, WT)>,
    // A laureate's most cited independent citing paper.
    laureates: HashMap<AuthorId, (u32, WT)>,
    stars: HashMap<AuthorId, Star>,
    // Per elite rank.
    institutions: Box<[Tally]>,
}

// An elite institution's independent citing papers and the most cited of them.
#[derive(Clone, Copy, Default)]
struct Tally {
    papers: u32,
    best: Option<(u32, WT)>,
}

struct Candidate<T> {
    item: T,
    // Each part's base worth and the facets that decay it.
    parts: Vec<(f64, Vec<Facet>)>,
    // Facets that decay the whole candidate.
    shared: Vec<Facet>,
}

#[wire]
#[derive(Serialize, Clone, Copy, PartialEq, Eq, Hash, Debug)]
#[serde(rename_all = "camelCase")]
pub(crate) enum HighlightKind {
    Hit,
    Apex,
    Laureate,
    Star,
    Institution,
}

// What makes a citing paper a highlight. `rarity` is the share of the reference sample whose best
// of the kind is at least as strong.
#[wire]
#[derive(Serialize, Clone, PartialEq, Debug)]
#[serde(tag = "kind", rename_all = "camelCase")]
pub(crate) enum Badge {
    // `multiple`: its citations over the bar of its field and year, the paper score squared.
    Hit {
        multiple: f64,
        rarity: f64,
    },
    // `rank` among the apex journals, from 1.
    Apex {
        source: usize,
        rank: usize,
        rarity: f64,
    },
    Laureate {
        author: usize,
        rarity: f64,
    },
    // `ratio`: their citations from `field` over the field's tightest ladder band.
    Star {
        author: usize,
        field: usize,
        ratio: f64,
        rarity: f64,
    },
    // An elite institution of the paper, on `papers` independent citing papers, `rank` among the
    // elite from 1.
    Institution {
        institution: usize,
        country: usize,
        papers: u32,
        rank: usize,
        rarity: f64,
    },
}

// A citing paper and the author's papers it cites, most cited first.
#[wire]
#[derive(Serialize, Clone, PartialEq, Debug)]
pub(crate) struct Highlight {
    pub wid: usize,
    pub cites: Vec<usize>,
    pub badges: Vec<Badge>,
}

// Facets a pick covers, whose worth each later pick then decays.
#[derive(Hash, PartialEq, Eq, Clone, Copy, Debug)]
enum Facet {
    Kind(HighlightKind),
    Journal(usize),
    Person(usize),
    Country(usize),
    Cited(usize),
}

impl Highlighter {
    pub fn new(ns: &NameStateMap, labels: &AttributeLabelUnion) -> Self {
        let review_source: Box<[bool]> = labels[Sources::NAME]
            .iter()
            .map(|l| is_review_journal(&l.name))
            .collect();
        let apex =
            top_ranked::<Sources>(ns, HIGHLIGHT_RULES.apex_journals, |dm| !review_source[dm]);
        let elite = top_ranked::<Institutions>(ns, HIGHLIGHT_RULES.elite_institutions, |_| true);
        Self {
            apex_rank: ranks(&apex, Sources::N),
            apex,
            elite_rank: ranks(&elite, Institutions::N),
            elite,
            review_source,
            stars: OnceLock::new(),
            reference: OnceLock::new(),
        }
    }

    pub fn apex_sources(&self) -> &[usize] {
        &self.apex
    }

    // None until `warm` has built the rarity reference, so no request waits on the build.
    pub fn find(&self, gets: &Getters, server: &ServerGetters, aid: usize) -> Option<Found> {
        let (reference, stars) = (self.reference.get()?, self.stars.get()?);
        let ctx = self.ctx(gets, server, stars);
        let scan = ctx.scan(aid);
        let candidates = ctx.candidates(&scan, reference);
        Some(Found {
            highlights: select(candidates, HIGHLIGHT_RULES.shown, HIGHLIGHT_RULES.decay),
            totals: scan.totals,
        })
    }

    // Builds the star table and the rarity reference `find` reads.
    pub fn warm(&self, ns: &NameStateMap, gets: &Getters, server: &ServerGetters) {
        let stars = self.stars.get_or_init(|| {
            let now = Instant::now();
            let stars = star_table(gets.columns_for(Authors::NAME).expect("author columns"));
            println!(
                "highlight star table of {} authors in {:.2?}",
                stars.iter().map(|s| s.len()).sum::<usize>(),
                now.elapsed()
            );
            stars
        });
        self.reference.get_or_init(|| {
            let now = Instant::now();
            let responses = &ns[Authors::NAME].responses;
            let step = responses.len().div_ceil(REFERENCE_SAMPLE).max(1);
            let sample: Vec<usize> = responses.iter().step_by(step).map(|r| r.dm_id).collect();
            let ctx = self.ctx(gets, server, stars);
            let threads = std::thread::available_parallelism().map_or(1, |p| p.get());
            let chunk = sample.len().div_ceil(threads).max(1);
            let bests: Vec<[Option<f64>; KINDS.len()]> = std::thread::scope(|s| {
                sample
                    .chunks(chunk)
                    .map(|part| {
                        let ctx = &ctx;
                        s.spawn(move || {
                            part.iter()
                                .map(|&a| ctx.scan(a).bests())
                                .collect::<Vec<_>>()
                        })
                    })
                    .collect::<Vec<_>>()
                    .into_iter()
                    .flat_map(|h| h.join().expect("highlight reference"))
                    .collect()
            });
            let reference = Reference::new(&bests);
            println!(
                "highlight reference over {} authors in {:.2?}",
                reference.size,
                now.elapsed()
            );
            reference
        });
    }

    fn ctx<'a>(
        &'a self,
        gets: &'a Getters,
        server: &'a ServerGetters,
        stars: &'a Stars,
    ) -> Ctx<'a> {
        Ctx {
            hl: self,
            gets,
            server,
            authors: gets.columns_for(Authors::NAME).expect("author columns"),
            stars,
        }
    }
}

impl Found {
    // The citing papers and the author's papers they cite.
    pub fn wids(&self) -> Vec<WT> {
        let mut wids: Vec<WT> = self
            .highlights
            .iter()
            .flat_map(|h| std::iter::once(h.wid).chain(h.cites.iter().copied()))
            .map(|w| WT::from_usize(w))
            .collect();
        wids.sort_unstable();
        wids.dedup();
        wids
    }

    // Every entity a badge names, as (entity type, dm id).
    pub fn labels(&self) -> impl Iterator<Item = (&'static str, usize)> + '_ {
        self.highlights
            .iter()
            .flat_map(|h| &h.badges)
            .flat_map(|b| match *b {
                Badge::Hit { .. } => [None, None],
                Badge::Apex { source, .. } => [Some((Sources::NAME, source)), None],
                Badge::Laureate { author, .. } => [Some((Authors::NAME, author)), None],
                Badge::Star { author, field, .. } => [
                    Some((Authors::NAME, author)),
                    Some((Subfields::NAME, field)),
                ],
                Badge::Institution {
                    institution,
                    country,
                    ..
                } => [
                    Some((Institutions::NAME, institution)),
                    Some((Countries::NAME, country)),
                ],
            })
            .flatten()
    }
}

impl Reference {
    fn new(bests: &[[Option<f64>; KINDS.len()]]) -> Self {
        let strengths = std::array::from_fn(|k| {
            let mut v: Vec<f64> = bests.iter().filter_map(|b| b[k]).collect();
            v.sort_by(f64::total_cmp);
            v
        });
        Self {
            size: bests.len(),
            strengths,
        }
    }

    // The share of the sample whose best of `kind` is at least `strength`; O(log n).
    fn rarity(&self, kind: HighlightKind, strength: f64) -> f64 {
        let s = &self.strengths[kind as usize];
        (s.len() - s.partition_point(|&x| x < strength)) as f64 / self.size.max(1) as f64
    }

    // Minus the log of the rarity, a strength past the whole sample counting as one in a sample
    // one larger.
    fn worth(&self, rarity: f64) -> f64 {
        -rarity.max(1.0 / (self.size + 1) as f64).ln()
    }
}

impl Ctx<'_> {
    fn subject(&self, aid: usize) -> Subject {
        let a = AuthorId::from_usize(aid);
        let mut own_insts = HashSet::new();
        for &w in self.gets.aworks(a) {
            for (id, author) in ship_authors(self.gets, self.gets.wanyships(w)) {
                if author == a {
                    own_insts.extend(self.gets.fshipis(id).iter().copied());
                }
            }
        }
        let mut fields: Vec<(u32, usize)> = self
            .authors
            .citing_sfc
            .row(aid)
            .into_iter()
            .map(|(score, sf)| (score, sf.to_usize()))
            .filter(|&(_, sf)| sf != 0)
            .collect();
        fields.sort_by_key(|&(score, _)| Reverse(score));
        let star_fields = fields
            .into_iter()
            .take(HIGHLIGHT_RULES.star_fields)
            .filter_map(|(_, sf)| star_band(self.authors, sf).map(|band| (sf, band)))
            .collect();
        Subject {
            aid: a,
            coauthors: self.server.coathors(aid).iter().map(|&(c, _)| c).collect(),
            own_insts,
            prize: *self.server.author_prizes(&aid),
            star_fields,
        }
    }

    // A citing paper's authorship rows when it counts for the subject: a team paper none of whose
    // authors is the subject or a co-author of theirs, and none of whose institutions is one the
    // subject's own rows name.
    fn independent(&self, s: &Subject, c: WT) -> Option<&[VaST<WorkAnyAuthorships>]> {
        let ships = self.gets.team_ships(c);
        let close = ships.is_empty()
            || ship_authors(self.gets, ships).any(|(_, b)| b == s.aid || s.coauthors.contains(&b))
            || self.gets.winsts(c).iter().any(|i| s.own_insts.contains(i));
        (!close).then_some(ships)
    }

    fn scan(&self, aid: usize) -> Scan {
        let s = self.subject(aid);
        let mut pairs: Vec<(WT, WT)> = self
            .gets
            .aworks(s.aid)
            .iter()
            .filter(|&&w| !self.gets.team_ships(w).is_empty())
            .flat_map(|&w| self.gets.citing(w).iter().map(move |&c| (c, w)))
            .collect();
        pairs.sort_unstable();
        let mut totals = HighlightTotals::default();
        let (mut hits, mut apex) = (PaperHeap::new(), PaperHeap::new());
        let mut laureates: HashMap<AuthorId, (u32, WT)> = HashMap::new();
        let mut stars: HashMap<AuthorId, Star> = HashMap::new();
        let mut institutions = vec![Tally::default(); HIGHLIGHT_RULES.elite_institutions];
        for group in pairs.chunk_by(|l, r| l.0 == r.0) {
            let c = group[0].0;
            totals.citing_papers += 1;
            let Some(ships) = self.independent(&s, c) else {
                continue;
            };
            totals.independent += 1;
            let citations = self.gets.wccount(c.to_usize()) as u32;
            for i in self.gets.winsts(c) {
                if let Some(r) = self.hl.elite_rank[i.to_usize()] {
                    let t = &mut institutions[r as usize];
                    t.papers += 1;
                    if t.best.is_none_or(|(n, _)| citations > n) {
                        t.best = Some((citations, c));
                    }
                }
            }
            let source = self.gets.top_source(&c).to_usize();
            if self.server.wrefcount(c.to_usize()) <= HIGHLIGHT_RULES.max_citing_refs
                && !self.hl.review_source[source]
            {
                if let Some(score) =
                    paper_score(citations, *self.gets.wbar(&c)).filter(|&p| is_hit(p))
                {
                    totals.hits += 1;
                    hits.push_unique(Reverse(((score * score, citations), c)));
                }
                if let Some(r) = self.hl.apex_rank[source] {
                    totals.apex += 1;
                    let strength = rank_strength(r as usize, HIGHLIGHT_RULES.apex_journals);
                    apex.push_unique(Reverse(((strength, citations), c)));
                }
            }
            for (_, b) in ship_authors(self.gets, ships) {
                let bu = b.to_usize();
                let prize = *self.server.author_prizes(&bu);
                if prize.0 != 0 && (s.prize.0 == 0 || prize != s.prize) {
                    let best = laureates.entry(b).or_insert((citations, c));
                    if citations > best.0 {
                        *best = (citations, c);
                    }
                }
                for &(field, band) in &s.star_fields {
                    let row = &self.stars[field];
                    let Ok(i) = row.binary_search_by_key(&b, |&(a, _)| a) else {
                        continue;
                    };
                    let fc = row[i].1;
                    let ratio = fc as f64 / band as f64;
                    let star = Star {
                        ratio,
                        field,
                        citations,
                        wid: c,
                    };
                    match stars.get(&b) {
                        Some(e) if (e.ratio, e.citations) >= (ratio, citations) => {}
                        _ => {
                            stars.insert(b, star);
                        }
                    }
                }
            }
        }
        // A laureate's badge subsumes their star.
        stars.retain(|a, _| !laureates.contains_key(a));
        totals.laureates = laureates.len() as u32;
        totals.stars = stars.len() as u32;
        totals.institutions = institutions.iter().filter(|t| t.qualifies()).count() as u32;
        let best = |heap: PaperHeap| {
            heap.into_iter()
                .map(|Reverse(((strength, _), wid))| (strength, wid))
                .collect()
        };
        Scan {
            pairs,
            totals,
            hits: best(hits),
            apex: best(apex),
            laureates,
            stars,
            institutions: institutions.into_boxed_slice(),
        }
    }

    fn candidates(&self, scan: &Scan, reference: &Reference) -> Vec<Candidate<Highlight>> {
        let mut laureates: Vec<(&AuthorId, &(u32, WT))> = scan.laureates.iter().collect();
        laureates.sort_by_key(|(a, (citations, _))| (Reverse(*citations), **a));
        let mut stars: Vec<(&AuthorId, &Star)> = scan.stars.iter().collect();
        stars.sort_by(|(a, l), (b, r)| {
            (r.ratio, r.citations)
                .partial_cmp(&(l.ratio, l.citations))
                .expect("star ratios are finite")
                .then(a.cmp(b))
        });
        let mut papers: Vec<WT> = scan
            .hits
            .iter()
            .chain(&scan.apex)
            .map(|&(_, w)| w)
            .collect();
        papers.extend(laureates.iter().take(PER_KIND).map(|(_, &(_, w))| w));
        papers.extend(stars.iter().take(PER_KIND).map(|(_, s)| s.wid));
        papers.sort_unstable();
        papers.dedup();
        let elite = self.elite_carriers(scan, &papers);
        papers.extend(elite.iter().map(|e| e.2));
        papers.sort_unstable();
        papers.dedup();

        let part = |kind, strength: f64, value: Option<Facet>| {
            let rarity = reference.rarity(kind, strength);
            let facets = std::iter::once(Facet::Kind(kind)).chain(value).collect();
            (rarity, (reference.worth(rarity), facets))
        };
        papers
            .into_iter()
            .map(|wid| {
                let mut badges = vec![];
                let mut parts = vec![];
                if let Some(&(multiple, _)) = scan.hits.iter().find(|(_, w)| *w == wid) {
                    let (rarity, p) = part(HighlightKind::Hit, multiple, None);
                    badges.push(Badge::Hit { multiple, rarity });
                    parts.push(p);
                }
                if let Some(&(strength, _)) = scan.apex.iter().find(|(_, w)| *w == wid) {
                    let source = self.gets.top_source(&wid).to_usize();
                    let (rarity, p) =
                        part(HighlightKind::Apex, strength, Some(Facet::Journal(source)));
                    let rank = strength_rank(strength, HIGHLIGHT_RULES.apex_journals) + 1;
                    badges.push(Badge::Apex {
                        source,
                        rank,
                        rarity,
                    });
                    parts.push(p);
                }
                for (a, _) in laureates
                    .iter()
                    .take(PER_KIND)
                    .filter(|(_, (_, w))| *w == wid)
                {
                    let author = a.to_usize();
                    let (rarity, p) =
                        part(HighlightKind::Laureate, 1.0, Some(Facet::Person(author)));
                    badges.push(Badge::Laureate { author, rarity });
                    parts.push(p);
                }
                for (a, s) in stars.iter().take(PER_KIND).filter(|(_, s)| s.wid == wid) {
                    let author = a.to_usize();
                    let (rarity, p) =
                        part(HighlightKind::Star, s.ratio, Some(Facet::Person(author)));
                    badges.push(Badge::Star {
                        author,
                        field: s.field,
                        ratio: s.ratio,
                        rarity,
                    });
                    parts.push(p);
                }
                for &(rank, papers, _) in elite.iter().filter(|e| e.2 == wid) {
                    let institution = self.hl.elite[rank];
                    let country = self.gets.icountry(&institution).to_usize();
                    let strength = rank_strength(rank, HIGHLIGHT_RULES.elite_institutions);
                    let (rarity, p) = part(
                        HighlightKind::Institution,
                        strength,
                        Some(Facet::Country(country)),
                    );
                    badges.push(Badge::Institution {
                        institution,
                        country,
                        papers,
                        rank: rank + 1,
                        rarity,
                    });
                    parts.push(p);
                }
                let cites = self.cited(scan, wid);
                let cited = Facet::Cited(cites[0]);
                let item = Highlight {
                    wid: wid.to_usize(),
                    cites,
                    badges,
                };
                Candidate::new(item, parts, vec![cited])
            })
            .collect()
    }

    // The best elite institutions on enough independent citing papers, each as (rank, papers, the
    // paper that carries it): the most cited of `papers` it is on, else its own most cited.
    fn elite_carriers(&self, scan: &Scan, papers: &[WT]) -> Vec<(usize, u32, WT)> {
        scan.institutions
            .iter()
            .enumerate()
            .filter(|(_, t)| t.qualifies())
            .take(PER_KIND)
            .map(|(rank, t)| {
                let institution = self.hl.elite[rank];
                let carrier = papers
                    .iter()
                    .copied()
                    .filter(|&w| {
                        self.gets
                            .winsts(w)
                            .iter()
                            .any(|i| i.to_usize() == institution)
                    })
                    .max_by_key(|&w| (self.gets.wccount(w.to_usize()), Reverse(w)))
                    .or(t.best.map(|(_, w)| w))
                    .expect("a counted institution has a paper");
                (rank, t.papers, carrier)
            })
            .collect()
    }

    // The author's papers `wid` cites, most cited first.
    fn cited(&self, scan: &Scan, wid: WT) -> Vec<usize> {
        let lo = scan.pairs.partition_point(|p| p.0 < wid);
        let hi = scan.pairs.partition_point(|p| p.0 <= wid);
        let mut cites: Vec<usize> = scan.pairs[lo..hi].iter().map(|p| p.1.to_usize()).collect();
        cites.sort_by_key(|&w| (Reverse(self.gets.wccount(w)), w));
        cites
    }
}

impl Scan {
    fn bests(&self) -> [Option<f64>; KINDS.len()] {
        KINDS.map(|k| match k {
            HighlightKind::Hit => self.hits.first().map(|h| h.0),
            HighlightKind::Apex => self.apex.first().map(|h| h.0),
            HighlightKind::Laureate => (!self.laureates.is_empty()).then_some(1.0),
            HighlightKind::Star => self.stars.values().map(|s| s.ratio).max_by(f64::total_cmp),
            HighlightKind::Institution => self
                .institutions
                .iter()
                .position(Tally::qualifies)
                .map(|rank| rank_strength(rank, HIGHLIGHT_RULES.elite_institutions)),
        })
    }
}

impl Tally {
    // On enough independent citing papers to badge one of them.
    fn qualifies(&self) -> bool {
        self.papers >= HIGHLIGHT_RULES.min_institution_papers
    }
}

impl<T> Candidate<T> {
    fn new(item: T, mut parts: Vec<(f64, Vec<Facet>)>, shared: Vec<Facet>) -> Self {
        parts.sort_by(|l, r| r.0.total_cmp(&l.0));
        Self {
            item,
            parts,
            shared,
        }
    }

    // Its parts, strongest first, decay through the picks so far and through its own earlier
    // parts, as if each were picked in turn.
    fn worth(&self, covered: &HashMap<Facet, i32>, decay: f64) -> f64 {
        let mut own: Vec<Facet> = Vec::new();
        let times = |fs: &[Facet], own: &[Facet]| {
            fs.iter()
                .map(|f| {
                    covered.get(f).copied().unwrap_or(0)
                        + own.iter().filter(|o| *o == f).count() as i32
                })
                .sum()
        };
        let mut parts = 0.0;
        for (base, fs) in &self.parts {
            parts += base * decay.powi(times(fs, &own));
            own.extend(fs);
        }
        parts * decay.powi(times(&self.shared, &[]))
    }

    fn facets(&self) -> impl Iterator<Item = &Facet> {
        self.parts.iter().flat_map(|(_, fs)| fs).chain(&self.shared)
    }
}

// Greedy: the worthiest candidate given the facets the picks so far cover, `n` times at most;
// ties go to the earlier candidate. O(n · candidates · facets).
fn select<T>(mut left: Vec<Candidate<T>>, n: usize, decay: f64) -> Vec<T> {
    let mut covered: HashMap<Facet, i32> = HashMap::new();
    let mut picked = Vec::with_capacity(n);
    while picked.len() < n && !left.is_empty() {
        let (i, _) = left.iter().enumerate().fold((0, f64::MIN), |best, (i, c)| {
            let w = c.worth(&covered, decay);
            if w > best.1 {
                (i, w)
            } else {
                best
            }
        });
        let c = left.remove(i);
        for f in c.facets() {
            *covered.entry(*f).or_default() += 1;
        }
        picked.push(c.item);
    }
    picked
}

// The filtered authors of authorship rows, with each row's id.
fn ship_authors<'a>(
    gets: &'a Getters,
    ships: &'a [VaST<WorkAnyAuthorships>],
) -> impl Iterator<Item = (usize, AuthorId)> + 'a {
    ships.iter().filter_map(|s| {
        let (filtered, id) = reverse_prefixed_n(s.to_usize());
        filtered.then(|| (id, *gets.fshipa(&id)))
    })
}

// The dm ids of the first `n` entities of the top-mean ordering that `keep` admits.
fn top_ranked<E: Entity>(
    ns: &NameStateMap,
    n: usize,
    keep: impl Fn(usize) -> bool,
) -> Box<[usize]> {
    let state = &ns[E::NAME];
    let order = state.orderings.by(TOP_MEAN).expect("a top-mean ordering");
    order
        .iter()
        .map(|&rid| &state.responses[rid as usize])
        .map(|r| r.dm_id)
        .filter(|&dm| keep(dm))
        .take(n)
        .collect()
}

// Each of `len` dm ids' rank in `ranked`, from 0.
fn ranks(ranked: &[usize], len: usize) -> Box<[Option<u16>]> {
    let mut out = vec![None; len];
    for (rank, &dm) in ranked.iter().enumerate() {
        out[dm] = Some(rank as u16);
    }
    out.into_boxed_slice()
}

// A rank from 0 in a pool of `size` as a strength, higher nearer the top.
fn rank_strength(rank: usize, size: usize) -> f64 {
    (size - rank) as f64
}

fn strength_rank(strength: f64, size: usize) -> usize {
    size - strength as usize
}

fn is_review_journal(name: &str) -> bool {
    let words: Vec<String> = name
        .split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty())
        .map(str::to_lowercase)
        .collect();
    REVIEW_JOURNAL_PHRASES
        .iter()
        .any(|phrase| words.windows(phrase.len()).any(|w| w == *phrase))
}

// A subfield's tightest ladder band, None where its cohort is empty.
fn star_band(authors: &RootColumns, sf: usize) -> Option<u32> {
    let band = authors.cit_rank_ladder[sf][LADDER_LEN - 1];
    (band != u32::MAX && band > 0).then_some(band)
}

// One pass over every author's citations per subfield, whose mapped pages it then releases, so the
// file is resident only while the table is built.
fn star_table(authors: &RootColumns) -> Stars {
    let citing = &authors
        .subfields
        .as_ref()
        .expect("author subfield profiles")
        .citing;
    let bands: Vec<Option<u32>> = (0..authors.cit_rank_ladder.len())
        .map(|sf| star_band(authors, sf))
        .collect();
    let mut stars = vec![Vec::new(); bands.len()];
    for a in 0..citing.len() {
        for (sf, &fc) in citing.row(a).iter().enumerate() {
            if bands[sf].is_some_and(|band| fc >= band) {
                stars[sf].push((AuthorId::from_usize(a), fc));
            }
        }
    }
    citing.release();
    stars.into_iter().map(Vec::into_boxed_slice).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cand(name: &'static str, parts: Vec<(f64, Vec<Facet>)>) -> Candidate<&'static str> {
        Candidate::new(name, parts, vec![])
    }

    fn apex(name: &'static str, base: f64) -> Candidate<&'static str> {
        cand(
            name,
            vec![(
                base,
                vec![Facet::Kind(HighlightKind::Apex), Facet::Journal(1)],
            )],
        )
    }

    #[test]
    fn a_rarer_kind_outranks_more_of_one() {
        let picked = select(
            vec![
                apex("nature-1", 3.0),
                apex("nature-2", 3.0),
                apex("nature-3", 3.0),
                cand(
                    "laureate",
                    vec![(1.0, vec![Facet::Kind(HighlightKind::Laureate)])],
                ),
            ],
            3,
            HIGHLIGHT_RULES.decay,
        );
        // The second apex pick is decayed through its kind and its journal.
        assert_eq!(picked, vec!["nature-1", "laureate", "nature-2"]);
    }

    #[test]
    fn a_paper_covering_two_kinds_comes_first() {
        let picked = select(
            vec![
                apex("nature", 2.0),
                cand(
                    "nature-by-laureate",
                    vec![
                        (
                            2.0,
                            vec![Facet::Kind(HighlightKind::Apex), Facet::Journal(1)],
                        ),
                        (1.0, vec![Facet::Kind(HighlightKind::Laureate)]),
                    ],
                ),
            ],
            1,
            HIGHLIGHT_RULES.decay,
        );
        assert_eq!(picked, vec!["nature-by-laureate"]);
    }

    #[test]
    fn papers_citing_one_work_decay_together() {
        let hit = |name, cited| {
            Candidate::new(
                name,
                vec![(1.0, vec![Facet::Kind(HighlightKind::Hit)])],
                vec![Facet::Cited(cited)],
            )
        };
        let picked = select(
            vec![hit("a", 7), hit("b", 7), hit("c", 8)],
            2,
            HIGHLIGHT_RULES.decay,
        );
        assert_eq!(picked, vec!["a", "c"]);
    }

    #[test]
    fn parts_of_one_kind_decay_within_a_paper() {
        let star = |person| {
            (
                1.0,
                vec![Facet::Kind(HighlightKind::Star), Facet::Person(person)],
            )
        };
        let two_stars = cand("two-stars", vec![star(1), star(2)]);
        assert_eq!(
            two_stars.worth(&HashMap::new(), HIGHLIGHT_RULES.decay),
            1.0 + HIGHLIGHT_RULES.decay
        );
    }

    #[test]
    fn review_journals_are_named_by_whole_phrases() {
        for review in [
            "Chemical Reviews",
            "Nature reviews. Cancer",
            "Annual Review of Biochemistry",
            "Trends in Ecology & Evolution",
            "Current Opinion in Cell Biology",
        ] {
            assert!(is_review_journal(review), "{review}");
        }
        for research in [
            "Physical Review Letters",
            "American Economic Review",
            "Advances in Neural Information Processing Systems",
            "Environmental Health Perspectives",
            "Progress in Photovoltaics Research and Applications",
            "Previews of Physics",
        ] {
            assert!(!is_review_journal(research), "{research}");
        }
    }

    #[test]
    fn rarity_counts_the_sample_at_least_as_strong() {
        let reference = Reference::new(&[
            [Some(2.0), None, None, None, None],
            [Some(5.0), None, Some(1.0), None, None],
            [None, None, None, None, None],
            [Some(9.0), None, None, None, None],
        ]);
        assert_eq!(reference.rarity(HighlightKind::Hit, 5.0), 0.5);
        assert_eq!(reference.rarity(HighlightKind::Hit, 10.0), 0.0);
        assert_eq!(reference.rarity(HighlightKind::Laureate, 1.0), 0.25);
        assert!(reference.worth(0.0) > reference.worth(0.25));
    }
}
