use std::{
    cmp::Ordering,
    fmt::Debug,
    io,
    iter::Enumerate,
    mem::replace,
    ops::AddAssign,
    sync::Arc,
    thread::{self, JoinHandle},
};

use dmove::{
    reverse_prefixed_n, ByteFixArrayInterface, DowncastingBuilder, Entity, FixAttBuilder,
    MarkedAttribute, NamespacedEntity, UnsignedNumber, VarAttBuilder, VarAttIterator,
    VariableSizeAttribute, VattArrPair, ET, MAA,
};
use dmove_macro::ByteFixArrayInterface;
use hashbrown::{HashMap, HashSet};
use tqdm::{Iter, Tqdm};

use crate::{
    common::{
        init_empty_slice, BeS, CitSubfieldsArrayMarker, EmptyAttributeEntity, HitWorkMarker,
        InstRelMarker, MainWorkMarker, QuickAttPair, QuickMap, RefSubfieldsArrayMarker,
        Top15AuthorMarker, Top3AffCountryMarker, Top3CitingSfMarker, Top3JournalMarker,
        Top3PaperSfMarker, Top3PaperTopicMarker, WorkLoader, YearlyCitationsMarker,
        YearlyPapersMarker,
    },
    env_consts::{FINAL_YEAR, START_YEAR},
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics, Works},
        a2_init_atts::{
            AuthorshipFilteredAuthor, CountryCodes, CountryCodesThree,
            FilteredAuthorshipInstitutions, InstCountries, SourceYearQs, WorkAnyAuthorships,
            WorkSources, WorkTopics, WorkYears,
        },
        derive_links1::{WorkFilteredAuthors, WorkInstitutions, WorkSubfields, WorksCiting},
        derive_links2::{WorkCountries, WorkTopSource},
        derive_links3::HitPapers,
    },
    make_interface_struct,
    oa_structs::{
        post::{Institution, Source},
        FieldLike, NamedEntity,
    },
    semantic_ids::SemCsvObj,
    steps::{
        a1_entity_mapping::{Qs, YearInterface, Years},
        derive_links1::{collapse_links, invert_read_multi_link_to_work},
    },
    CiteCountMarker, QuickestBox, QuickestNumbered, ReadFixIter, ReadIter, Stowage,
    WorkCountMarker,
};
pub const N_RELS: usize = 8;
pub const ERA_SIZE: usize = 11;
pub const MAX_YEAR: usize = (FINAL_YEAR - START_YEAR) as usize;
pub const MIN_YEAR: usize = MAX_YEAR - ERA_SIZE + 1;

pub type EraRec = [u32; ERA_SIZE];
pub type TopNRec<E, const N: usize> = [(u32, ET<E>); N];
pub type Top3Rec<E> = TopNRec<E, 3>;
pub type Top15Rec<E> = TopNRec<E, 25>;

type YT = ET<Years>;
type IT = ET<Institutions>;
type Top3RelExtender<E, SE> = TopNRelExtender<3, E, SE, HashMap<ET<E>, u32>>;
type Top15HRelExtender<E, SE> = TopNRelExtender<25, E, SE, HashMap<ET<E>, f64>>;

#[derive(Debug, ByteFixArrayInterface)]
pub struct InstRelation {
    pub start: YT,
    pub end: YT,
    pub inst: IT,
    pub papers: u16,
    pub citations: u32,
}

struct ExtensionContainer<E>
where
    E: MarkedAttribute<WorkCountMarker>,
{
    paper_subfields: SelfExtender<SfDistRec<E>>,
    citing_subfields: SelfExtender<SfDistRec<E>>,
    papers_by_years: SelfExtender<EraRec>,
    citing_by_years: SelfExtender<EraRec>,
    top3_paper_sfs: Top3RelExtender<Subfields, E>,
    top3_paper_topics: Top3RelExtender<Topics, E>,
    top3_citing_sfs: Top3RelExtender<Subfields, E>,
    top3_aff_countries: Top3RelExtender<Countries, E>,
    top3_journals: Top3RelExtender<Sources, E>,
    top5_authors: Top15HRelExtender<Authors, E>,
    rels: Vec<[InstRelation; N_RELS]>,
    rel_map_rec: HashMap<ET<Institutions>, InstRelation>,
}

