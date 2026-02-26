use std::{f64, sync::Arc};

use crate::{
    ids::AttributeLabelUnion,
    io::{AttributeLabel, WT},
    path_finder::RefGraph,
};
use rankless_rs::{
    common::{
        init_empty_slice, BeS, HitWorkMarker, MainEntity, MainWorkMarker, MarkedBackendLoader,
        NumberedEntity, QuickAttPair, QuickMap, QuickestBox, QuickestVBox, Stowage,
        Top15AuthorMarker, Top3AffCountryMarker, Top3CitingSfMarker, Top3JournalMarker,
        Top3PaperSfMarker, Top3PaperTopicMarker, WorkLoader, YearlyCitationsMarker,
        YearlyPapersMarker, NET,
    },
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{
            AuthorOrcids, AuthorRawCites, AuthorRawWorkCounts, AuthorWikiSlugs,
            AuthorshipDiscardedAuthor, AuthorshipFilteredAuthor, CitiesNames, CountryCodes,
            DiscardedAuthorsNames, DiscardedAuthorshipInstitutions, FilteredAuthorshipInstitutions,
            InstCities, InstCountries, InstLocs, SourceYearQs, TopicSubfields, WorkAnyAuthorships,
            WorkBiblios, WorkDois, WorkReferences, WorkTopics, WorkYears, WorksNames,
        },
        derive_links1::{WorkInstitutions, WorkSubfields},
        derive_links2::{AuthorNobels, SourceStats, WorkCountries, WorkTopSource},
        derive_links3::{Coauthors, HitPapers, HitPapersDois, HitPapersNames},
        derive_links4::{AuthorCitingHitsDirect, AuthorCitingHitsOnce},
        derive_links5::HitPaperYearlyCitations,
    },
    steps::{
        a1_entity_mapping::YearInterface,
        derive_links1::{CountryInsts, WorkPeriods},
        derive_links2::{EraRec, Top15Rec, Top3Rec},
    },
    CiteCountMarker, NameExtensionMarker, NameMarker, QuickestNumbered, ReadFixIter,
    SemanticIdMarker, WorkCountMarker,
};

use dmove::{
    BackendLoading, BigId, ByteArrayInterface, ByteFixArrayInterface, CompactEntity, Entity,
    EntityImmutableRefMapperBackend, Locators, MappableEntity, MarkedAttribute, NamespacedEntity,
    UnsignedNumber, VaST, VarAttBuilder, VarBox, VarSizedAttributeElement, VariableSizeAttribute,
    VattArrPair, ET, MAA,
};
use hashbrown::HashMap;
use rand::Rng;

const SPEC_CORR_RATE: f64 = 0.45;

type VB<E> = BeS<QuickAttPair, E>;
type FB<E> = BeS<QuickestBox, E>;
type MB<E> = BeS<QuickMap, E>;

pub struct Getters {
    ifs: Interfaces,
    pub stowage: Arc<Stowage>,
    pub inst_oa: Box<[BigId]>,
    pub work_oa: Box<[BigId]>,
    pub hit_papers: Box<[WT]>,
    pub hit_wid_map: HashMap<WT, usize>,
    pub orcid_map: HashMap<ET<AuthorOrcids>, usize>,
}

