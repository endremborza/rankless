use std::{f64, sync::Arc};

use crate::{
    io::{AttributeLabel, WT},
    path_finder::RefGraph,
};
use rankless_rs::{
    common::{
        reverse_id, BeS, CitRankLadderMarker, CitSubfieldsArrayMarker, HIndexMarker,
        HIndexSinceMarker, HitWorkMarker, MainEntity, MainWorkMarker, MarkedBackendLoader, MmapBox,
        NumberedEntity, QuickAttPair, QuickMap, QuickestBox, QuickestVBox, RefSubfieldsArrayMarker,
        ScoredPaperCountMarker, Stowage, Top15AuthorMarker, Top3AffCountryMarker, TopJournalMarker,
        TopMeanPaperScoreMarker, TopNCitingSfMarker, TopNCitingTopicMarker, TopNPaperSfMarker,
        TopNPaperTopicMarker, WeightedPaperScoreMarker, WorkLoader, YearCentroidMarker,
        YearlyCitationsMarker, YearlyPapersMarker, NET,
    },
    env_consts::START_YEAR,
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{
            AuthorNobels, AuthorOrcids, AuthorRawCites, AuthorRawWorkCounts, AuthorWikiSlugs,
            AuthorshipDiscardedAuthor, AuthorshipFilteredAuthor, CitiesNames, CountryCodes,
            CountryPopulations, DiscardedAuthorsNames, DiscardedAuthorshipInstitutions,
            DiscardedAuthorshipPosition, FilteredAuthorshipInstitutions,
            FilteredAuthorshipPosition, InstCities, InstCountries, InstLocs, SourceYearQs,
            TopicSubfields, WorkAnyAuthorships, WorkBiblios, WorkDois, WorkReferences, WorkTopics,
            WorkYears, WorksNames,
        },
        derive_links1::{WorkInstitutions, WorkSubfields},
        derive_links2::{SourceStats, WorkCountries, WorkTopSource},
        derive_links3::{Coauthors, HitPapers, HitPapersCreatedTopic, WorkBars},
        derive_links4::{AuthorCitingHitsDirect, AuthorCitingHitsOnce},
        derive_links5::HitPaperYearlyCitations,
    },
    ladder::LADDER_LEN,
    metrics::{mean_of, paper_score, H_SINCE},
    steps::{
        a1_entity_mapping::YearInterface,
        a2_init_atts::OrcidType,
        derive_links1::{CountryInsts, WorkPeriods},
        derive_links2::EraRec,
    },
    CiteCountMarker, NameExtensionMarker, NameMarker, PeerMarker, SemanticIdMarker,
    WorkCountMarker, N_PEERS,
};

use dmove::{
    BigId, ByteArrayInterface, ByteFixArrayInterface, CompactEntity, Entity,
    EntityImmutableRefMapperBackend, Locators, MappableEntity, MarkedAttribute, MmapSlice,
    NamespacedEntity, UnsignedNumber, VaST, VarAttBuilder, VarBox, VarSizedAttributeElement,
    VariableSizeAttribute, VattArrPair, ET, MAA,
};
use hashbrown::HashMap;
use rand::Rng;

const SPEC_CORR_RATE: f64 = 0.45;
const N_SUBFIELDS: usize = Subfields::N;

type FB<E> = BeS<QuickestBox, E>;
type MB<E> = BeS<QuickMap, E>;

pub type RootColumnMap = HashMap<&'static str, RootColumns>;

pub struct Getters {
    ifs: Interfaces,
    pub stowage: Arc<Stowage>,
    pub inst_oa: Box<[BigId]>,
    pub work_oa: Box<[BigId]>,
    pub hit_papers: Box<[WT]>,
    pub hit_wid_map: HashMap<WT, usize>,
    pub orcid_map: HashMap<ET<AuthorOrcids>, usize>,
    root_columns: RootColumnMap,
}

// The per-subfield citation profile a peer ranking is computed from and the matching paper profile
// (the production-side counts); the two are written together and exist for the same root types.
pub struct SubfieldProfiles {
    pub citing: MmapSlice<[u32; N_SUBFIELDS]>,
    pub refed: MmapSlice<[u32; N_SUBFIELDS]>,
}