struct SfDistRec<E: MarkedAttribute<WorkCountMarker>>([ET<MAA<E, WorkCountMarker>>; Subfields::N]);

struct CiteDeriver {
    pub stowage: Stowage,
    backends: CDBackends,
    journal_vals: Arc<[u32]>,
}

struct CdManager {
    cd: Arc<CiteDeriver>,
    threads: Vec<JoinHandle<()>>,
}

struct SelfExtender<T> {
    vec: Vec<T>,
    rec: T,
}

struct TopNRelExtender<const N: usize, E, SE, Prep>
where
    SE: Entity,
    E: Entity,
    ET<E>: UnsignedNumber,
    Prep: TopPrepper<E>,
{
    vec: Vec<TopNRec<E, N>>,
    prep: Prep,
    seid: SE::T,
}

enum TopSorter {
    Default,
    TopJournal(Arc<[u32]>),
}

make_interface_struct!(CDBackends,
    wciting > Works;
    year => WorkYears,
    icountry => InstCountries,
    wtopsource => WorkTopSource,
    ship_fa => AuthorshipFilteredAuthor;
    wsubfields -> WorkSubfields,
    wtopics -> WorkTopics,
    wcountries -> WorkCountries,
    wsources -> WorkSources,
    winsts -> WorkInstitutions,
    w_aships -> WorkAnyAuthorships,
    fship_insts -> FilteredAuthorshipInstitutions;
);

trait IRelAdder: Entity {
    fn get_by_work(wu: usize, bends: &CDBackends, _id: ET<Self>) -> Vec<IT> {
        bends.winsts.get(&wu).unwrap().to_vec()
    }
}

trait TopPrepper<E> {
    type K;
    fn add(&mut self, k: Self::K);
    fn to_v(self) -> Vec<(usize, u32)>;
}

impl<E> Default for SfDistRec<E>
where
    E: MarkedAttribute<WorkCountMarker>,
    ET<MAA<E, WorkCountMarker>>: Default,
{
    fn default() -> Self {
        let arr = [(); Subfields::N].map(|_| ET::<MAA<E, WorkCountMarker>>::default());
        Self(arr)
    }
}

impl Stowage {
    fn write_all_sem_ids(&self) {
        self.write_semantic_id::<Authors>();
        self.write_semantic_id::<Institutions>();
        self.write_semantic_id::<Sources>();
        self.write_semantic_id::<Subfields>();
        let citer = self
            .get_entity_interface::<CountryCodesThree, ReadFixIter>()
            .zip(self.get_entity_interface::<CountryCodes, ReadFixIter>())
            .map(|(e3, e2)| {
                if e3 != [0; 3] {
                    String::from_utf8(e3.into()).unwrap().to_lowercase()
                } else {
                    String::from_utf8(e2.into()).unwrap().to_lowercase()
                }
            });
        self.decsem::<Countries, _>(citer);
    }

    fn ditf<Marker, E, T>(&self, v: Vec<T>, suff: &str)
    where
        E: Entity,
        T: ByteFixArrayInterface,
    {
        self.declare_iter::<FixAttBuilder, _, _, E, Marker>(
            v.into_iter(),
            &format!("{}-{suff}", E::NAME),
        );
    }
}

impl InstRelation {
    fn new(inst: ET<Institutions>) -> Self {
        Self {
            start: ET::<Years>::MAX,
            end: ET::<Years>::MIN,
            inst,
            papers: 0,
            citations: 0,
        }
    }

    fn update(&mut self, ccount: u32, year: ET<Years>) {
        self.papers += 1;
        self.citations += ccount;
        if year > self.end {
            self.end = year.clone()
        }
        if year < self.start {
            self.start = year
        }
    }
}

impl<T> SelfExtender<T>
where
    T: Default,
{
    fn new() -> Self {
        Self {
            vec: Vec::new(),
            rec: T::default(),
        }
    }

    fn push(&mut self) {
        self.vec
            .push(std::mem::replace(&mut self.rec, T::default()));
    }
}

