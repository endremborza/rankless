use crate::{
    biblo_var_att::BiblioInfo,
    common::{
        field_id_parse, init_empty_slice, oa_id_parse, oa_id_parse_opt, short_string_to_u64, BeS,
        DoiMarker, MainEntity, NameExtensionMarker, NameMarker, NumberedEntity, ParsedId,
        QuickestNumbered, Stowage, MAIN_NAME, NET,
    },
    csv_writers::{institutions, works},
    data_consts::CC_MAP,
    env_consts::START_YEAR,
    gen::a1_entity_mapping::{
        AreaFields, Authors, Cities, Countries, DiscardedAuthors, Domains, Fields, Institutions,
        Sources, Subfields, Topics, Works,
    },
    oa_structs::{
        post::{
            read_post_str_arr, Author, Authorship, Field, IdSet, Institution, Location, Source,
            SubField, Topic,
        },
        Biblio, FieldLike, Geo, Named, NamedEntity, ReferencedWork, Work, WorkTopic,
    },
    steps::a1_entity_mapping::{iter_authorships, Qs, RawYear, SourceArea, YearInterface, Years},
};
use dmove::{
    para::Worker, BigId, DiscoMapEntityBuilder, DowncastingBuilder, DowncastingPrefixedVarBuilder,
    Entity, EntityImmutableMapperBackend, FixAttBuilder, LoadedIdMap, MappableEntity,
    MetaIntegrator, NamespacedEntity, UnsignedNumber, VarAttBuilder, ET,
};
use levenshtein::levenshtein;
use serde::{de::DeserializeOwned, Deserialize};
use std::{
    cmp::min,
    io,
    marker::PhantomData,
    sync::{Arc, Mutex},
    usize,
};
use tqdm::Iter;

pub const DOI_PREFIX_LEN: usize = 16;
const ORCID_PREF: &str = "https://orcid.org/";
const MIN_TOPIC_SCORE: f64 = 0.7;
const MIN_RATE: f64 = 0.8;
const MIN_LEN: usize = 10;

#[derive(Deserialize)]
struct SourceQ {
    publication_year: u16,
    id: BigId,
    best_q: u8,
}

#[derive(Deserialize)]
struct WikiId {
    slug: String,
    oa_id: BigId,
}

#[derive(Deserialize)]
struct NobelEntry {
    oa_id: BigId,
    category: u8,
    year: RawYear,
}

struct ShipRelWriter {
    fship2a: Vec<usize>,
    fship2is: Vec<Vec<ET<Institutions>>>,

    dship2a: Vec<usize>,
    dship2is: Vec<Vec<ET<Institutions>>>,

    w2combined_ships: Box<[Vec<(bool, usize)>]>,

    winf: Arc<LoadedIdMap<ET<Works>>>,
    fainf: LoadedIdMap<ET<Authors>>,
    dainf: LoadedIdMap<ET<DiscardedAuthors>>,
    iinf: LoadedIdMap<ET<Institutions>>,
}

struct WorkBiblioWriter {
    biblios: Mutex<Box<[BiblioInfo]>>,
    winf: Arc<LoadedIdMap<ET<Works>>>,
}

struct WorkAttWriter {
    wyears: Mutex<Box<[ET<Years>]>>,
    wnames: Mutex<Box<[String]>>,
    wdois: Mutex<Box<[String]>>,
    winf: Arc<LoadedIdMap<ET<Works>>>,
}

struct BoxRoller<T, E> {
    arr: std::vec::IntoIter<T>,
    phantom: PhantomData<fn() -> E>,
}

struct StrWriter<'a> {
    stowage: &'a Stowage,
    main: &'static str,
    sub: &'static str,
}

struct GenObjAttWorker<'a, Source, Target, StoredOfTarget, SourceIF, TargetIF>
where
    Source: MainEntity,
    Target: MappableEntity,
    StoredOfTarget: Sync + Send,
    TargetIF: EntityImmutableMapperBackend<Target>,
    SourceIF: EntityImmutableMapperBackend<Source>,
{
    data_worker: DataAttWorker<'a, Source, StoredOfTarget, SourceIF>,
    att_interface: &'a TargetIF,
    p: PhantomData<fn() -> Target>,
}

struct DataAttWorker<'a, Source, TargetType, SourceIF>
where
    Source: MainEntity,
    TargetType: Sync + Send,
    SourceIF: EntityImmutableMapperBackend<Source>,
{
    self_interface: &'a SourceIF,
    attribute_arr: Mutex<Box<[TargetType]>>,
    p: PhantomData<fn() -> Source>,
}

struct GenWorker<W, PreParseTargetType, PostParseTargetType, IngestableAttType, Source, AGMarker, I>
{
    worker: W,
    phantom_prep: PhantomData<fn() -> PreParseTargetType>,
    phantom_post: PhantomData<fn() -> PostParseTargetType>,
    phantom_ing: PhantomData<fn() -> IngestableAttType>,
    phantom_m: PhantomData<fn() -> AGMarker>,
    phantom_s: PhantomData<fn() -> Source>,
    phantom_i: PhantomData<fn() -> I>,
}