// One representative root (any RootInterfaceable type) names each top-N record type: the record is
// `[(score, target_id); N]`, identical across root types since it depends only on the target entity
// and N, not the root. The frontend rebuilds the hero relations from these per request.
type TopSfRec = ET<MAA<Subfields, TopNPaperSfMarker>>;
type TopJournalRec = ET<MAA<Sources, TopJournalMarker>>;
type TopAuthorRec = ET<MAA<Authors, Top15AuthorMarker>>;
type TopCountryRec = ET<MAA<Countries, Top3AffCountryMarker>>;
type TopTopicRec = ET<MAA<Topics, TopNPaperTopicMarker>>;

// Everything one root type keeps loaded for the whole run, indexed by `dm_id` and reached by etype
// string: the columns. The counting columns are resident for every root — papers, citations, the
// yearly era records, the hit papers, the peers, the citation-rank ladder, and the columns derived
// at load. The top-N relation tables are memory-mapped, read per entity view and never resident in
// full. Which relation tables a type has is a ladder: hit papers hold the four core tables alone,
// subfields add the affiliation-country and topic tables and the scored-paper count and h-index
// every peer type has, the four other peer types add the subfield profiles, and authors alone add
// the career centroid (a calendar year). Which score columns a type has beyond those follows the
// metric portfolio rather than the ladder, so each type's are loaded by name.
pub struct RootColumns {
    pub papers: Box<[u32]>,
    pub citations: Box<[u32]>,
    pub yearly_papers: Box<[EraRec]>,
    pub yearly_cites: Box<[EraRec]>,
    pub hit_works: VarBox<Box<[ET<HitPapers>]>>,
    // The length of each `hit_works` row, held flat. Redundant with the rows themselves, and kept
    // anyway: `hit_papers` and `hit_rate` are both scannable metrics, and a scan over 4-byte
    // counts reads a quarter of what a scan over the rows' fat pointers would.
    pub hit_counts: Box<[u32]>,
    pub peers: Box<[[u32; N_PEERS]]>,
    pub cit_rank_ladder: Box<[[u32; LADDER_LEN]]>,
    // Cohort mean of `papers`, the dampening constant under the root's field score.
    pub mean_papers: f64,
    // Papers with a paper score, the hit rate's denominator; a hit paper is one.
    pub scored_papers: Box<[u32]>,
    // Whether the entities have a place: institutions, whose country and city are `Getters` fixed
    // attributes.
    pub located: bool,
    pub paper_sfc: MmapSlice<TopSfRec>,
    pub citing_sfc: MmapSlice<TopSfRec>,
    pub journals: MmapSlice<TopJournalRec>,
    pub authors: MmapSlice<TopAuthorRec>,
    pub aff_countries: Option<MmapSlice<TopCountryRec>>,
    pub paper_topic: Option<MmapSlice<TopTopicRec>>,
    pub citing_topic: Option<MmapSlice<TopTopicRec>>,
    pub subfields: Option<SubfieldProfiles>,
    pub h_indices: Option<Box<[u32]>>,
    pub h_since: Option<Box<[[u32; H_SINCE.len()]]>>,
    pub weighted_paper_scores: Option<Box<[f32]>>,
    pub top_means: Option<Box<[f32]>>,
    pub population: Option<Box<[u32]>>,
    pub paper_scores: Option<Box<[f32]>>,
    pub year_centroids: Option<Box<[f32]>>,
}