impl<const N: usize, E, SE, Prep> TopNRelExtender<N, E, SE, Prep>
where
    E: Entity,
    SE: Entity,
    ET<E>: UnsignedNumber,
    ET<SE>: UnsignedNumber,
    Prep: TopPrepper<E> + Default,
{
    fn new() -> Self {
        Self {
            vec: Vec::new(),
            prep: Prep::default(),
            seid: SE::T::default(),
        }
    }

    fn add(&mut self, e: Prep::K) {
        self.prep.add(e)
    }

    fn push(&mut self, seid: SE::T, sort_o: TopSorter) {
        let cv = replace(&mut self.prep, Prep::default()).to_v();
        self.push_from_it(cv.into_iter(), seid, sort_o)
    }

    fn push_from_arr<'a, T>(&mut self, arr: &[T], seid: SE::T)
    where
        T: UnsignedNumber + 'a,
        SE: Entity,
    {
        self.push_from_it(
            arr.iter().map(|e| e.to_usize() as u32).enumerate(),
            seid,
            TopSorter::Default,
        );
    }

    fn push_from_it<I>(&mut self, it: I, seid: SE::T, sort_o: TopSorter)
    where
        I: Iterator<Item = (usize, u32)>,
        SE: Entity,
    {
        self.seid = seid;
        let mut v: Vec<(usize, u32)> = it.filter(|e| self.filter(e)).collect();
        v.sort_by(|l, r| sort_o.cmp(l, r));
        push_cut::<N, _>(
            v.into_iter()
                .map(|t| (t.1.to_usize() as u32, E::T::from_usize(t.0)))
                .collect(),
            &mut self.vec,
        );
    }

    fn filter<T>(&self, e: &(usize, T)) -> bool {
        if e.0 == 0 {
            return false;
        }
        if (SE::NAME == E::NAME) & (e.0 == self.seid.to_usize()) {
            return false;
        }
        true
    }
}

