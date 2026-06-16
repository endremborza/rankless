use std::{f64, sync::Arc};

use crate::{
    io::{AttributeLabel, WT},
    path_finder::RefGraph,
};
use rankless_rs::{
    common::{
        reverse_id, BeS, CitRankLadderMarker, CitSubfieldsArrayMarker, HIndexMarker, HitWorkMarker,
        MainEntity, MainWorkMarker, MarkedBackendLoader, MmapBox, NumberedEntity, QuickAttPair,
        QuickMap, QuickestBox, QuickestVBox, Stowage, Top15AuthorMarker, Top3AffCountryMarker,
        Top3CitingSfMarker, Top3JournalMarker, Top3PaperSfMarker, TopNPaperTopicMarker, WorkLoader,
        YearCentroidMarker, YearlyCitationsMarker, YearlyPapersMarker, NET,
    },
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{
            AuthorNobels, AuthorOrcids, AuthorRawCites, AuthorRawWorkCounts, AuthorWikiSlugs,
            AuthorshipDiscardedAuthor, AuthorshipFilteredAuthor, CitiesNames, CountryCodes,
            DiscardedAuthorsNames, DiscardedAuthorshipInstitutions, DiscardedAuthorshipPosition,
            FilteredAuthorshipInstitutions, FilteredAuthorshipPosition, InstCities, InstCountries,
            InstLocs, SourceYearQs, TopicSubfields, WorkAnyAuthorships, WorkBiblios, WorkDois,
            WorkReferences, WorkTopics, WorkYears, WorksNames,
        },
        derive_links1::{WorkInstitutions, WorkSubfields},
        derive_links2::{SourceStats, WorkCountries, WorkTopSource},
        derive_links3::{Coauthors, HitPapers, HitPapersBenchmarks, HitPapersCreatedTopic},
        derive_links4::{AuthorCitingHitsDirect, AuthorCitingHitsOnce},
        derive_links5::HitPaperYearlyCitations,
    },
    ladder::LADDER_LEN,
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

pub type PeerAuxMap = HashMap<&'static str, PeerAux>;

pub struct Getters {
    ifs: Interfaces,
    pub stowage: Arc<Stowage>,
    pub inst_oa: Box<[BigId]>,
    pub work_oa: Box<[BigId]>,
    pub hit_papers: Box<[WT]>,
    pub hit_wid_map: HashMap<WT, usize>,
    pub orcid_map: HashMap<ET<AuthorOrcids>, usize>,
    pub top_rels: TopRelsMap,
}

// Per-root-type peer auxiliary data loaded once at server startup: the memory-mapped per-subfield
// citation profile (used for peer subfield ranking) plus the author-only h-index / career-year
// centroid columns. Kept here, alongside `Getters`, so all `get_marked_interface` loading stays in
// the interfacing layer rather than leaking into request-handling code.
pub struct PeerAux {
    pub cit_subfields: MmapSlice<[u32; N_SUBFIELDS]>,
    pub h_indices: Option<Box<[u32]>>,
    pub year_centroids: Option<Box<[f32]>>,
}

// One representative root (any RootInterfaceable type) names each top-N record type: the record is
// `[(score, target_id); N]`, identical across root types since it depends only on the target entity
// and N, not the root. The frontend rebuilds the hero relations from these per request.
type TopSfRec = ET<MAA<Subfields, Top3PaperSfMarker>>;
type TopJournalRec = ET<MAA<Sources, Top3JournalMarker>>;
type TopAuthorRec = ET<MAA<Authors, Top15AuthorMarker>>;
type TopCountryRec = ET<MAA<Countries, Top3AffCountryMarker>>;
type TopTopicRec = ET<MAA<Topics, TopNPaperTopicMarker>>;

pub type TopRelsMap = HashMap<&'static str, TopRels>;