macro_rules! make_interfaces {
    ($($e_key:ident > $e_t:ty),*;$($f_key:ident => $f_t:ty),*; $($v_key:ident -> $v_t:ty),*; $($loc_key:ident loc $loc_t:ty),*; $($m_key:ident >> $m_t:ty),*) => {
        rankless_rs::make_interface_struct!(Interfaces,
            $($e_key > $e_t),*;
            $($f_key => $f_t),*;
            $($v_key -> $v_t),*;
            $($loc_key loc $loc_t),*;
            $($m_key >> $m_t),*
        );

        impl Getters {

            $(
                pub fn $f_key<'a, K: UnsignedNumber>(&'a self, key: &K) -> &'a ET<$f_t> {
                    type BE = FB<$f_t>;
                    let uk = key.to_usize();
                    <BE as EntityImmutableRefMapperBackend<$f_t>>::get_ref_via_immut(&self.ifs.$f_key, &uk).expect(&format!("e: {}, k: {}", <$f_t as Entity>::NAME, uk))

                }
            )*

            $(
                pub fn $v_key<'a, K: UnsignedNumber>(&'a self, key: K) -> &'a [VaST<$v_t>] {
                    let uk = key.to_usize();
                    self.ifs.$v_key.get(&uk).expect(&format!("e: {}, k: {}", <$v_t as Entity>::NAME, uk))

                }
            )*

            $(
                pub fn $e_key<'a>(&'a self, key: ET<$e_t>) -> &'a [VaST<MAA<$e_t, MainWorkMarker>>] {
                    let uk = key.to_usize();
                    self.ifs.$e_key.get(&uk).expect(&format!("e: {} works, k: {}", <$e_t as Entity>::NAME, uk))

                }
            )*

            $(
                pub fn $m_key<'a, >(&'a self, key: &'a <$m_t as MappableEntity>::KeyType) -> &'a ET<$m_t> {
                    type BE = MB<$m_t>;
                    <BE as EntityImmutableRefMapperBackend<$m_t>>::get_ref_via_immut(&self.ifs.$m_key, &key)
                    .unwrap_or_else( ||
                        {
                            // println!("not found in map e: {}, k: {:?}", <$m_t as Entity>::NAME, key);
                            &0
                        }
                    )

                }
            )*

            $(
                pub fn $loc_key<'a>(&'a self) -> Arc<Locators<$loc_t>> {
                    self.ifs.$loc_key.clone()
                }
            )*

            pub fn works_of_entity<'a>(&'a self, key: usize, etype: String) -> Option<&'a [WT]>  {
                // This is super similar to WorksFromMemory but with a string parameter
                $(
                    if &etype == <$e_t as Entity>::NAME {
                        return Some(self.ifs.$e_key.get(&key).expect(&format!("e: {} works, k: {}", <$e_t as Entity>::NAME, key)))
                    }

                )*
                None
            }

        }
        $(
        impl WorksFromMemory for $e_t {
            fn works_from_ram(gets: &Getters, id: NET<Self>) -> &[WT] {
                gets.$e_key(id)
            }
        }
        )*

        $(
        impl LocatorsFromMemory for $loc_t {
            fn locs_from_ram(gets: &Getters) -> Arc<Locators<$loc_t>> {
                gets.$loc_key()
            }
        }
        )*

    };
}

//TODO/clarity wet pattern
macro_rules! make_ent_interfaces {
    (
        $S:ident,
        $T:ident,
        $($f_key:ident => $f_mark:ty),*;
        $($r_key:ident -> $r_mark:ty),*;
        $($oa_key:ident),*;
        $($p_trait:ident),*

    ) => {
        pub struct $S<T> where T: $T $(+ $p_trait)*
        {
            $(pub $f_key: VarBox<String>),*,
            $(pub $r_key: Box<[<T as NumAtt<$r_mark>>::Num]>),*
            $(, pub $oa_key: Box<[u64]>)*
        }

        impl<E> $S<E> where E: $T $(+ $p_trait)*
        {
            pub fn new(stowage: &Stowage) -> Self {
                Self {
                    $($f_key: <E as VarAtt<$f_mark>>::load(stowage)),*,
                    $($r_key: <E as FixAtt<$r_mark>>::load(stowage)),*
                    $(, $oa_key: reverse_id::<E>(stowage))*
                }
            }
        }

        pub trait $T: Entity $(+ $p_trait)*
            $( + StringAtt<$f_mark>)*
            $( + NumAtt<$r_mark>)*
        {}

        impl <T> $T for T where T: Entity $(+ $p_trait)*
            $( + StringAtt<$f_mark>)*
            $( + NumAtt<$r_mark>)*
        {}

    };
}