impl<E> ExtensionContainer<E>
where
    E: MarkedAttribute<WorkCountMarker>,
    ET<E>: UnsignedNumber,
    ET<MAA<E, WorkCountMarker>>: UnsignedNumber,
{
    fn new() -> Self {
        Self {
            paper_subfields: SelfExtender::new(),
            citing_subfields: SelfExtender::new(),
            papers_by_years: SelfExtender::new(),
            citing_by_years: SelfExtender::new(),
            top3_paper_sfs: Top3RelExtender::new(),
            top3_paper_topics: Top3RelExtender::new(),
            top3_citing_sfs: Top3RelExtender::new(),
            top3_aff_countries: Top3RelExtender::new(),
            top3_journals: Top3RelExtender::new(),
            top5_authors: Top15HRelExtender::new(),
            rels: Vec::new(),
            rel_map_rec: HashMap::new(),
        }
    }

    fn extend_get_ccount(
        &mut self,
        id: ET<E>,
        wid: &ET<Works>,
        bends: &CDBackends,
        year: YT,
    ) -> usize
    where
        E: IRelAdder,
    {
        inc_year(&mut self.papers_by_years.rec, year);
        let wu = wid.to_usize();
        for sf_id in bends.wsubfields.get(&wu).unwrap() {
            self.paper_subfields.rec.0[*sf_id as usize].inc();
        }
        for topic_id in bends.wtopics.get(&wu).unwrap() {
            self.top3_paper_topics.add(*topic_id);
        }
        for cid in bends.wcountries.get(&wu).unwrap() {
            self.top3_aff_countries.add(*cid);
        }
        self.top3_journals.add(*bends.wtopsource.get(wu).unwrap());
        let wcs = bends.wciting.get(&wu).unwrap();
        let wlen = wcs.len();
        let coauthships = bends.w_aships.get(&wu).unwrap();
        let ccn = coauthships.len() as f64;
        for any_ship_id in coauthships {
            let (is_filtered, ship_id) = reverse_prefixed_n(any_ship_id.to_usize());
            if is_filtered {
                self.top5_authors
                    .add((bends.ship_fa[ship_id], wlen as f64 / ccn));
            }
        }
        for c_wid in wcs {
            for sf_id in bends.wsubfields.get(&c_wid.to_usize()).unwrap() {
                self.citing_subfields.rec.0[*sf_id as usize].inc();
            }
            inc_year(&mut self.citing_by_years.rec, bends.year[c_wid.to_usize()]);
        }
        let o = E::get_by_work(wu, &bends, id);
        for iid in o.into_iter() {
            self.rel_map_rec
                .entry(iid)
                .or_insert_with(|| InstRelation::new(iid))
                .update(wlen as u32, year);
        }
        wcs.len()
    }

    fn push(&mut self, parent_id: E::T, cd: &CiteDeriver) {
        let map_base = replace(&mut self.rel_map_rec, HashMap::new());
        let mut rel_vec: Vec<InstRelation> = map_base.into_values().collect();
        rel_vec.sort_by(|l, r| (r.papers, (r.end - r.start)).cmp(&(l.papers, l.end - l.start)));
        push_cut::<N_RELS, InstRelation>(rel_vec, &mut self.rels);
        self.top3_paper_sfs
            .push_from_arr(&self.paper_subfields.rec.0, parent_id);
        self.top3_citing_sfs
            .push_from_arr(&self.citing_subfields.rec.0, parent_id);
        self.top3_paper_topics.push(parent_id, TopSorter::Default);
        self.top5_authors.push(parent_id, TopSorter::Default);
        self.top3_aff_countries.push(parent_id, TopSorter::Default);
        self.top3_journals
            .push(parent_id, TopSorter::TopJournal(cd.journal_vals.clone()));
        self.paper_subfields.push();
        self.citing_subfields.push();
        self.papers_by_years.push();
        self.citing_by_years.push();
    }

    fn add_iters(self, stowage: &Stowage) {
        let cisu_vec = self.citing_subfields.vec.into_iter().map(|e| e.0).collect();
        let pasu_vec = self.paper_subfields.vec.into_iter().map(|e| e.0).collect();

        stowage.ditf::<CitSubfieldsArrayMarker, E, _>(cisu_vec, "cit-subfields");
        stowage.ditf::<RefSubfieldsArrayMarker, E, _>(pasu_vec, "ref-subfields");
        stowage.ditf::<YearlyPapersMarker, E, _>(self.papers_by_years.vec, "papers-yearly");
        stowage.ditf::<YearlyCitationsMarker, E, _>(self.citing_by_years.vec, "citations-yearly");
        stowage.ditf::<Top3PaperSfMarker, E, _>(self.top3_paper_sfs.vec, "top-paper-subfields");
        stowage.ditf::<Top3CitingSfMarker, E, _>(self.top3_citing_sfs.vec, "top-citing-subfields");
        stowage.ditf::<Top3PaperTopicMarker, E, _>(self.top3_paper_topics.vec, "top-paper-topics");
        stowage.ditf::<Top15AuthorMarker, E, _>(self.top5_authors.vec, "top-paper-authors");
        stowage.ditf::<Top3JournalMarker, E, _>(self.top3_journals.vec, "top-journals");
        stowage
            .ditf::<Top3AffCountryMarker, E, _>(self.top3_aff_countries.vec, "top-aff-countries");
        stowage.ditf::<InstRelMarker, E, _>(self.rels, "rel-insts");
    }
}

impl CiteDeriver {
    fn new(stowage: Stowage) -> Self {
        let astow = Arc::new(stowage);
        let backends = CDBackends::new(astow.clone());

        let journal_vals = source_stats
            .iter()
            .map(|hm| (5 - hm.1) as u32 * hm.0[0] * 2 + hm.0[1] * 3)
            .collect();
        Self {
            backends,
            stowage: Arc::into_inner(astow).unwrap(),
            journal_vals,
        }
    }