trait AttGetter<T, Marker> {
    fn get_att(&self) -> Option<T>;
}

trait ObjAttGetter<T: Entity + MappableEntity> {
    fn get_obj_att(&self) -> Option<T::KeyType>;
}

trait GotAttParser<RawAtt, ParsedAtt, IngestableAttType, Source, Marker, I>
where
    Source: MainEntity,
    I: Iterator<Item = IngestableAttType>,
{
    fn parse(&self, att: Option<RawAtt>) -> Option<ParsedAtt>;
    fn ingest(&self, res: ParsedAtt, ind: NET<Source>);
    fn map_ind(&self, ind: Source::KeyType) -> Option<NET<Source>>;
    fn ingest_result<F>(self, f: F)
    where
        F: Fn(I);
}

trait StorableMarker<T>
where
    Self: Sized,
{
    type FinalType;
    fn update(&mut self, other: T);
    fn finalize(self) -> Self::FinalType;
}

impl Stowage {
    fn add_source_qs<SIF, YIF>(&mut self, sources_interface: &SIF, years_interface: &YIF)
    where
        YIF: EntityImmutableMapperBackend<Years>,
        SIF: EntityImmutableMapperBackend<Sources>,
    {
        let source_q_kv_iter = self
            .read_csv_objs::<SourceQ>(Sources::NAME, Qs::NAME)
            .filter_map(|yq| {
                let source_oa_id = yq.get_parsed_id().unwrap();
                sources_interface.get_via_immut(&source_oa_id).map(|sid| {
                    let year = years_interface.get_via_immut(&yq.publication_year).unwrap();
                    ((sid, year), yq.best_q)
                })
            });

        self.add_iter_owned::<DiscoMapEntityBuilder<
            (<Sources as Entity>::T, <Years as Entity>::T),
            <Qs as Entity>::T,
        >, _, _>(source_q_kv_iter, Some("source-year-qs"));
    }

    fn add_inst_atts(
        &mut self,
    ) -> (
        BeS<QuickestNumbered, Institutions>,
        BeS<QuickestNumbered, Countries>,
    ) {
        let cif = self.get_entity_interface::<Cities, QuickestNumbered>();
        let iif: BeS<QuickestNumbered, Institutions> =
            self.get_entity_interface::<Institutions, QuickestNumbered>();
        let coif = self.get_entity_interface::<Countries, QuickestNumbered>();
        let mut cinames = init_empty_slice::<Cities, String>();
        let mut conames = init_empty_slice::<Countries, String>();
        let mut ccs = init_empty_slice::<Countries, [u8; 2]>();
        let mut cities = init_empty_slice::<Institutions, ET<Cities>>();
        let mut locs = init_empty_slice::<Institutions, (f64, f64)>();
        for cgeo in self.read_csv_objs::<Geo>(Institutions::NAME, institutions::atts::geo) {
            let rcid = short_string_to_u64(cgeo.city.as_deref().unwrap_or(""));
            let cid = cif.0.get(&rcid).unwrap();
            let rcoid = cgeo.get_parsed_id().unwrap();
            let coid = coif.0.get(&rcoid).unwrap();
            if *coid > 0 {
                ccs[coid.to_usize()] = rcoid.to_le_bytes()[..2].try_into().unwrap();
                cinames[cid.to_usize()] = cgeo.city.unwrap_or_default();
                conames[coid.to_usize()] = cgeo.country.unwrap_or_default();
            }
            if let Some(iid) = iif.0.get(&oa_id_parse(&cgeo.parent_id.unwrap())) {
                let iid_u = iid.to_usize();
                cities[iid_u] = *cid;
                if let (Some(lon), Some(lat)) = (cgeo.longitude, cgeo.latitude) {
                    locs[iid_u] = (lat, lon);
                }
            }
        }

        const ROR_PREFIX: &str = "https://ror.org/";
        let mut inames = init_empty_slice::<Institutions, String>();
        let mut rors = init_empty_slice::<Institutions, [u8; 9]>();
        for iobj in self.read_csv_objs::<Institution>(Institutions::NAME, MAIN_NAME) {
            if let Some(iid_o) = iobj.get_parsed_id() {
                if let Some(iid) = iif.0.get(&iid_o) {
                    let iid_u = iid.to_usize();
                    inames[iid_u] = iobj.display_name;
                    assign_farr(iobj.ror, ROR_PREFIX, &mut rors, iid_u);
                }
            }
        }
        let cc3s = ccs
            .iter()
            .map(|e| {
                for (k, v) in CC_MAP.iter() {
                    if k == e {
                        return *v;
                    }
                }
                [0; 3]
            })
            .collect::<Vec<[u8; 3]>>();
        add_name_box::<Countries>(self, conames);
        add_name_box::<Cities>(self, cinames);
        add_name_box::<Institutions>(self, inames);
        self.add_barr::<FixAttBuilder, _>(ccs, "country-codes");
        self.add_iter_owned::<FixAttBuilder, _, _>(cc3s.into_iter(), Some("country-codes-three"));
        self.add_barr::<FixAttBuilder, _>(locs, "inst-locs");
        self.add_barr::<FixAttBuilder, _>(rors, "inst-rors");
        self.add_barr::<FixAttBuilder, _>(cities, "inst-cities");

        (iif, coif)
    }

