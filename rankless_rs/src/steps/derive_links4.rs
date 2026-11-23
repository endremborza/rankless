use std::{io, sync::Arc};

use dmove::{
    para_multi_gen_run, BigId, Entity, LoadedIdMap, MarkedAttribute, NamespacedEntity,
    UnsignedNumber, VarAttBuilder, VariableSizeAttribute, ET, MAA,
};

use crate::{
    common::{
        reverse_id, CitRankLadderMarker, EmptyAttributeEntity, HIndexMarker, HIndexSinceMarker,
        HitWorkMarker, MainWorkMarker, ScoredPaperCountMarker, TopMeanPaperScoreMarker,
        WeightedPaperScoreMarker,
    },
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{WorkAnyAuthorships, WorkYears},
        derive_links1::WorkInstitutions,
        derive_links2::{WorkCitingCounts, WorkCountries},
        derive_links3::{
            HitPapers, HitPapersCiteCounts, HitPapersDois, HitPapersNames, HitPapersWids, WorkBars,
        },
    },
    ladder,
    metrics::{summarize, top_n, Paper, PaperSetSummary, H_SINCE},
    peers::{self, PeerCalculator},
    steps::a1_entity_mapping::{YearInterface, Years},
    CiteCountMarker, NameExtensionMarker, NameMarker, QuickestBox, QuickestNumbered, ReadIter,
    Stowage, N_PEERS,
};

fn sorted_hit_papers<E>(
    parc: &(
        Stowage,
        LoadedIdMap<ET<HitPapers>>,
        Box<[ET<WorkCitingCounts>]>,
    ),
) where
    E: MarkedAttribute<MainWorkMarker>,
    MAA<E, MainWorkMarker>: Entity<T = Box<[ET<Works>]>> + NamespacedEntity + VariableSizeAttribute,
{
    let hits = parc
        .0
        .get_entity_interface::<MAA<E, MainWorkMarker>, ReadIter>()
        .map(|e| {
            let mut v: Vec<(ET<HitPapers>, usize)> = e
                .iter()
                .filter_map(|wid| match parc.1 .0.get(&(*wid as BigId)) {
                    Some(hw) => Some((*hw, wid.to_usize())),
                    None => None,
                })
                .collect();
            v.sort_by(|l, r| parc.2[r.1].cmp(&parc.2[l.1]));
            v.into_iter()
                .map(|(hid, _)| hid)
                .collect::<Vec<ET<HitPapers>>>()
                .into_boxed_slice()
        });
    parc.0
        .declare_iter::<VarAttBuilder, _, _, E, HitWorkMarker>(hits, &format!("{}-hits", E::NAME));
}

impl MarkedAttribute<NameMarker> for HitPapers {
    type AttributeEntity = HitPapersNames;
}

impl MarkedAttribute<CiteCountMarker> for HitPapers {
    type AttributeEntity = HitPapersCiteCounts;
}

impl MarkedAttribute<MainWorkMarker> for HitPapers {
    type AttributeEntity = HitPapersWids;
}

impl MarkedAttribute<NameExtensionMarker> for HitPapers {
    type AttributeEntity = EmptyAttributeEntity<String>;
}

// The per-work columns a paper is scored from.
struct ScoreCols<'a> {
    bars: &'a [ET<WorkBars>],
    citations: &'a [ET<WorkCitingCounts>],
    years: &'a [ET<Years>],
}

struct HitPaperPeerCtx {
    pub filter: Vec<bool>,
    cit_counts: Box<[ET<HitPapersCiteCounts>]>,
}

impl ScoreCols<'_> {
    fn paper(&self, wid: usize, team: Option<&[u16]>) -> Paper {
        Paper {
            citations: self.citations[wid].to_usize() as u32,
            bar: self.bars[wid],
            year: YearInterface::reverse(self.years[wid]),
            team: team.map_or(1, |t| t[wid] as usize),
        }
    }
}

impl HitPaperPeerCtx {
    fn new(stowage: &Stowage) -> Self {
        let cit_counts = stowage.get_entity_interface::<HitPapersCiteCounts, QuickestBox>();
        let filter = vec![true; cit_counts.len()];
        Self { filter, cit_counts }
    }

    fn ln_cites(&self, idx: usize) -> f32 {
        (self.cit_counts[idx].to_usize() as f32).max(1.0).ln()
    }
}

impl PeerCalculator for HitPaperPeerCtx {
    type E = HitPapers;
    type EmbBasis = [f32; 1];
    const N_CANDIDATES: usize = 10_000;

    fn get_embedding_basis(&self) -> Box<[Self::EmbBasis]> {
        self.cit_counts
            .iter()
            .map(|c| [c.to_usize() as f32])
            .collect()
    }

    fn pair_distance(&self, a: usize, b: usize) -> f64 {
        (self.ln_cites(a) - self.ln_cites(b)).powi(2) as f64
    }
}