    fn witer<E>(&self) -> Tqdm<Enumerate<VarAttIterator<MAA<E, MainWorkMarker>>>>
    where
        E: MarkedAttribute<MainWorkMarker> + IRelAdder,
        MAA<E, MainWorkMarker>:
            Entity<T = Box<[ET<Works>]>> + NamespacedEntity + VariableSizeAttribute,
    {
        self.stowage
            .get_entity_interface::<MAA<E, MainWorkMarker>, ReadIter>()
            .enumerate()
            .tqdm()
            .desc(Some(E::NAME))
    }

    fn cite_count<E>(&self)
    where
        E: MarkedAttribute<MainWorkMarker> + MarkedAttribute<WorkCountMarker> + IRelAdder,
        E::T: UnsignedNumber,
        MAA<E, MainWorkMarker>:
            Entity<T = Box<[ET<Works>]>> + NamespacedEntity + VariableSizeAttribute,
        ET<MAA<E, WorkCountMarker>>: UnsignedNumber,
    {
        let mut ext = ExtensionContainer::<E>::new();

        let iter = self.witer::<E>().map(|(i, ws)| {
            let eid = ET::<E>::from_usize(i);
            let sum = ws
                .iter()
                .map(|wid| {
                    let year = self.backends.year[wid.to_usize()];
                    ext.extend_get_ccount(eid, wid, &self.backends, year)
                })
                .sum();
            ext.push(eid, self);
            sum
        });

        add_iter_cc::<E, _>(&self.stowage, iter);
        ext.add_iters(&self.stowage);
    }

    fn author_paths(&self) {
        let mut ext = ExtensionContainer::<Authors>::new();
        let mut source_paths = HashMap::<[ET<Sources>; 2], u32>::new();
        let mut sf_paths = HashMap::<[ET<Subfields>; 2], u32>::new();

        let iter = self.witer::<Authors>().map(|(i, ws)| {
            let eid = ET::<Authors>::from_usize(i);
            let mut path_base = HashSet::<ET<Sources>>::new();
            let mut sf_path_base = HashSet::<ET<Subfields>>::new();
            let sum = ws
                .iter()
                .map(|wid| {
                    let wu = wid.to_usize();
                    let year = self.backends.year[wid.to_usize()];
                    self.backends
                        .wsources
                        .get(&wu)
                        .unwrap()
                        .iter()
                        .for_each(|e| {
                            path_base.insert(*e);
                        });

                    self.backends
                        .wsubfields
                        .get(&wu)
                        .unwrap()
                        .iter()
                        .for_each(|e| {
                            sf_path_base.insert(*e);
                        });

                    ext.extend_get_ccount(eid, wid, &self.backends, year)
                })
                .sum();
            ext.push(eid, self);
            add_paths(path_base, &mut source_paths);
            add_paths(sf_path_base, &mut sf_paths);
            sum
        });

        add_iter_cc::<Authors, _>(&self.stowage, iter);
        ext.add_iters(&self.stowage);
        self.stowage.add_iter_owned::<FixAttBuilder, _, _>(
            source_paths.into_iter(),
            Some("source-pairs-by-path"),
        );
        self.stowage.add_iter_owned::<FixAttBuilder, _, _>(
            sf_paths.into_iter(),
            Some("subfield-pairs-by-path"),
        )
    }

    fn q_ccs(&self) {
        let mut q_maps = init_empty_slice::<Qs, HashMap<ET<Works>, usize>>();
        let qy_map = self
            .stowage
            .get_entity_interface::<SourceYearQs, QuickMap>();
        let mut source_stats = init_empty_slice::<Sources, ([u32; 2], u8)>();

        let mut source_ext = ExtensionContainer::<Sources>::new();
        let iter = self.witer::<Sources>().map(|(i, ws)| {
            let sid = ET::<Sources>::from_usize(i);
            let mut best_q = 5;
            let mut counts: Vec<usize> = ws
                .iter()
                .map(|e| {
                    let wind = *e as usize;
                    let year = self.backends.year[wind];
                    let q = *qy_map.get(&(sid, year)).unwrap_or(&0);
                    if (q != 0) & (q < best_q) {
                        best_q = q;
                    }
                    let ccount = source_ext.extend_get_ccount(sid, e, &self.backends, year);
                    q_maps[q as usize].insert(*e, ccount);
                    ccount
                })
                .collect();
            source_ext.push(sid, self);
            let h = get_h_index_and_sort(&mut counts);
            let median = *counts.get(counts.len() / 2).unwrap_or(&0) as u32;
            source_stats[i] = ([h, median], best_q);
            counts.into_iter().sum()
        });

        add_iter_cc::<Sources, _>(&self.stowage, iter);

        source_ext.add_iters(&self.stowage);

        self.stowage.add_iter_owned::<FixAttBuilder, _, _>(
            source_stats.into_vec().into_iter(),
            Some("source-stats"),
        );

        self.stowage
            .declare_iter::<DowncastingBuilder, _, _, Qs, CiteCountMarker>(
                q_maps.iter().map(|e| e.values().sum()),
                &format!("qs-cite-count"),
            )
    }
}