    fn add_author_atts(&mut self) {
        let aif = self.get_entity_interface::<Authors, QuickestNumbered>();
        self.add_nobels(&aif);
        let mut names = init_empty_slice::<Authors, String>();
        let mut wiki_slugs = init_empty_slice::<Authors, String>();
        let mut orcids = init_empty_slice::<Authors, [u8; 19]>();
        let mut raw_cites = init_empty_slice::<Authors, usize>();
        let mut raw_works = init_empty_slice::<Authors, usize>();
        let discarded_name_iter = self
            .read_csv_objs::<Author>(Authors::NAME, MAIN_NAME)
            .filter_map(|aobj| {
                if let Some(pid) = aobj.get_parsed_id() {
                    let aname = aobj.display_name.unwrap_or_default();
                    if let Some(aidt) = aif.0.get(&pid) {
                        let aid = aidt.to_usize();
                        names[aid] = aname;
                        assign_farr(aobj.orcid, ORCID_PREF, &mut orcids, aid);
                        raw_cites[aid] = aobj.cited_by_count.unwrap_or(0) as usize;
                        raw_works[aid] = aobj.works_count.unwrap_or(0) as usize;
                        None
                    } else {
                        Some(aname)
                    }
                } else {
                    None
                }
            });

        for wobj in self.read_csv_objs::<WikiId>(Authors::NAME, "wiki-slug") {
            if let Some(aidt) = aif.0.get(&wobj.oa_id) {
                wiki_slugs[aidt.to_usize()] = wobj.slug;
            }
        }
        let init_wu = vec!["Unknown".to_string()].into_iter();

        self.declare_iter::<VarAttBuilder, _, _, DiscardedAuthors, NameMarker>(
            init_wu.chain(discarded_name_iter),
            &get_name_name::<DiscardedAuthors>(),
        );
        add_name_box::<Authors>(self, names);
        self.add_barr::<VarAttBuilder, _>(wiki_slugs, "author-wiki-slugs");
        self.add_barr::<FixAttBuilder, _>(orcids, "author-orcids");
        self.add_barr::<DowncastingBuilder, _>(raw_cites, "author-raw-cites");
        self.add_barr::<DowncastingBuilder, _>(raw_works, "author-raw-work-counts");
    }

    fn add_theme_atts<E, F>(&mut self, ifs: &BeS<QuickestNumbered, E>, gatt: F)
    where
        E: NumberedEntity<T = ET<E>>,
        ET<E>: UnsignedNumber,
        F: Fn(&str) -> BigId,
    {
        const IDS: &str = "ids";
        const WPREF: &str = "https://en.wikipedia.org/wiki/";
        let mut wids = init_empty_slice::<E, String>();
        for ids in self.read_csv_objs::<IdSet>(E::NAME, IDS) {
            if let (Some(id), Some(wid)) = (
                ifs.0.get(&gatt(&ids.parent_id.clone().unwrap())),
                ids.wikipedia,
            ) {
                wids[id.to_usize()] = wid.replace(WPREF, "");
            }
        }
        self.add_barr::<VarAttBuilder, _>(wids, &format!("{}-wikipedia", E::NAME));
    }

    fn add_work_atts(&self, winf: Arc<LoadedIdMap<ET<Works>>>) -> LoadedIdMap<ET<Works>> {
        WorkAttWriter::new(winf.clone())
            .para(self.read_csv_objs(Works::NAME, MAIN_NAME))
            .post(self);
        Arc::into_inner(winf).unwrap()
    }

    fn add_ship_relations(&self) -> LoadedIdMap<ET<Works>> {
        let winf: Arc<LoadedIdMap<ET<Works>>> = self
            .get_entity_interface::<Works, QuickestNumbered>()
            .into();
        let mut ship_rel_writer = ShipRelWriter::new(winf.clone(), self);
        for ship in iter_authorships(self) {
            ship_rel_writer.proc_next(ship);
        }
        ship_rel_writer.post(self);
        {
            WorkBiblioWriter::new(winf.clone())
                .para(self.read_csv_objs(Works::NAME, "biblio"))
                .post(self);
        }
        Arc::into_inner(winf).unwrap()
    }

    fn property_writer<
        AttWorker,
        Builder,
        CsvObj,
        PreParseTargetType,
        PostParseTargetType,
        IngestableAtt,
        Source,
        AGMarker,
        I,
    >(
        &self,
        w: GenWorker<
            AttWorker,
            PreParseTargetType,
            PostParseTargetType,
            IngestableAtt,
            Source,
            AGMarker,
            I,
        >,
        name: &str,
        main: &str,
        sub: &str,
    ) where
        CsvObj: DeserializeOwned + Send + AttGetter<PreParseTargetType, AGMarker> + ParsedId,
        AttWorker: GotAttParser<
                PreParseTargetType,
                PostParseTargetType,
                IngestableAtt,
                Source,
                AGMarker,
                I,
            > + Sync,
        Source: MainEntity,
        PostParseTargetType: Sync,
        Builder: MetaIntegrator<IngestableAtt>,
        I: Iterator<Item = IngestableAtt>,
    {
        w.para(self.read_csv_objs::<CsvObj>(main, sub))
            .worker
            .ingest_result(|atts| {
                self.add_iter_owned::<Builder, _, IngestableAtt>(atts, Some(name));
            });
    }