make_interfaces!(
    citing > Works,
    cworks > Countries,
    iworks > Institutions,
    aworks > Authors,
    soworks > Sources,
    sfworks > Subfields,
    hit_wids > HitPapers;
    year => WorkYears,
    top_source => WorkTopSource,
    wperiod => WorkPeriods,
    source_stats => SourceStats,
    tsuf => TopicSubfields,
    icountry => InstCountries,
    icity => InstCities,
    iloc => InstLocs,
    ccodes => CountryCodes,
    fshipa => AuthorshipFilteredAuthor,
    dshipa => AuthorshipDiscardedAuthor,
    fship_pos => FilteredAuthorshipPosition,
    dship_pos => DiscardedAuthorshipPosition,
    author_prizes => AuthorNobels,
    author_orcids => AuthorOrcids,
    raw_cites => AuthorRawCites,
    raw_works => AuthorRawWorkCounts,
    wbar => WorkBars,
    hit_created_topic => HitPapersCreatedTopic;
    wrefs -> WorkReferences,
    wtopics -> WorkTopics,
    wsubfields -> WorkSubfields,
    winsts -> WorkInstitutions,
    wanyships -> WorkAnyAuthorships,
    wcountries -> WorkCountries,
    wbiblios -> WorkBiblios,
    fshipis -> FilteredAuthorshipInstitutions,
    dshipis -> DiscardedAuthorshipInstitutions,
    cinames -> CitiesNames,
    aslugs -> AuthorWikiSlugs,
    coathors -> Coauthors,
    author_citing_direct -> AuthorCitingHitsDirect,
    author_citing_once -> AuthorCitingHitsOnce,
    hit_yearlies -> HitPaperYearlyCitations,
    country_insts -> CountryInsts;
    dan_locators loc DiscardedAuthorsNames,
    doi_locators loc WorkDois,
    wn_locators loc WorksNames;
    sqy >> SourceYearQs
);

// The search side of a root type: names, semantic ids and OpenAlex ids, loaded at startup and
// dropped once the search state is built; every counting column lives in `RootColumns`.
make_ent_interfaces!(
    RootInterfaces,
    RootInterfaceable,
    names => NameMarker, name_exts => NameExtensionMarker, sem_ids => SemanticIdMarker;
    ccounts -> CiteCountMarker;
    oa_id; MainEntity, NamespacedEntity
);

make_ent_interfaces!(
    NodeInterfaces,
    NodeInterfaceable,
    names => NameMarker;
    ccounts -> CiteCountMarker;;
);

// The pipeline stores the career centroid as an index on the year axis; served as a calendar year.
fn centroid_years(mut centroids: Box<[f32]>) -> Box<[f32]> {
    for c in centroids.iter_mut() {
        *c += START_YEAR as f32;
    }
    centroids
}

// Paper and citation counts as u32 by dm id; a root without work counts (hit papers) counts one
// paper per entity.
fn counts<E>(stow: &Stowage) -> (Box<[u32]>, Box<[u32]>)
where
    E: NumAtt<WorkCountMarker> + NumAtt<CiteCountMarker>,
{
    let ccounts = <E as FixAtt<CiteCountMarker>>::load(stow);
    let wcounts = <E as FixAtt<WorkCountMarker>>::load(stow);
    let citations: Box<[u32]> = ccounts.iter().map(|c| c.to_usize() as u32).collect();
    let papers = (0..citations.len())
        .map(|i| wcounts.get(i).map_or(1, |w| w.to_usize() as u32))
        .collect();
    (papers, citations)
}