impl CdManager {
    //TODO: this could be replaced with the parallel macro
    fn new(cd: CiteDeriver) -> Self {
        Self {
            cd: Arc::new(cd),
            threads: Vec::new(),
        }
    }

    fn send<F>(&mut self, f: F)
    where
        F: Fn(&CiteDeriver) + Send + 'static,
    {
        let ac = self.cd.clone();
        self.threads.push(thread::spawn(move || f(&ac)));
    }

    fn join(&mut self) {
        let ot = std::mem::replace(&mut self.threads, Vec::new());
        ot.into_iter().for_each(|t| {
            t.join().unwrap();
        });
    }
}

impl TopSorter {
    fn cmp<T>(&self, l: &(usize, T), r: &(usize, T)) -> Ordering
    where
        T: UnsignedNumber,
    {
        match self {
            Self::Default => r.1.cmp(&l.1),
            Self::TopJournal(b) => b[r.0].cmp(&b[l.0]),
        }
    }
}

impl<E> TopPrepper<E> for HashMap<E::T, u32>
where
    E: Entity,
    ET<E>: UnsignedNumber,
{
    type K = ET<E>;
    fn add(&mut self, k: Self::K) {
        self.entry(k).or_insert(0).inc();
    }

    fn to_v(self) -> Vec<(usize, u32)> {
        self.iter().map(|e| (e.0.to_usize(), *e.1)).collect()
    }
}

impl<E> TopPrepper<E> for HashMap<E::T, f64>
where
    E: Entity,
    ET<E>: UnsignedNumber,
{
    type K = (ET<E>, f64);
    fn add(&mut self, k: Self::K) {
        self.entry(k.0).or_insert(0.0).add_assign(k.1);
    }

    fn to_v(self) -> Vec<(usize, u32)> {
        self.into_iter()
            .map(|e| (e.0.to_usize(), e.1.round() as u32))
            .collect()
    }
}

impl Default for InstRelation {
    fn default() -> Self {
        Self::new(0)
    }
}

impl SemCsvObj for Authors {
    type CsvObj = NamedEntity;
}

impl SemCsvObj for Subfields {
    type CsvObj = FieldLike;
}

impl SemCsvObj for Sources {
    type CsvObj = Source;
}

impl SemCsvObj for Institutions {
    type CsvObj = Institution;
}

impl IRelAdder for Sources {}

impl IRelAdder for Subfields {}

impl IRelAdder for Topics {}

impl IRelAdder for Institutions {}

impl IRelAdder for Countries {
    fn get_by_work(wu: usize, bends: &CDBackends, id: ET<Self>) -> Vec<IT> {
        let mut o = Vec::new();
        for iid in bends.winsts.get(&wu).unwrap() {
            if *bends.icountry.get(iid.to_usize()).unwrap() == id {
                o.push(*iid);
            }
        }
        o
    }
}

impl IRelAdder for Authors {
    fn get_by_work(wu: usize, bends: &CDBackends, aid: ET<Self>) -> Vec<IT> {
        let mut o = Vec::new();
        for ship_any in bends.w_aships.get(&wu).unwrap() {
            let (is_filtered, ship_id) = reverse_prefixed_n(ship_any.to_usize());
            if is_filtered {
                if bends.ship_fa[ship_id] == aid {
                    for iid in bends.fship_insts.get(&ship_id).unwrap() {
                        o.push(*iid)
                    }
                }
            }
        }
        o
    }
}