    fn object_property<CsvObj, Source, Target, SIF, TIF>(
        &mut self,
        source_interface: &SIF,
        target_interface: &TIF,
        fatt_name: &str,
    ) -> io::Result<usize>
    where
        CsvObj: ObjAttGetter<Target> + ParsedId + DeserializeOwned + Send,
        Source: MainEntity,
        Target: Entity + MappableEntity,
        ET<Target>: UnsignedNumber,
        SIF: EntityImmutableMapperBackend<Source> + Sync,
        TIF: EntityImmutableMapperBackend<Target> + Sync,
    {
        let obj_worker = GenObjAttWorker::<'_, Source, Target, ET<Target>, SIF, TIF>::new(
            source_interface,
            target_interface,
        );
        let winit = GenWorker::new(obj_worker);
        self.property_writer::<_, FixAttBuilder, CsvObj, _, _, _, _, _, _>(
            winit,
            fatt_name,
            Source::NAME,
            MAIN_NAME,
        );
        self.declare_link::<Source, Target>(fatt_name);
        Ok(0)
    }

    fn multi_object_property<CsvObj, Source, Target, SIF, TIF>(
        &mut self,
        source_interface: &SIF,
        target_interface: &TIF,
        fatt_name: &str,
        sub: &str,
    ) -> io::Result<usize>
    where
        CsvObj: ObjAttGetter<Target> + ParsedId + DeserializeOwned + Send,
        Source: MainEntity,
        Target: MainEntity,
        SIF: EntityImmutableMapperBackend<Source> + Sync,
        TIF: EntityImmutableMapperBackend<Target> + Sync,
    {
        let obj_worker = GenObjAttWorker::<'_, Source, Target, Vec<NET<Target>>, SIF, TIF>::new(
            source_interface,
            target_interface,
        );
        let winit = GenWorker::new(obj_worker);
        self.property_writer::<_, VarAttBuilder, CsvObj, _, _, _, _, _, _>(
            winit,
            fatt_name,
            Source::NAME,
            sub,
        );
        self.declare_link::<Source, Target>(fatt_name);
        Ok(0)
    }

    fn add_empty_name_ext<T: Entity>(&mut self) {
        let name = get_name_ext_name::<T>();
        self.add_empty_something::<T, NameExtensionMarker>(&name);
    }

    fn add_empty_something<E: Entity, Marker>(&mut self, name: &str) {
        //TODO: this takes memory (and some space) for no fucking reason
        let iter = (0..E::N).map(|_| "".to_string());
        self.declare_iter::<VarAttBuilder, _, _, E, Marker>(iter, name)
    }

    fn add_nobels(&self, aif: &LoadedIdMap<ET<Authors>>) {
        let mut author_nobels = init_empty_slice::<Authors, (u8, ET<Years>)>();
        for ne in self.read_csv_objs::<NobelEntry>(Authors::NAME, "nobel") {
            if let Some(aidt) = aif.0.get(&ne.oa_id) {
                if ne.year > START_YEAR as RawYear {
                    author_nobels[aidt.to_usize()] = (ne.category, YearInterface::parse(ne.year));
                }
            }
        }
        self.add_barr::<FixAttBuilder, _>(author_nobels, "author-nobels");
    }
}

impl WorkAttWriter {
    fn new(winf: Arc<LoadedIdMap<ET<Works>>>) -> Self {
        Self {
            wdois: init_empty_slice::<Works, _>().into(),
            wyears: init_empty_slice::<Works, _>().into(),
            wnames: init_empty_slice::<Works, _>().into(),
            winf,
        }
    }

    fn post(self, stowage: &Stowage) {
        let wyname = "work-years";
        stowage.add_iter_owned::<FixAttBuilder, _, _>(iter_mboxa(self.wyears), Some(wyname));
        stowage.declare_link::<Works, Years>(wyname);
        stowage.declare_iter::<VarAttBuilder, _, _, Works, NameMarker>(
            iter_mboxa(self.wnames),
            &get_name_name::<Works>(),
        );
        stowage.declare_iter::<VarAttBuilder, _, _, Works, DoiMarker>(
            iter_mboxa(self.wdois),
            "work-dois",
        );
    }
}

impl ShipRelWriter {
    fn new(winf: Arc<LoadedIdMap<ET<Works>>>, stowage: &Stowage) -> Self {
        Self {
            fship2a: vec![0],
            fship2is: vec![Vec::new()],
            dship2a: vec![0],
            dship2is: vec![Vec::new()],
            w2combined_ships: init_empty_slice::<Works, _>(),
            winf,
            fainf: stowage.get_entity_interface::<Authors, QuickestNumbered>(),
            dainf: stowage.get_entity_interface::<DiscardedAuthors, QuickestNumbered>(),
            iinf: stowage.get_entity_interface::<Institutions, QuickestNumbered>(),
        }
    }