pub fn main(stowage: Stowage) -> io::Result<()> {
    let hit_map = stowage.get_entity_interface::<HitPapers, QuickestNumbered>();
    let wcc = stowage.get_entity_interface::<WorkCitingCounts, QuickestBox>();
    let w_years = stowage.get_entity_interface::<WorkYears, QuickestBox>();
    score_roots(&stowage, &wcc, &w_years);

    let parc = Arc::new((stowage, hit_map, wcc));
    para_multi_gen_run!(sorted_hit_papers, Institutions, Authors, Countries, Sources, Subfields, Topics; parc).last();

    let hit_to_wid = reverse_id::<HitPapers>(&parc.0);
    let wid_to_oa = reverse_id::<Works>(&parc.0);
    let hit_sem_ids = parc
        .0
        .get_entity_interface::<HitPapersDois, ReadIter>()
        .enumerate()
        .map(|(hit, doi)| {
            if doi.is_empty() {
                format!("w{}", wid_to_oa[hit_to_wid[hit].to_usize()])
            } else {
                doi
            }
        });
    parc.0.decsem::<HitPapers, _>(hit_sem_ids);
    let hp_ctx = HitPaperPeerCtx::new(&parc.0);
    let hp_ccounts: Vec<usize> = hp_ctx.cit_counts.iter().map(|c| c.to_usize()).collect();
    peers::compute_peers::<1, N_PEERS, _, _>(&parc.0, &hp_ctx, &hp_ctx.filter, &hp_ccounts);

    // HitPapers has no per-subfield citations, but make_ent_interfaces! requires the marker on every
    // RootInterfaceable entity. Write an all-MAX (no-standing) row per subfield so it loads uniformly.
    parc.0.ditf::<CitRankLadderMarker, HitPapers, _>(
        vec![[u32::MAX; ladder::LADDER_LEN]; Subfields::N],
        "cit-rank-ladder",
    );

    parc.0.write_code()?;
    Ok(())
}

// Every score-based column of every peer root, one `summarize` per entity.
fn score_roots(stowage: &Stowage, citations: &[ET<WorkCitingCounts>], years: &[ET<Years>]) {
    let bars = stowage.get_entity_interface::<WorkBars, QuickestBox>();
    let cols = ScoreCols {
        bars: &bars,
        citations,
        years,
    };
    let author_teams = team_sizes(
        stowage
            .get_entity_interface::<WorkAnyAuthorships, ReadIter>()
            .map(|r| r.len()),
    );
    let inst_teams = team_sizes(
        stowage
            .get_entity_interface::<WorkInstitutions, ReadIter>()
            .map(|r| r.len()),
    );
    // A work's country list keeps a 0 for an institution without a country, which is no member.
    let country_teams = team_sizes(
        stowage
            .get_entity_interface::<WorkCountries, ReadIter>()
            .map(|r| r.iter().filter(|c| c.to_usize() != 0).count()),
    );
    let cols = &cols;
    std::thread::scope(|s| {
        s.spawn(|| score_root::<Authors>(stowage, cols, Some(&author_teams), false));
        s.spawn(|| score_root::<Institutions>(stowage, cols, Some(&inst_teams), true));
        s.spawn(|| score_root::<Countries>(stowage, cols, Some(&country_teams), true));
        s.spawn(|| score_root::<Subfields>(stowage, cols, None, true));
        score_root::<Sources>(stowage, cols, None, true);
    });
}

// `team` holds each work's member count of the root's kind, None for a root without a weighted
// total; `since` adds the recent h-indices; a root without a Top-N gets no top mean.
fn score_root<E>(stowage: &Stowage, cols: &ScoreCols, team: Option<&[u16]>, since: bool)
where
    E: Entity + MarkedAttribute<MainWorkMarker>,
    MAA<E, MainWorkMarker>: Entity<T = Box<[ET<Works>]>> + NamespacedEntity + VariableSizeAttribute,
{
    let n = top_n(E::NAME).unwrap_or(0);
    let sums: Vec<PaperSetSummary> = stowage
        .get_entity_interface::<MAA<E, MainWorkMarker>, ReadIter>()
        .map(|ws| summarize(ws.iter().map(|w| cols.paper(w.to_usize(), team)), n))
        .collect();
    stowage.ditf::<ScoredPaperCountMarker, E, u32>(
        sums.iter().map(|s| s.scored).collect(),
        "scored-paper-count",
    );
    stowage.ditf::<HIndexMarker, E, u32>(sums.iter().map(|s| s.h_index).collect(), "h-index");
    if since {
        stowage.ditf::<HIndexSinceMarker, E, [u32; H_SINCE.len()]>(
            sums.iter().map(|s| s.h_since).collect(),
            "h-index-since",
        );
    }
    if team.is_some() {
        stowage.ditf::<WeightedPaperScoreMarker, E, f32>(
            sums.iter().map(|s| s.weighted as f32).collect(),
            "weighted-paper-score",
        );
    }
    if n > 0 {
        stowage.ditf::<TopMeanPaperScoreMarker, E, f32>(
            sums.iter().map(|s| s.top_mean as f32).collect(),
            "top-mean-paper-score",
        );
    }
}

fn team_sizes(counts: impl Iterator<Item = usize>) -> Box<[u16]> {
    counts
        .map(|n| u16::try_from(n).expect("a work's team fits u16"))
        .collect()
}