// Per-root-type top-N relation tables, memory-mapped (read once per entity view, never resident in
// full). Replaces the eager `RootInterfaces` load + startup `prime_relations` materialization.
// `aff_countries`/`paper_topic` are absent for hit papers (empty placeholders, no data file).
pub struct TopRels {
    pub paper_sfc: MmapSlice<TopSfRec>,
    pub citing_sfc: MmapSlice<TopSfRec>,
    pub journals: MmapSlice<TopJournalRec>,
    pub authors: MmapSlice<TopAuthorRec>,
    pub aff_countries: Option<MmapSlice<TopCountryRec>>,
    pub paper_topic: Option<MmapSlice<TopTopicRec>>,
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
        $($var_key:ident - $var_mark:ty = $var_t:ty),*;
        $($fix_key:ident - $fix_mark:ty | $fix_t:ty),*;
        $($float_key:ident : $float_mark:ty),*;
        $($oa_key:ident),*;
        $($p_trait:ident),*

    ) => {
        pub struct $S<T> where T: $T $(+ $p_trait)*
        {
            $(pub $f_key: VarBox<String>),*,
            $(pub $r_key: Box<[<T as NumAtt<$r_mark>>::Num]>),*
            $(, pub $var_key: VarBox<<T as VarAtt<$var_mark>>::VT>)*
            $(, pub $fix_key: Box<[<T as FixAtt<$fix_mark>>::FT]>)*
            $(, pub $float_key: Box<[f64]>),*
            $(, pub $oa_key: Box<[u64]>)*
        }

        impl<E> $S<E> where E: $T $(+ $p_trait)*
        {
            pub fn new(stowage: &Stowage) -> Self {
                Self {
                    $($f_key: <E as VarAtt<$f_mark>>::load(stowage)),*,
                    $($r_key: <E as FixAtt<$r_mark>>::load(stowage)),*
                    $(, $fix_key:  <E as FixAtt<$fix_mark>>::load(stowage))*
                    $(, $var_key:  <E as VarAtt<$var_mark>>::load(stowage))*
                    $(, $float_key:  <E as FloatAtt<$float_mark>>::load(stowage))*
                    $(, $oa_key: reverse_id::<E>(stowage))*
                }
            }
        }

        pub trait $T: Entity $(+ $p_trait)*
            $( + StringAtt<$f_mark>)*
            $( + NumAtt<$r_mark>)*
            $( + VarAtt<$var_mark, VT=$var_t>)*
            $( + FixAtt<$fix_mark, FT=$fix_t>)*
            $( + FloatAtt<$float_mark>)*
        {}

        impl <T> $T for T where T: Entity $(+ $p_trait)*
            $( + StringAtt<$f_mark>)*
            $( + NumAtt<$r_mark>)*
            $( + VarAtt<$var_mark, VT=$var_t>)*
            $( + FixAtt<$fix_mark, FT=$fix_t>)*
            $( + FloatAtt<$float_mark>)*
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
    hit_bms => HitPapersBenchmarks,
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

make_ent_interfaces!(
    RootInterfaces,
    RootInterfaceable,
    names => NameMarker, name_exts => NameExtensionMarker, sem_ids => SemanticIdMarker;
    wcounts -> WorkCountMarker, ccounts -> CiteCountMarker;
    hit_works - HitWorkMarker = Box<[ET<HitPapers>]>;
    yearly_papers - YearlyPapersMarker | EraRec,
    yearly_cites - YearlyCitationsMarker | EraRec,
    cit_rank_ladder - CitRankLadderMarker | [u32; LADDER_LEN],
    peers - PeerMarker | [NET<Self>; N_PEERS];;
    oa_id; MainEntity, NamespacedEntity
    // inst_rels - InstRelMarker | [InstRelation; N_RELS];;
    // ref_sfc : RefSubfieldsConcentrationMarker,
    // cit_sfc : CitSubfieldsConcentrationMarker

);

make_ent_interfaces!(
    NodeInterfaces,
    NodeInterfaceable,
    names => NameMarker;
    ccounts -> CiteCountMarker;;;;;
);

// The four core top-N tables exist for every root type; hit papers lack the country/topic tables.
macro_rules! core_top_rels {
    ($stow:expr, $E:ty) => {
        TopRels {
            paper_sfc: $stow.get_marked_interface::<$E, Top3PaperSfMarker, MmapBox>(),
            citing_sfc: $stow.get_marked_interface::<$E, Top3CitingSfMarker, MmapBox>(),
            journals: $stow.get_marked_interface::<$E, Top3JournalMarker, MmapBox>(),
            authors: $stow.get_marked_interface::<$E, Top15AuthorMarker, MmapBox>(),
            aff_countries: None,
            paper_topic: None,
        }
    };
}

fn load_top_rels_map(stow: &Stowage) -> TopRelsMap {
    let mut m: TopRelsMap = HashMap::new();
    macro_rules! full {
        ($E:ty) => {{
            let mut tr = core_top_rels!(stow, $E);
            tr.aff_countries =
                Some(stow.get_marked_interface::<$E, Top3AffCountryMarker, MmapBox>());
            tr.paper_topic = Some(stow.get_marked_interface::<$E, TopNPaperTopicMarker, MmapBox>());
            tr
        }};
    }
    m.insert(Institutions::NAME, full!(Institutions));
    m.insert(Authors::NAME, full!(Authors));
    m.insert(Subfields::NAME, full!(Subfields));
    m.insert(Countries::NAME, full!(Countries));
    m.insert(Sources::NAME, full!(Sources));
    m.insert(HitPapers::NAME, core_top_rels!(stow, HitPapers));
    m
}

pub trait StringAtt<Mark>: MarkedAttribute<Mark> + VarAtt<Mark, VT = String> {}

pub trait NumAtt<Mark>: MarkedAttribute<Mark> + FixAtt<Mark, FT = Self::Num> {
    type Num: UnsignedNumber;
}

pub trait FloatAtt<Mark>: FixAtt<Mark, FT = f64> + MarkedAttribute<Mark> {}

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

    pub fn build_peer_aux(&self) -> PeerAuxMap {
        let stow = &self.stowage;
        let mut m: PeerAuxMap = HashMap::new();
        m.insert(
            Authors::NAME,
            PeerAux {
                cit_subfields: stow
                    .get_marked_interface::<Authors, CitSubfieldsArrayMarker, MmapBox>(),
                h_indices: Some(stow.get_marked_interface::<Authors, HIndexMarker, QuickestBox>()),
                year_centroids: Some(
                    stow.get_marked_interface::<Authors, YearCentroidMarker, QuickestBox>(),
                ),
            },
        );
        m.insert(
            Institutions::NAME,
            PeerAux {
                cit_subfields: stow
                    .get_marked_interface::<Institutions, CitSubfieldsArrayMarker, MmapBox>(),
                h_indices: None,
                year_centroids: None,
            },
        );
        m.insert(
            Countries::NAME,
            PeerAux {
                cit_subfields: stow
                    .get_marked_interface::<Countries, CitSubfieldsArrayMarker, MmapBox>(),
                h_indices: None,
                year_centroids: None,
            },
        );
        m.insert(
            Sources::NAME,
            PeerAux {
                cit_subfields: stow
                    .get_marked_interface::<Sources, CitSubfieldsArrayMarker, MmapBox>(),
                h_indices: None,
                year_centroids: None,
            },
        );
        m
    }

    pub fn top_rels_for(&self, etype: &str) -> Option<&TopRels> {
        self.top_rels.get(etype)
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
        let top_rels = load_top_rels_map(&stowage);
        println!("loaded full Getters");
        Self {
            ifs,
            stowage,
            inst_oa,
            work_oa,
            hit_papers,
            hit_wid_map,
            orcid_map,
            top_rels,
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
            Some(WorksNames::NAME),
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
            top_rels: HashMap::new(),
        }
    }
}

impl<T, Mark> StringAtt<Mark> for T where T: VarAtt<Mark, VT = String> {}
impl<T, Mark> FloatAtt<Mark> for T where T: FixAtt<Mark, FT = f64> {}

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