    fn proc_next(&mut self, ship: Authorship) {
        let w_ind = match get_wind(&ship, &self.winf) {
            Some(wpi) => wpi,
            None => return,
        };

        let ivec: Vec<ET<Institutions>> = ship
            .institutions
            .unwrap_or_default()
            .trim()
            .split(";")
            .filter(|e| e.len() > 1)
            .filter_map(|e| oa_id_parse_opt(e))
            .filter_map(|e| self.iinf.0.get(&e))
            .map(|e| *e)
            .collect();

        let (is_filtered, aid) = ship
            .author_id
            .as_deref()
            .and_then(oa_id_parse_opt)
            .and_then(|oa_aid| {
                if let Some(faid) = self.fainf.0.get(&oa_aid) {
                    Some((true, faid.to_usize()))
                } else {
                    self.dainf.0.get(&oa_aid).map(|d| (false, d.to_usize()))
                }
            })
            .unwrap_or((false, 0));

        let (ship2a, ship2is) = if is_filtered {
            (&mut self.fship2a, &mut self.fship2is)
        } else {
            (&mut self.dship2a, &mut self.dship2is)
        };
        let ship_ind = ship2a.len();
        ship2a.push(aid);
        ship2is.push(ivec);
        self.w2combined_ships[w_ind].push((is_filtered, ship_ind));
    }

    fn post(self, stowage: &Stowage) {
        let faa_name = "authorship-filtered-author";
        let daa_name = "authorship-discarded-author";
        let fai_name = "filtered-authorship-institutions";

        stowage.add_iter_owned::<FixAttBuilder, _, _>(
            self.fship2a
                .into_iter()
                .map(|e| <ET<Authors> as UnsignedNumber>::from_usize(e)),
            Some(faa_name),
        );
        stowage.add_iter_owned::<FixAttBuilder, _, _>(
            self.dship2a
                .into_iter()
                .map(|e| <ET<DiscardedAuthors> as UnsignedNumber>::from_usize(e)),
            Some(daa_name),
        );

        stowage.add_iter_owned::<VarAttBuilder, _, _>(
            self.fship2is.into_iter().map(|v| v.into_boxed_slice()),
            Some(fai_name),
        );
        stowage.add_iter_owned::<VarAttBuilder, _, _>(
            self.dship2is.into_iter().map(|v| v.into_boxed_slice()),
            Some("discarded-authorship-institutions"),
        );
        stowage.add_iter_owned::<DowncastingPrefixedVarBuilder, _, _>(
            self.w2combined_ships
                .into_vec()
                .into_iter()
                .map(|v| v.into_boxed_slice()),
            Some("work-any-authorships"),
        );
    }
}

impl WorkBiblioWriter {
    fn new(winf: Arc<LoadedIdMap<ET<Works>>>) -> Self {
        Self {
            biblios: init_empty_slice::<Works, _>().into(),
            winf,
        }
    }

    fn post(self, stowage: &Stowage) {
        stowage.add_iter_owned::<VarAttBuilder, _, _>(
            iter_mboxa(self.biblios).tqdm(),
            Some("work-biblios"),
        );
    }
}

impl Worker<Work> for WorkAttWriter {
    fn proc(&self, input: Work) {
        let w_ind = match get_wind(&input, &self.winf) {
            Some(wpi) => wpi,
            None => return,
        };

        if let Some(doi) = input.get_att() {
            self.wdois.lock().unwrap()[w_ind] = doi;
        }

        if let Some(name) = input.display_name {
            self.wnames.lock().unwrap()[w_ind] = name;
        }

        if let Some(year) = input.publication_year {
            self.wyears.lock().unwrap()[w_ind] = YearInterface::parse(year);
        }
    }
}

impl Worker<Biblio> for WorkBiblioWriter {
    fn proc(&self, bib: Biblio) {
        let w_ind = match get_wind(&bib, &self.winf) {
            Some(wpi) => wpi,
            None => return,
        };
        let new_bib: BiblioInfo = bib.into();
        if new_bib != BiblioInfo::default() {
            self.biblios.lock().unwrap()[w_ind] = new_bib;
        }
    }
}

impl<'a> StrWriter<'a> {
    fn new(stowage: &'a Stowage) -> Self {
        Self {
            stowage,
            main: "",
            sub: "",
        }
    }

    fn set_path(&mut self, main: &'static str, sub: &'static str) -> &mut Self {
        self.main = main;
        self.sub = sub;
        self
    }

    fn write_name<CsvObj, Source>(&mut self) -> BeS<QuickestNumbered, Source>
    where
        CsvObj: DeserializeOwned + ParsedId + AttGetter<String, NameMarker> + Send,
        Source: MainEntity + NamespacedEntity,
    {
        let interface = self
            .stowage
            .get_entity_interface::<Source, QuickestNumbered>();
        let prop_name = &get_name_name::<Source>();
        self.write_meta::<Source, CsvObj, NameMarker>(&interface, prop_name);
        interface
    }