fn load_root_columns(stow: &Stowage) -> RootColumnMap {
    macro_rules! load {
        ($E:ty, $M:ty) => {
            stow.get_marked_interface::<$E, $M, QuickestBox>()
        };
    }
    // One rung per tier of the ladder, each built on the one below it, so a root type is declared
    // by naming how far up it goes.
    macro_rules! cols {
        ($E:ty) => {{
            let (papers, citations) = counts::<$E>(stow);
            let hit_works = <$E as VarAtt<HitWorkMarker>>::load(stow);
            let hit_counts: Box<[u32]> = (0..papers.len())
                .map(|dm| hit_works.0.get(dm).map_or(0, |h| h.len() as u32))
                .collect();
            // The field score's dampener, over every dm id but 0, the padding entity. That is a
            // wider population than the page filter (`derive_links3::entity_sem_ids`) keeps, so
            // the constant describes more entities than the score is ever shown for.
            let mean_papers = mean_of(papers.iter().skip(1).copied());
            RootColumns {
                scored_papers: papers.clone(),
                papers,
                citations,
                yearly_papers: <$E as FixAtt<YearlyPapersMarker>>::load(stow),
                yearly_cites: <$E as FixAtt<YearlyCitationsMarker>>::load(stow),
                hit_works,
                hit_counts,
                peers: <$E as FixAtt<PeerMarker>>::load(stow)
                    .iter()
                    .map(|row| row.map(|e| e.to_usize() as u32))
                    .collect(),
                cit_rank_ladder: <$E as FixAtt<CitRankLadderMarker>>::load(stow),
                mean_papers,
                located: <$E as Entity>::NAME == Institutions::NAME,
                paper_sfc: stow.get_marked_interface::<$E, TopNPaperSfMarker, MmapBox>(),
                citing_sfc: stow.get_marked_interface::<$E, TopNCitingSfMarker, MmapBox>(),
                journals: stow.get_marked_interface::<$E, TopJournalMarker, MmapBox>(),
                authors: stow.get_marked_interface::<$E, Top15AuthorMarker, MmapBox>(),
                aff_countries: None,
                paper_topic: None,
                citing_topic: None,
                subfields: None,
                h_indices: None,
                h_since: None,
                weighted_paper_scores: None,
                top_means: None,
                population: None,
                paper_scores: None,
                year_centroids: None,
            }
        }};
        ($E:ty, topics) => {{
            let mut c = cols!($E);
            c.aff_countries =
                Some(stow.get_marked_interface::<$E, Top3AffCountryMarker, MmapBox>());
            c.paper_topic = Some(stow.get_marked_interface::<$E, TopNPaperTopicMarker, MmapBox>());
            c.citing_topic =
                Some(stow.get_marked_interface::<$E, TopNCitingTopicMarker, MmapBox>());
            c.scored_papers = load!($E, ScoredPaperCountMarker);
            c.h_indices = Some(load!($E, HIndexMarker));
            c
        }};
        ($E:ty, profiles) => {{
            let mut c = cols!($E, topics);
            c.subfields = Some(SubfieldProfiles {
                citing: stow.get_marked_interface::<$E, CitSubfieldsArrayMarker, MmapBox>(),
                refed: stow.get_marked_interface::<$E, RefSubfieldsArrayMarker, MmapBox>(),
            });
            c
        }};
        ($E:ty, author_only) => {{
            let mut c = cols!($E, profiles);
            c.year_centroids = Some(centroid_years(
                stow.get_marked_interface::<$E, YearCentroidMarker, QuickestBox>(),
            ));
            c
        }};
    }
    std::thread::scope(|sc| {
        [
            sc.spawn(|| {
                let mut c = cols!(Authors, author_only);
                c.weighted_paper_scores = Some(load!(Authors, WeightedPaperScoreMarker));
                c.top_means = Some(load!(Authors, TopMeanPaperScoreMarker));
                (Authors::NAME, c)
            }),
            sc.spawn(|| {
                let mut c = cols!(Institutions, profiles);
                c.h_since = Some(load!(Institutions, HIndexSinceMarker));
                c.weighted_paper_scores = Some(load!(Institutions, WeightedPaperScoreMarker));
                c.top_means = Some(load!(Institutions, TopMeanPaperScoreMarker));
                (Institutions::NAME, c)
            }),
            sc.spawn(|| {
                let mut c = cols!(Countries, profiles);
                c.h_since = Some(load!(Countries, HIndexSinceMarker));
                c.weighted_paper_scores = Some(load!(Countries, WeightedPaperScoreMarker));
                c.top_means = Some(load!(Countries, TopMeanPaperScoreMarker));
                c.population = Some(stow.get_entity_interface::<CountryPopulations, QuickestBox>());
                (Countries::NAME, c)
            }),
            sc.spawn(|| {
                let mut c = cols!(Sources, profiles);
                c.h_since = Some(load!(Sources, HIndexSinceMarker));
                c.top_means = Some(load!(Sources, TopMeanPaperScoreMarker));
                (Sources::NAME, c)
            }),
            sc.spawn(|| {
                let mut c = cols!(Subfields, topics);
                c.h_since = Some(load!(Subfields, HIndexSinceMarker));
                (Subfields::NAME, c)
            }),
            sc.spawn(|| (HitPapers::NAME, cols!(HitPapers))),
        ]
        .into_iter()
        .map(|h| h.join().expect("root columns"))
        .collect()
    })
}