pub fn main(mut stowage: Stowage) -> io::Result<()> {
    let cd = CiteDeriver::new(stowage);
    let mut cdm = CdManager::new(cd);
    cdm.send(CiteDeriver::author_paths);
    cdm.send(CiteDeriver::cite_count::<Sources>);
    cdm.send(CiteDeriver::cite_count::<Institutions>);
    cdm.send(CiteDeriver::cite_count::<Countries>);
    cdm.send(CiteDeriver::cite_count::<Subfields>);
    cdm.send(CiteDeriver::cite_count::<Topics>);
    cdm.send(|dm| dm.stowage.write_all_sem_ids());
    cdm.join();
    cdm.cd.stowage.write_code()?;
    let interface = stowage.get_entity_interface::<WorksCiting, ReadIter>();
    let wc_name = "work-citing-counts";
    stowage.add_iter_owned::<DowncastingBuilder, _, _>(interface.map(|e| e.len()), Some(&wc_name));
    stowage.declare::<Works, CiteCountMarker>(wc_name);

    let sqy = stowage.get_entity_interface::<SourceYearQs, QuickMap>();
    let w_sources = stowage.get_entity_interface::<WorkSources, ReadIter>();
    let w_years = stowage.get_entity_interface::<WorkYears, QuickestBox>();
    let iter = w_sources.enumerate().map(|(i, sources)| {
        let wy = w_years[i];
        let mut best_q = 6;
        let mut best_s = 0;
        let mut update = |mut q, sid| {
            if q == 0 {
                q = 5
            }
            if q < best_q {
                best_s = sid;
                best_q = q;
            }
        };
        for sid in sources {
            let q = *sqy.get(&(sid, wy)).unwrap_or(&5);
            update(q, sid);
        }
        best_s
    });
    stowage.add_iter_owned::<FixAttBuilder, _, _>(iter, Some("work-top-source"));

    invert_read_multi_link_to_work::<WorkFilteredAuthors>(&mut stowage, "author-works");
    invert_read_multi_link_to_work::<WorkSubfields>(&mut stowage, "subfield-works");
    invert_read_multi_link_to_work::<WorkInstitutions>(&mut stowage, "institution-works");
    collapse_links::<WorkInstitutions, InstCountries>(&mut stowage, "work-countries");
    stowage.write_code()?;
    Ok(())
}

fn get_h_index_and_sort<T>(counts: &mut Vec<T>) -> u32
where
    T: UnsignedNumber,
{
    counts.sort();
    for (i, cc) in counts.iter().rev().enumerate() {
        if i > cc.to_usize() {
            return i as u32;
        }
    }
    counts.len() as u32
}

fn add_iter_cc<E, I>(stowage: &Stowage, it: I)
where
    E: Entity,
    I: Iterator<Item = usize>,
{
    stowage.declare_iter::<DowncastingBuilder, _, _, E, CiteCountMarker>(
        it,
        &format!("{}-cite-count", E::NAME),
    );
}

fn inc_year(era_rec: &mut EraRec, year: YT) {
    let yi = year.to_usize();
    if (yi >= MIN_YEAR) & (yi <= MAX_YEAR) {
        era_rec[yi - MIN_YEAR] += 1
    }
}

fn push_cut<const C: usize, T>(mut v: Vec<T>, outer: &mut Vec<[T; C]>)
where
    T: Default + Debug,
{
    for _ in v.len()..(C + 1) {
        v.push(T::default());
    }
    v.truncate(C);
    outer.push(v.try_into().unwrap());
}

fn add_paths<T>(path_base: HashSet<T>, paths_map: &mut HashMap<[T; 2], u32>)
where
    T: Eq + Hash + Ord + Copy,
{
    for s1 in path_base.iter() {
        for s2 in path_base.iter() {
            if s1 < s2 {
                let k = [*s1, *s2];
                paths_map.entry(k).or_insert(0).add_assign(1);
            }
        }
    }
}