    fn write_name_ext<CsvObj, E>(&mut self, interface: &BeS<QuickestNumbered, E>)
    where
        CsvObj: DeserializeOwned + ParsedId + AttGetter<String, NameExtensionMarker> + Send,
        E: MainEntity + NamespacedEntity,
    {
        let prop_name = &get_name_ext_name::<E>();
        self.write_meta::<E, CsvObj, NameExtensionMarker>(interface, prop_name);
    }

    fn write_meta<E, CsvObj, Marker>(
        &mut self,
        interface: &BeS<QuickestNumbered, E>,
        prop_name: &str,
    ) where
        CsvObj: DeserializeOwned + ParsedId + AttGetter<String, Marker> + Send,
        E: MainEntity + NamespacedEntity,
    {
        if self.main.is_empty() {
            self.set_path(E::NAME, MAIN_NAME);
        }
        let winit = GenWorker::new(DataAttWorker::<E, String, _>::new(interface));
        self.stowage
            .property_writer::<_, VarAttBuilder, CsvObj, _, _, _, _, Marker, _>(
                winit, prop_name, self.main, self.sub,
            );
        self.set_path("", "");
        self.stowage.declare::<E, Marker>(&prop_name);
    }
}

impl<'a, S, T, SIF> DataAttWorker<'a, S, T, SIF>
where
    S: MainEntity,
    T: Default + Sync + Send,
    SIF: EntityImmutableMapperBackend<S>,
{
    fn new(self_interface: &'a SIF) -> Self {
        let init_slice = init_empty_slice::<S, T>();
        Self {
            self_interface,
            attribute_arr: init_slice.into(),
            p: PhantomData,
        }
    }
}

impl<'a, S, T, TT, SIF, TIF> GenObjAttWorker<'a, S, T, TT, SIF, TIF>
where
    S: MainEntity,
    T: MappableEntity,
    TT: Default + Sync + Send,
    SIF: EntityImmutableMapperBackend<S>,
    TIF: EntityImmutableMapperBackend<T>,
{
    fn new(source_interface: &'a SIF, att_interface: &'a TIF) -> Self {
        Self {
            data_worker: DataAttWorker::<'a, S, TT, SIF>::new(source_interface),
            att_interface,
            p: PhantomData,
        }
    }
}

impl<W, T1, T2, T3, T4, T5, T6> GenWorker<W, T1, T2, T3, T4, T5, T6> {
    fn new(worker: W) -> Self {
        Self {
            worker,
            phantom_prep: PhantomData,
            phantom_post: PhantomData,
            phantom_ing: PhantomData,
            phantom_m: PhantomData,
            phantom_s: PhantomData,
            phantom_i: PhantomData,
        }
    }
}

impl<T, E> BoxRoller<T, E> {
    fn new(arr: Box<[T]>) -> Self {
        Self {
            arr: arr.into_vec().into_iter(),
            phantom: PhantomData,
        }
    }
}

impl<T> StorableMarker<Self> for T {
    type FinalType = Self;
    fn update(&mut self, other: Self) {
        *self = other;
    }
    fn finalize(self) -> Self::FinalType {
        self
    }
}

impl<T> StorableMarker<T> for Vec<T> {
    type FinalType = Box<[T]>;
    fn update(&mut self, other: T) {
        self.push(other);
    }
    fn finalize(self) -> Self::FinalType {
        self.into_boxed_slice()
    }
}

impl ParsedId for SourceQ {
    fn get_parsed_id(&self) -> Option<BigId> {
        Some(self.id)
    }
}

impl<E, CsvObj> AttGetter<E::KeyType, E> for CsvObj
where
    E: Entity + MappableEntity,
    CsvObj: ObjAttGetter<E>,
{
    fn get_att(&self) -> Option<E::KeyType> {
        self.get_obj_att()
    }
}

impl AttGetter<String, NameExtensionMarker> for Source {
    fn get_att(&self) -> Option<String> {
        post_ext_name(&self.alternate_titles)
    }
}

impl AttGetter<String, NameExtensionMarker> for Institution {
    fn get_att(&self) -> Option<String> {
        post_ext_name(&self.display_name_acronyms)
    }
}

impl AttGetter<String, DoiMarker> for Work {
    fn get_att(&self) -> Option<String> {
        if let Some(doi) = &self.doi {
            if doi.len() > DOI_PREFIX_LEN {
                return Some(doi[DOI_PREFIX_LEN..].to_string());
            }
        }
        None
    }
}

impl<T> AttGetter<String, NameMarker> for T
where
    T: Named,
{
    fn get_att(&self) -> Option<String> {
        Some(self.get_name())
    }
}

impl Named for Source {
    fn get_name(&self) -> String {
        let dn = &self.display_name;
        if let Some((left, right)) = dn.split_once('/') {
            let lmin = min(left.len(), right.len());
            if lmin >= MIN_LEN {
                let rate = 1.0 - levenshtein(left, right) as f64 / lmin as f64;
                if rate >= MIN_RATE {
                    return left.to_string();
                }
            }
        }
        dn.clone()
    }
}