macro_rules! make_interfaces {
    ($($e_key:ident > $e_t:ty),*;$($f_key:ident => $f_t:ty),*; $($v_key:ident -> $v_t:ty),*; $($loc_key:ident loc $loc_t:ty),*; $($m_key:ident >> $m_t:ty),*) => {
        struct Interfaces {
            $($e_key: VB<MAA<$e_t, MainWorkMarker>>,)*
            $($f_key: FB<$f_t>,)*
            $($v_key: VB<$v_t>,)*
            $($m_key: MB<$m_t>,)*
            $($loc_key: Arc<Locators<$loc_t>>,)*
        }

        impl Interfaces {
            fn new(stowage: Arc<Stowage>) -> Self {

                $(
                    let stowage_clone = Arc::clone(&stowage);
                    let $e_key = std::thread::spawn( move || {
                        <$e_t as WorkLoader>::load_work_interface(stowage_clone)
                    });
                )*
                $(
                    let stowage_clone = Arc::clone(&stowage);
                    let $f_key = std::thread::spawn( move || {
                        stowage_clone.get_entity_interface::<$f_t, QuickestBox>()
                    });
                )*
                $(
                    let stowage_clone = Arc::clone(&stowage);
                    let $v_key = std::thread::spawn( move || {
                        stowage_clone.get_entity_interface::<$v_t, QuickAttPair>()
                    });
                )*
                $(
                    let stowage_clone = Arc::clone(&stowage);
                    let $m_key = std::thread::spawn( move || {
                        stowage_clone.get_entity_interface::<$m_t, QuickMap>()
                    });
                )*
                $(
                    let stowage_clone = Arc::clone(&stowage);
                    let $loc_key = std::thread::spawn( move || {
                        get_locator::<$loc_t>(&stowage_clone)
                    });
                )*

                Self {
                    $($e_key: $e_key.join().expect("Thread panicked")),*,
                    $($f_key: $f_key.join().expect("Thread panicked")),*,
                    $($v_key: $v_key.join().expect("Thread panicked")),*,
                    $($m_key: $m_key.join().expect("Thread panicked")),*,
                    $($loc_key: $loc_key.join().expect("Thread panicked")),*,
                }
            }

            fn fake() -> Self {
                    Self {
                        $($f_key: Vec::new().into()),*,
                        $($e_key: VattArrPair::empty()),*,
                        $($v_key: VattArrPair::empty()),*,
                        $($loc_key: Locators::<$loc_t>::empty().into()),*,
                        $($m_key: HashMap::new().into()),*
                    }
            }
        }

        impl Getters {

            $(
                pub fn $f_key<'a, K: UnsignedNumber>(&'a self, key: &'a K) -> &'a ET<$f_t> {
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
    ($S:ident, $T:ident,
        $($f_key:ident => $f_mark:ty),*;
        $($r_key:ident -> $r_mark:ty),*;
        $($var_key:ident - $var_mark:ty = $var_t:ty),*;
        $($fix_key:ident - $fix_mark:ty | $fix_t:ty),*;
        $($float_key:ident : $float_mark:ty),*;
        $($oa_key:ident),*;
        $($p_trait:ident),*

    ) => {
        pub struct $S<T> where T: $T
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

        pub trait $T: Entity
            $( + StringAtt<$f_mark>)*
            $( + NumAtt<$r_mark>)*
            $( + VarAtt<$var_mark, VT=$var_t>)*
            $( + FixAtt<$fix_mark, FT=$fix_t>)*
            $( + FloatAtt<$float_mark>)*
        {}

        impl <T> $T for T where T: Entity
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
    author_prizes => AuthorNobels,
    raw_cites => AuthorRawCites,
    raw_works => AuthorRawWorkCounts;
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
    hit_names -> HitPapersNames,
    hit_dois -> HitPapersDois,
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
    top_journals - Top3JournalMarker | Top3Rec<Sources>,
    top_authors - Top15AuthorMarker | Top15Rec<Authors>,
    top_aff_countries - Top3AffCountryMarker | Top3Rec<Countries>,
    top_paper_topic - Top3PaperTopicMarker | Top3Rec<Topics>,
    top_citing_sfc - Top3CitingSfMarker | Top3Rec<Subfields>,
    top_paper_sfc - Top3PaperSfMarker | Top3Rec<Subfields>;;
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

pub trait MetaMapGetter: RootInterfaceable + Sized {
    fn get_meta(
        _id: usize,
        _gets: &Getters,
        _entif: &RootInterfaces<Self>,
    ) -> Option<HashMap<&'static str, String>> {
        None
    }
}

impl<E> NodeInterfaces<E>
where
    E: NodeInterfaceable,
{
    pub fn update_stats(self, stats: &mut AttributeLabelUnion, full_cc: f64) {
        update_stats::<E>(self.names, self.ccounts, Vec::new(), stats, full_cc)
    }
}

impl<E> RootInterfaces<E>
where
    E: NodeInterfaceable + RootInterfaceable,
{
    pub fn update_stats(self, stats: &mut AttributeLabelUnion, full_cc: f64) {
        update_stats::<E>(
            self.names,
            self.ccounts,
            self.sem_ids.0.to_vec(),
            stats,
            full_cc,
        )
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
        let na_orcid: ET<AuthorOrcids> = <ET<AuthorOrcids> as Default>::default();
        stowage
            .get_entity_interface::<AuthorOrcids, ReadFixIter>()
            .enumerate()
            .for_each(|(ai, orcid_id)| {
                if orcid_id != na_orcid {
                    orcid_map.insert(orcid_id, ai);
                }
            });
        let ifs = Interfaces::new(stowage.clone());
        println!("loaded full Getters");
        Self {
            ifs,
            stowage,
            inst_oa,
            work_oa,
            hit_papers,
            hit_wid_map,
            orcid_map,
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
        }
    }
}

fn get_locator<E>(stowage: &Stowage) -> Arc<Locators<E>>
where
    Locators<E>: BackendLoading<E>,
    E: NamespacedEntity,
    E: VariableSizeAttribute,
    ET<E>: VarSizedAttributeElement,
{
    let path = stowage.path_from_ns(E::NS);
    return <Locators<E> as BackendLoading<E>>::load_backend(&path).into();
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

impl MetaMapGetter for Sources {}
impl MetaMapGetter for Subfields {}
impl MetaMapGetter for Countries {}
impl MetaMapGetter for HitPapers {}

impl MetaMapGetter for Institutions {
    fn get_meta(
        id: usize,
        gets: &Getters,
        _: &RootInterfaces<Institutions>,
    ) -> Option<HashMap<&'static str, String>> {
        let loc = gets.iloc(&id);
        let kvs = vec![("lat", loc.0.to_string()), ("lon", loc.1.to_string())];
        Some(HashMap::from_iter(kvs.into_iter()))
    }
}
impl MetaMapGetter for Authors {
    fn get_meta(
        id: usize,
        gets: &Getters,
        entif: &RootInterfaces<Authors>,
    ) -> Option<HashMap<&'static str, String>> {
        let slug = String::from_utf8(gets.aslugs(id).to_vec()).unwrap();
        let any_hits = if (gets.author_citing_once(id).len() > 0)
            || (gets.author_citing_direct(id).len() > 0)
            || (entif.hit_works.0[id].len() > 0)
        {
            "1"
        } else {
            "0"
        };
        let kvs = vec![
            ("wikiSlug", slug),
            ("rawCites", gets.raw_cites(&id).to_string()),
            ("rawPapers", gets.raw_works(&id).to_string()),
            ("anyHits", any_hits.to_string()),
        ];
        Some(HashMap::from_iter(kvs.into_iter()))
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

fn reverse_id<E>(stowage: &Stowage) -> Box<[BigId]>
where
    E: MainEntity + NamespacedEntity,
{
    let interface = stowage.get_entity_interface::<E, QuickestNumbered>();
    let mut out = init_empty_slice::<E, BigId>();
    for (k, v) in interface.0 {
        out[v.to_usize()] = k;
    }
    out
}

fn update_stats<E>(
    names: VarBox<String>,
    ccounts: Box<[<E as NumAtt<CiteCountMarker>>::Num]>,
    semantic_ids: Vec<String>,
    stats: &mut AttributeLabelUnion,
    full_cc: f64,
) where
    E: NodeInterfaceable,
{
    const SPEC_RATE: f64 = 1.0 - SPEC_CORR_RATE;
    let numer_add = (full_cc / f64::from(E::N as u32)) * SPEC_CORR_RATE;
    let elevel = names
        .0
        .into_vec()
        .into_iter()
        .enumerate()
        .map(|(i, name)| {
            //TODO: u32 counts (max 4B) need to be ensured
            let numer = f64::from(ccounts[i].to_usize() as u32) * SPEC_RATE + numer_add;
            let spec_baseline = numer / full_cc;
            AttributeLabel {
                name,
                semantic_id: semantic_ids.get(i).unwrap_or(&"".to_string()).to_string(),
                spec_baseline,
            }
        })
        .collect();
    stats.insert(E::NAME.to_string(), elevel);
}