pub trait StringAtt<Mark>: MarkedAttribute<Mark> + VarAtt<Mark, VT = String> {}

pub trait NumAtt<Mark>: MarkedAttribute<Mark> + FixAtt<Mark, FT = Self::Num> {
    type Num: UnsignedNumber;
}

pub trait FixAtt<Mark>: MarkedAttribute<Mark> {
    type FT: ByteFixArrayInterface;
    fn load(stowage: &Stowage) -> Box<[Self::FT]>;
}

pub trait VarAtt<Mark>: MarkedAttribute<Mark> {
    type VT: ByteArrayInterface;
    fn load(stowage: &Stowage) -> VarBox<Self::VT>;
}

pub trait WorksFromMemory: MarkedAttribute<MainWorkMarker> + NumberedEntity {
    fn works_from_ram(gets: &Getters, id: NET<Self>) -> &[WT];
}

pub trait LocatorsFromMemory: VariableSizeAttribute + Sized
where
    ET<Self>: VarSizedAttributeElement,
{
    fn locs_from_ram(gets: &Getters) -> Arc<Locators<Self>>;
}

impl<E> NodeInterfaces<E>
where
    E: NodeInterfaceable,
{
    pub fn into_stats_entry(self, full_cc: f64) -> (String, Box<[AttributeLabel]>) {
        let names: Box<[Arc<str>]> = (&self.names).into();
        make_stats_entry_arc::<E>(&names, &[], &self.ccounts, full_cc)
    }
}

impl Getters {
    pub fn total_cite_count(&self) -> f64 {
        // let div: usize = <ET<WorksCiting> as VarSizedAttributeElement>::DIVISOR;
        let o = self
            .ifs
            .citing
            .locators
            .divided_sizes
            .iter()
            .map(|e| e.to_usize())
            .sum::<usize>() as u32;
        f64::from(o)
    }

    pub fn wccount(&self, wid: usize) -> usize {
        self.ifs.citing.locators.divided_sizes[wid].to_usize()
    }

    pub fn columns_for(&self, etype: &str) -> Option<&RootColumns> {
        self.root_columns.get(etype)
    }

    pub fn new(stowage: Arc<Stowage>) -> Self {
        let inst_oa = reverse_id::<Institutions>(&stowage);
        let work_oa = reverse_id::<Works>(&stowage);
        let hit_papers: Box<[WT]> = reverse_id::<HitPapers>(&stowage)
            .iter()
            .map(|e| WT::from_usize(e.to_usize()))
            .collect();
        let hit_wid_map: HashMap<WT, usize> =
            HashMap::from_iter(hit_papers.iter().enumerate().map(|(hwi, e)| (*e, hwi)));
        let mut orcid_map = HashMap::new();
        let ifs = Interfaces::new(stowage.clone());
        let na_orcid = OrcidType::default();
        ifs.author_orcids
            .iter()
            .enumerate()
            .for_each(|(aid, orcid_id)| {
                if orcid_id != &na_orcid {
                    orcid_map.insert(*orcid_id, aid);
                }
            });
        let root_columns = load_root_columns(&stowage);
        let mut gets = Self {
            ifs,
            stowage,
            inst_oa,
            work_oa,
            hit_papers,
            hit_wid_map,
            orcid_map,
            root_columns,
        };
        gets.score_hit_papers();
        println!("loaded full Getters");
        gets
    }

    // The hit-paper root's paper scores, from each hit's stored bar and its citations.
    fn score_hit_papers(&mut self) {
        let cols = &self.root_columns[HitPapers::NAME];
        let scores = self
            .hit_papers
            .iter()
            .zip(cols.citations.iter())
            .map(|(wid, &c)| paper_score(c, *self.wbar(wid)).unwrap_or(0.0) as f32)
            .collect();
        if let Some(cols) = self.root_columns.get_mut(HitPapers::NAME) {
            cols.paper_scores = Some(scores);
        }
    }