impl ObjAttGetter<Fields> for SubField {
    fn get_obj_att(&self) -> Option<<Fields as MappableEntity>::KeyType> {
        Some(field_id_parse(&self.field))
    }
}

impl ObjAttGetter<Domains> for Field {
    fn get_obj_att(&self) -> Option<<Domains as MappableEntity>::KeyType> {
        Some(field_id_parse(&self.domain))
    }
}

impl ObjAttGetter<Subfields> for Topic {
    fn get_obj_att(&self) -> Option<<Subfields as MappableEntity>::KeyType> {
        Some(field_id_parse(&self.subfield))
    }
}

impl ObjAttGetter<Topics> for WorkTopic {
    fn get_obj_att(&self) -> Option<<Topics as MappableEntity>::KeyType> {
        if self.score.unwrap_or(0.0) > MIN_TOPIC_SCORE {
            return oa_id_parse_opt(self.topic_id.as_ref().unwrap());
        }
        None
    }
}

impl ObjAttGetter<Countries> for Institution {
    fn get_obj_att(&self) -> Option<<Countries as MappableEntity>::KeyType> {
        self.country_code.as_ref().map(|cc| short_string_to_u64(cc))
    }
}

impl ObjAttGetter<Works> for ReferencedWork {
    fn get_obj_att(&self) -> Option<<Works as MappableEntity>::KeyType> {
        oa_id_parse_opt(&self.referenced_work_id)
    }
}

impl ObjAttGetter<AreaFields> for SourceArea {
    fn get_obj_att(&self) -> Option<<AreaFields as MappableEntity>::KeyType> {
        Some(self.raw_area_id())
    }
}

impl ObjAttGetter<Sources> for Location {
    fn get_obj_att(&self) -> Option<<Sources as MappableEntity>::KeyType> {
        self.source_id.as_deref().and_then(oa_id_parse_opt)
    }
}

impl<T, E> Iterator for BoxRoller<T, E>
where
    T: StorableMarker<E>,
{
    type Item = T::FinalType;

    fn next(&mut self) -> Option<Self::Item> {
        self.arr.next().map(|v| v.finalize())
    }
}

impl<'a, Source, TargetType, Marker, SIF>
    GotAttParser<TargetType, TargetType, TargetType, Source, Marker, std::vec::IntoIter<TargetType>>
    for DataAttWorker<'a, Source, TargetType, SIF>
where
    Source: MainEntity,
    TargetType: Sync + Send,
    SIF: EntityImmutableMapperBackend<Source>,
{
    fn parse(&self, att: Option<TargetType>) -> Option<TargetType> {
        att
    }

    fn ingest(&self, res: TargetType, ind: NET<Source>) {
        self.attribute_arr.lock().unwrap()[ind.to_usize()] = res;
    }

    fn map_ind(&self, ind: Source::KeyType) -> Option<NET<Source>> {
        self.self_interface.get_via_immut(&ind)
    }
    fn ingest_result<F>(self, f: F)
    where
        F: Fn(std::vec::IntoIter<TargetType>),
    {
        f(self
            .attribute_arr
            .into_inner()
            .unwrap()
            .into_vec()
            .into_iter())
    }
}

impl<Source, Target, Marker, StoredOfTarget, SIF, TIF>
    GotAttParser<
        Target::KeyType,
        Target::T,
        StoredOfTarget::FinalType,
        Source,
        Marker,
        BoxRoller<StoredOfTarget, Target::T>,
    > for GenObjAttWorker<'_, Source, Target, StoredOfTarget, SIF, TIF>
where
    Source: MainEntity,
    Target: Entity + MappableEntity,
    <Source as Entity>::T: UnsignedNumber,
    TIF: EntityImmutableMapperBackend<Target>,
    SIF: EntityImmutableMapperBackend<Source>,
    StoredOfTarget: StorableMarker<Target::T> + Send + Sync,
{
    fn parse(&self, att_o: Option<Target::KeyType>) -> Option<Target::T> {
        if let Some(att) = att_o {
            self.att_interface.get_via_immut(&att)
        } else {
            None
        }
    }

    fn ingest(&self, res: Target::T, ind: NET<Source>) {
        StoredOfTarget::update(
            &mut self.data_worker.attribute_arr.lock().unwrap()[ind.to_usize()],
            res,
        )
    }

    fn map_ind(&self, ind: Source::KeyType) -> Option<NET<Source>> {
        self.data_worker.self_interface.get_via_immut(&ind)
    }

    fn ingest_result<F>(self, f: F)
    where
        F: Fn(BoxRoller<StoredOfTarget, Target::T>),
    {
        let arr = self.data_worker.attribute_arr.into_inner().unwrap();
        f(BoxRoller::new(arr))
    }
}

impl<
        CsvObj,
        W,
        PreParseTargetType,
        PostParseTargetType,
        IngestableAttType,
        Source,
        AGMarker,
        I,
    > Worker<CsvObj>
    for GenWorker<
        W,
        PreParseTargetType,
        PostParseTargetType,
        IngestableAttType,
        Source,
        AGMarker,
        I,
    >
where
    W: GotAttParser<
            PreParseTargetType,
            PostParseTargetType,
            IngestableAttType,
            Source,
            AGMarker,
            I,
        > + Sync,
    CsvObj: ParsedId + Send + AttGetter<PreParseTargetType, AGMarker>,
    Source: MainEntity,
    PostParseTargetType: Sync,
    I: Iterator<Item = IngestableAttType>,
{
    fn proc(&self, input: CsvObj) {
        if let Some(in_id) = input.get_parsed_id() {
            if let (Some(att), Some(ind)) = (
                self.worker.parse(input.get_att()),
                self.worker.map_ind(in_id),
            ) {
                self.worker.ingest(att, ind);
            }
        }
    }
}

pub fn main(mut stowage: Stowage) -> io::Result<()> {
    let works_interface = {
        let winf = stowage.add_ship_relations();
        stowage.add_work_atts(winf.into())
    };
    let (insts_interface, countries_interface) = stowage.add_inst_atts();
    stowage.add_author_atts();
    let mut str_writer = StrWriter::new(&stowage);
    let domains_interface = str_writer.write_name::<FieldLike, Domains>();
    let fields_interface = str_writer.write_name::<FieldLike, Fields>();
    let subfields_interface = str_writer.write_name::<FieldLike, Subfields>();
    let sources_interface = str_writer.write_name::<Source, Sources>();
    let topics_interface = str_writer.write_name::<NamedEntity, Topics>();

    str_writer.write_name_ext::<Institution, Institutions>(&insts_interface); //TODO: move to inst
                                                                              //atts
    str_writer.write_name_ext::<Source, Sources>(&sources_interface);

    stowage.add_theme_atts::<Subfields, _>(&subfields_interface, field_id_parse);
    stowage.add_theme_atts::<Topics, _>(&topics_interface, oa_id_parse);

    stowage.add_empty_name_ext::<Authors>();
    stowage.add_empty_name_ext::<Countries>();
    stowage.add_empty_name_ext::<Subfields>();

    stowage.add_source_qs(&sources_interface, &YearInterface {});
    stowage.object_property::<Institution, Institutions, Countries, _, _>(
        &insts_interface,
        &countries_interface,
        "inst-countries",
    )?;
    stowage.object_property::<SubField, Subfields, _, _, _>(
        &subfields_interface,
        &fields_interface,
        "subfield-ancestors",
    )?;
    stowage.object_property::<Field, Fields, _, _, _>(
        &fields_interface,
        &domains_interface,
        "field-ancestors",
    )?;
    stowage.object_property::<Topic, Topics, _, _, _>(
        &topics_interface,
        &subfields_interface,
        "topic-subfields",
    )?;
    let area_fields_interface = stowage.get_entity_interface::<AreaFields, QuickestNumbered>();
    stowage.multi_object_property::<SourceArea, Sources, _, _, _>(
        &sources_interface,
        &area_fields_interface,
        "source-area-fields",
        AreaFields::NAME,
    )?;
    stowage.multi_object_property::<ReferencedWork, Works, _, _, _>(
        &works_interface,
        &works_interface,
        "work-references",
        works::atts::referenced_works,
    )?;
    stowage.multi_object_property::<Location, Works, _, _, _>(
        &works_interface,
        &sources_interface,
        "work-sources",
        works::atts::locations,
    )?;
    stowage.multi_object_property::<WorkTopic, Works, _, _, _>(
        &works_interface,
        &topics_interface,
        "work-topics",
        works::atts::topics,
    )?;

    stowage.write_code()?;
    Ok(())
}

fn get_name_name<E: Entity>() -> String {
    format!("{}-names", E::NAME)
}

fn get_name_ext_name<E: Entity>() -> String {
    format!("{}-name-exts", E::NAME)
}

fn iter_mboxa<T>(ba: Mutex<Box<[T]>>) -> std::vec::IntoIter<T> {
    ba.into_inner().unwrap().into_vec().into_iter()
}

fn post_ext_name(in_str: &Option<String>) -> Option<String> {
    Some(read_post_str_arr(in_str).join(" "))
}

fn add_name_box<E: Entity>(stowage: &Stowage, names: Box<[String]>) {
    stowage.declare_iter::<VarAttBuilder, _, _, E, NameMarker>(
        names.into_vec().into_iter(),
        &get_name_name::<E>(),
    );
}

fn assign_farr<const S: usize>(
    so: Option<String>,
    prefix: &str,
    arr: &mut Box<[[u8; S]]>,
    ind: usize,
) {
    if let Some(s) = so {
        arr[ind] = s.as_bytes()[prefix.len()..].try_into().unwrap();
    }
}

fn get_wind<T: ParsedId, U: UnsignedNumber>(obj: &T, inf: &LoadedIdMap<U>) -> Option<usize> {
    obj.get_parsed_id()
        .and_then(|id| inf.0.get(&id))
        .map(|i| i.to_usize())
}