    pub fn fake() -> Self {
        let id: u64 = rand::thread_rng().gen();
        let mut stowage = Stowage::new(&format!("/tmp/tmp-stow/{id}"));

        stowage.set_namespace("a2_init_atts");
        let last = (1..200)
            .map(|e| e.to_string())
            .collect::<Vec<String>>()
            .join(".");
        stowage.add_iter_owned::<VarAttBuilder, _, _>(
            ["W0", "W1", "W2", "W3", &last]
                .iter()
                .map(|e| e.to_string()),
            WorksNames::NAME,
        );

        let mut ifs = Interfaces::fake();
        //TODO a hack for testing
        ifs.year = YearInterface::iter().collect();
        Self {
            stowage: Arc::new(stowage),
            ifs,
            inst_oa: Vec::new().into(),
            work_oa: (0..20000000).collect::<Vec<BigId>>().into(),
            hit_papers: Vec::new().into(),
            hit_wid_map: HashMap::new(),
            orcid_map: HashMap::new(),
            root_columns: HashMap::new(),
        }
    }
}

impl<T, Mark> StringAtt<Mark> for T where T: VarAtt<Mark, VT = String> {}

impl<T, Mark> NumAtt<Mark> for T
where
    T: FixAtt<Mark, FT = ET<MAA<Self, Mark>>>,
    ET<MAA<T, Mark>>: UnsignedNumber,
{
    type Num = ET<MAA<Self, Mark>>;
}

impl<T, Mark> FixAtt<Mark> for T
where
    T: MarkedAttribute<Mark>,
    MAA<T, Mark>: CompactEntity + MarkedBackendLoader<QuickestBox, BE = Box<[ET<MAA<T, Mark>>]>>,
    ET<MAA<T, Mark>>: ByteFixArrayInterface,
{
    type FT = ET<MAA<Self, Mark>>;
    fn load(stowage: &Stowage) -> Box<[Self::FT]> {
        stowage.get_marked_interface::<Self, Mark, QuickestBox>()
    }
}

impl<T, Mark> VarAtt<Mark> for T
where
    T: MarkedAttribute<Mark>,
    MAA<T, Mark>: CompactEntity + MarkedBackendLoader<QuickestVBox, BE = VarBox<ET<MAA<T, Mark>>>>,
    ET<MAA<T, Mark>>: ByteArrayInterface + VarSizedAttributeElement,
{
    type VT = ET<MAA<Self, Mark>>;
    fn load(stowage: &Stowage) -> VarBox<Self::VT> {
        stowage.get_marked_interface::<Self, Mark, QuickestVBox>()
    }
}

impl RefGraph for Getters {
    fn get_refs(&self, wid: WT) -> &[WT] {
        self.wrefs(wid)
    }
    fn get_cites(&self, wid: WT) -> &[WT] {
        self.citing(wid)
    }
}

pub fn make_stats_entry_arc<E>(
    names: &[Arc<str>],
    sem_ids: &[Arc<str>],
    ccounts: &[<E as NumAtt<CiteCountMarker>>::Num],
    full_cc: f64,
) -> (String, Box<[AttributeLabel]>)
where
    E: NodeInterfaceable,
{
    const SPEC_RATE: f64 = 1.0 - SPEC_CORR_RATE;
    let numer_add = (full_cc / f64::from(E::N as u32)) * SPEC_CORR_RATE;
    let empty: Arc<str> = Arc::<str>::from("");
    //no double enumerate because nodes feed empty sem_ids
    let elevel = names
        .iter()
        .enumerate()
        .map(|(i, name)| {
            //TODO: u32 counts (max 4B) need to be ensured
            let numer = f64::from(ccounts[i].to_usize() as u32) * SPEC_RATE + numer_add;
            let spec_baseline = numer / full_cc;
            let semantic_id = if let Some(sem_id) = sem_ids.get(i) {
                if !sem_id.is_empty() {
                    sem_id.clone()
                } else {
                    empty.clone()
                }
            } else {
                empty.clone()
            };
            AttributeLabel {
                name: name.clone(),
                semantic_id,
                spec_baseline,
            }
        })
        .collect();
    (E::NAME.to_string(), elevel)
}
