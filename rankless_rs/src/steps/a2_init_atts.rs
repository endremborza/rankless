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
    user_ledger::{augment_with_aliases, build_author_orcid_map, UserLedger, ORCID_PREF},
};
use dmove::{
    par_join, para::Worker, BigId, DiscoMapEntityBuilder, DowncastingBuilder,
    DowncastingPrefixedVarBuilder, Entity, EntityImmutableMapperBackend, FixAttBuilder,
    LoadedIdMap, MappableEntity, MetaIntegrator, NamespacedEntity, UnsignedNumber, VarAttBuilder,
    ET,
};
use levenshtein::levenshtein;
use serde::{de::DeserializeOwned, Deserialize};
use std::{
    cmp::min,
    collections::HashMap,
    io,
    marker::PhantomData,
    sync::{Arc, Mutex},
};
use tqdm::Iter;

pub const DOI_PREFIX_LEN: usize = 16;
const MIN_TOPIC_SCORE: f64 = 0.7;
const MIN_RATE: f64 = 0.8;
const MIN_LEN: usize = 10;

pub type OrcidType = [u8; 19];

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

struct ShipRelWriter<'a> {
    fship2a: Vec<usize>,
    fship2is: Vec<Vec<ET<Institutions>>>,
    fship2pos: Vec<u16>,

    dship2a: Vec<usize>,
    dship2is: Vec<Vec<ET<Institutions>>>,
    dship2pos: Vec<u16>,

    w2combined_ships: Box<[Vec<(bool, usize)>]>,

    winf: Arc<LoadedIdMap<ET<Works>>>,
    fainf: LoadedIdMap<ET<Authors>>,
    dainf: LoadedIdMap<ET<DiscardedAuthors>>,
    iinf: LoadedIdMap<ET<Institutions>>,
    removed_edges: &'a hashbrown::HashSet<(dmove::BigId, dmove::BigId)>,
    seen_filtered_ships: hashbrown::HashSet<(usize, usize)>,
}

struct WorkBiblioWriter {
    biblios: Mutex<Box<[BiblioInfo]>>,
    winf: Arc<LoadedIdMap<ET<Works>>>,
    work_drops: Arc<hashbrown::HashSet<dmove::BigId>>,
}

struct WorkAttWriter {
    wyears: Mutex<Box<[ET<Years>]>>,
    wnames: Mutex<Box<[String]>>,
    wdois: Mutex<Box<[String]>>,
    winf: Arc<LoadedIdMap<ET<Works>>>,
    /// Drop-side work oa_ids: skip their attributes (keep's win).
    work_drops: Arc<hashbrown::HashSet<dmove::BigId>>,
}

struct BoxRoller<T, E> {
    arr: std::vec::IntoIter<T>,
    phantom: PhantomData<fn() -> E>,
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
    fn add_source_qs<SIF, YIF>(&self, sources_interface: &SIF, years_interface: &YIF)
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
        &self,
    ) -> (
        BeS<QuickestNumbered, Institutions>,
        BeS<QuickestNumbered, Countries>,
    ) {
        let cif = self.get_entity_interface::<Cities, QuickestNumbered>();
        let iif: BeS<QuickestNumbered, Institutions> =
            self.get_entity_interface::<Institutions, QuickestNumbered>();
        let coif = self.get_entity_interface::<Countries, QuickestNumbered>();
        let mut ciname_counts = init_empty_slice::<Cities, HashMap<String, u32>>();
        let mut coname_counts = init_empty_slice::<Countries, HashMap<String, u32>>();
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
                *ciname_counts[cid.to_usize()]
                    .entry(cgeo.city.unwrap_or_default())
                    .or_insert(0) += 1;
                *coname_counts[coid.to_usize()]
                    .entry(cgeo.country.unwrap_or_default())
                    .or_insert(0) += 1;
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
        let pick_best = |counts: Box<[HashMap<String, u32>]>| -> Box<[String]> {
            counts
                .into_vec()
                .into_iter()
                .map(|m| {
                    m.into_iter()
                        .max_by_key(|(_, c)| *c)
                        .map(|(k, _)| k)
                        .unwrap_or_default()
                })
                .collect()
        };
        add_name_box::<Countries>(self, pick_best(coname_counts));
        add_name_box::<Cities>(self, pick_best(ciname_counts));
        add_name_box::<Institutions>(self, inames);
        self.add_barr::<FixAttBuilder, _>(ccs, "country-codes");
        self.add_iter_owned::<FixAttBuilder, _, _>(cc3s.into_iter(), Some("country-codes-three"));
        self.add_barr::<FixAttBuilder, _>(locs, "inst-locs");
        self.add_barr::<FixAttBuilder, _>(rors, "inst-rors");
        self.add_barr::<FixAttBuilder, _>(cities, "inst-cities");

        (iif, coif)
    }

    fn add_author_atts(&self, ledger: &UserLedger) {
        let mut aif = self.get_entity_interface::<Authors, QuickestNumbered>();
        // Augment so drop-side oa_ids resolve to keep's dm_id.
        augment_with_aliases(&mut aif, &ledger.author_aliases);
        self.add_nobels(&aif);
        let mut names = init_empty_slice::<Authors, String>();
        let mut wiki_slugs = init_empty_slice::<Authors, String>();
        let mut orcids = init_empty_slice::<Authors, OrcidType>();
        let mut raw_cites = init_empty_slice::<Authors, usize>();
        let mut raw_works = init_empty_slice::<Authors, usize>();

        let discarded_name_iter = self
            .read_csv_objs::<Author>(Authors::NAME, MAIN_NAME)
            .filter_map(|aobj| {
                let pid = aobj.get_parsed_id()?;
                let aname = aobj.display_name.unwrap_or_default();
                let Some(aidt) = aif.0.get(&pid) else {
                    return Some(aname);
                };
                let aid = aidt.to_usize();
                // Counts always accumulate (zero-initialised slice); merging a drop
                // into a keep is just two += against the same dm_id, which is order-
                // independent across CSV rows.
                raw_cites[aid] += aobj.cited_by_count.unwrap_or(0) as usize;
                raw_works[aid] += aobj.works_count.unwrap_or(0) as usize;
                if !ledger.author_aliases.contains_key(&pid) {
                    names[aid] = aname;
                    assign_farr(aobj.orcid, ORCID_PREF, &mut orcids, aid);
                }
                None
            });

        for wobj in self.read_csv_objs::<WikiId>(Authors::NAME, "wiki-slug") {
            if let Some(aidt) = aif.0.get(&wobj.oa_id) {
                // Only set wiki slug for keep-side authors.
                if !ledger.author_aliases.contains_key(&wobj.oa_id) {
                    wiki_slugs[aidt.to_usize()] = wobj.slug;
                }
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

    fn add_theme_atts<E, F>(&self, ifs: &BeS<QuickestNumbered, E>, gatt: F)
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

    fn add_work_atts(
        &self,
        winf: Arc<LoadedIdMap<ET<Works>>>,
        work_drops: Arc<hashbrown::HashSet<dmove::BigId>>,
    ) -> (LoadedIdMap<ET<Works>>, Box<[ET<Years>]>) {
        let wyears = WorkAttWriter::new(winf.clone(), work_drops)
            .para(self.read_csv_objs(Works::NAME, MAIN_NAME))
            .post(self);
        (Arc::into_inner(winf).unwrap(), wyears)
    }

    fn add_ship_relations(
        &self,
        ledger: &UserLedger,
        work_drops: Arc<hashbrown::HashSet<dmove::BigId>>,
    ) -> LoadedIdMap<ET<Works>> {
        let mut winf: LoadedIdMap<ET<Works>> =
            self.get_entity_interface::<Works, QuickestNumbered>();
        augment_with_aliases(&mut winf, &ledger.work_aliases);
        let winf: Arc<LoadedIdMap<ET<Works>>> = winf.into();

        let mut ship_rel_writer = ShipRelWriter::new(winf.clone(), self, ledger);
        for ship in iter_authorships(self) {
            ship_rel_writer.proc_next(ship);
        }
        ship_rel_writer.post(self);
        {
            WorkBiblioWriter::new(winf.clone(), work_drops.clone())
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
        &self,
        source_interface: &SIF,
        target_interface: &TIF,
        fatt_name: &str,
    ) where
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
    }

    fn multi_object_property<CsvObj, Source, Target, SIF, TIF>(
        &self,
        source_interface: &SIF,
        target_interface: &TIF,
        fatt_name: &str,
        sub: &str,
    ) where
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
    }

    fn add_empty_name_ext<T: Entity>(&self) {
        let name = get_name_ext_name::<T>();
        self.add_empty_something::<T, NameExtensionMarker>(&name);
    }

    fn add_empty_something<E: Entity, Marker>(&self, name: &str) {
        //TODO: this takes memory (and some space) for no fucking reason
        let iter = (0..=E::N).map(|_| String::new());
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
    fn new(
        winf: Arc<LoadedIdMap<ET<Works>>>,
        work_drops: Arc<hashbrown::HashSet<dmove::BigId>>,
    ) -> Self {
        Self {
            wdois: init_empty_slice::<Works, _>().into(),
            wyears: init_empty_slice::<Works, _>().into(),
            wnames: init_empty_slice::<Works, _>().into(),
            winf,
            work_drops,
        }
    }

    fn post(self, stowage: &Stowage) -> Box<[ET<Years>]> {
        let wyname = "work-years";
        let wyears = self.wyears.into_inner().unwrap();
        stowage.add_iter_owned::<FixAttBuilder, _, _>(wyears.iter().copied(), Some(wyname));
        stowage.declare_link::<Works, Years>(wyname);
        stowage.declare_iter::<VarAttBuilder, _, _, Works, NameMarker>(
            iter_mboxa(self.wnames),
            &get_name_name::<Works>(),
        );
        stowage.declare_iter::<VarAttBuilder, _, _, Works, DoiMarker>(
            iter_mboxa(self.wdois),
            "work-dois",
        );
        wyears
    }
}

impl<'a> ShipRelWriter<'a> {
    fn new(winf: Arc<LoadedIdMap<ET<Works>>>, stowage: &Stowage, ledger: &'a UserLedger) -> Self {
        let mut fainf = stowage.get_entity_interface::<Authors, QuickestNumbered>();
        augment_with_aliases(&mut fainf, &ledger.author_aliases);
        Self {
            fship2a: vec![0],
            fship2is: vec![Vec::new()],
            fship2pos: vec![0],
            dship2a: vec![0],
            dship2is: vec![Vec::new()],
            dship2pos: vec![0],
            w2combined_ships: init_empty_slice::<Works, _>(),
            winf,
            fainf,
            dainf: stowage.get_entity_interface::<DiscardedAuthors, QuickestNumbered>(),
            iinf: stowage.get_entity_interface::<Institutions, QuickestNumbered>(),
            removed_edges: &ledger.removed_edges,
            seen_filtered_ships: hashbrown::HashSet::new(),
        }
    }

    fn proc_next(&mut self, ship: Authorship) {
        let work_oa = match ship.get_parsed_id() {
            Some(w) => w,
            None => return,
        };
        let w_ind = match self.winf.0.get(&work_oa) {
            Some(w) => w.to_usize(),
            None => return,
        };

        // Skip edges that the user has disowned.
        if let Some(author_oa) = ship.author_id.as_deref().and_then(oa_id_parse_opt) {
            if self.removed_edges.contains(&(author_oa, work_oa)) {
                return;
            }
        }

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

        if is_filtered && !self.seen_filtered_ships.insert((w_ind, aid)) {
            return;
        }

        let (ship2a, ship2is, ship2pos) = if is_filtered {
            (&mut self.fship2a, &mut self.fship2is, &mut self.fship2pos)
        } else {
            (&mut self.dship2a, &mut self.dship2is, &mut self.dship2pos)
        };
        let ship_ind = ship2a.len();
        ship2a.push(aid);
        ship2is.push(ivec);
        ship2pos.push(ship.position);
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
        stowage.add_iter_owned::<DowncastingBuilder, _, _>(
            self.fship2pos.into_iter().map(|p| p as usize),
            Some("filtered-authorship-position"),
        );
        stowage.add_iter_owned::<DowncastingBuilder, _, _>(
            self.dship2pos.into_iter().map(|p| p as usize),
            Some("discarded-authorship-position"),
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
    fn new(
        winf: Arc<LoadedIdMap<ET<Works>>>,
        work_drops: Arc<hashbrown::HashSet<dmove::BigId>>,
    ) -> Self {
        Self {
            biblios: init_empty_slice::<Works, _>().into(),
            winf,
            work_drops,
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
        // Drop-side work: keep's attrs win; skip.
        if let Some(oa_id) = input.get_parsed_id() {
            if self.work_drops.contains(&oa_id) {
                return;
            }
        }

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
        // Drop-side work: keep's biblio wins; skip.
        if let Some(oa_id) = bib.get_parsed_id() {
            if self.work_drops.contains(&oa_id) {
                return;
            }
        }
        let new_bib: BiblioInfo = bib.into();
        if new_bib != BiblioInfo::default() {
            self.biblios.lock().unwrap()[w_ind] = new_bib;
        }
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

    fn take_arr(self) -> Box<[TT]> {
        self.data_worker.attribute_arr.into_inner().unwrap()
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

fn write_entity_name<CsvObj, E>(stowage: &Stowage) -> BeS<QuickestNumbered, E>
where
    CsvObj: DeserializeOwned + ParsedId + AttGetter<String, NameMarker> + Send,
    E: MainEntity + NamespacedEntity,
{
    let interface = stowage.get_entity_interface::<E, QuickestNumbered>();
    let prop_name = get_name_name::<E>();
    let winit = GenWorker::new(DataAttWorker::<E, String, _>::new(&interface));
    stowage.property_writer::<_, VarAttBuilder, CsvObj, _, _, _, _, NameMarker, _>(
        winit,
        &prop_name,
        E::NAME,
        MAIN_NAME,
    );
    stowage.declare::<E, NameMarker>(&prop_name);
    interface
}

fn write_entity_name_ext<CsvObj, E>(stowage: &Stowage, interface: &BeS<QuickestNumbered, E>)
where
    CsvObj: DeserializeOwned + ParsedId + AttGetter<String, NameExtensionMarker> + Send,
    E: MainEntity + NamespacedEntity,
{
    let prop_name = get_name_ext_name::<E>();
    let winit = GenWorker::new(DataAttWorker::<E, String, _>::new(interface));
    stowage.property_writer::<_, VarAttBuilder, CsvObj, _, _, _, _, NameExtensionMarker, _>(
        winit,
        &prop_name,
        E::NAME,
        MAIN_NAME,
    );
    stowage.declare::<E, NameExtensionMarker>(&prop_name);
}

pub fn main(stowage: Stowage) -> io::Result<()> {
    let mut ledger = UserLedger::load(&stowage)?;
    let orcid_to_oa = build_author_orcid_map(&stowage);
    ledger.resolve_orcids(&orcid_to_oa);

    // Collect drop-side work oa_ids for attribute writers.
    let work_drops: Arc<hashbrown::HashSet<dmove::BigId>> =
        Arc::new(ledger.work_aliases.keys().copied().collect());

    let (works_interface, wyears) = {
        let winf = stowage.add_ship_relations(&ledger, work_drops.clone());
        stowage.add_work_atts(winf.into(), work_drops.clone())
    };
    let sarc = Arc::new(stowage);

    // Wave 1: parallel heavy CSV reads (institutions, authors, 5 entity name tables)
    let (
        (insts_interface, countries_interface),
        domains_interface,
        fields_interface,
        subfields_interface,
        sources_interface,
        topics_interface,
    ) = std::thread::scope(|s| {
        s.spawn(|| sarc.add_author_atts(&ledger));
        let h1 = s.spawn(|| sarc.add_inst_atts());
        let h3 = s.spawn(|| write_entity_name::<FieldLike, Domains>(&sarc));
        let h4 = s.spawn(|| write_entity_name::<FieldLike, Fields>(&sarc));
        let h5 = s.spawn(|| write_entity_name::<FieldLike, Subfields>(&sarc));
        let h6 = s.spawn(|| write_entity_name::<Source, Sources>(&sarc));
        let h7 = s.spawn(|| write_entity_name::<NamedEntity, Topics>(&sarc));
        (
            h1.join().unwrap(),
            h3.join().unwrap(),
            h4.join().unwrap(),
            h5.join().unwrap(),
            h6.join().unwrap(),
            h7.join().unwrap(),
        )
    });

    // Wave 2: parallel name extensions, theme attrs, empty exts, source qs
    par_join!(
        || write_entity_name_ext::<Institution, Institutions>(&sarc, &insts_interface),
        || write_entity_name_ext::<Source, Sources>(&sarc, &sources_interface),
        || sarc.add_theme_atts::<Subfields, _>(&subfields_interface, field_id_parse),
        || sarc.add_theme_atts::<Topics, _>(&topics_interface, oa_id_parse),
        || sarc.add_empty_name_ext::<Authors>(),
        || sarc.add_empty_name_ext::<Countries>(),
        || sarc.add_empty_name_ext::<Subfields>(),
        || sarc.add_source_qs(&sources_interface, &YearInterface {}),
    );

    // Wave 3: parallel property writes, multi-object properties, and work-references
    let area_fields_interface = sarc.get_entity_interface::<AreaFields, QuickestNumbered>();
    par_join!(
        || sarc.object_property::<Institution, Institutions, Countries, _, _>(
            &insts_interface,
            &countries_interface,
            "inst-countries"
        ),
        || sarc.object_property::<SubField, Subfields, _, _, _>(
            &subfields_interface,
            &fields_interface,
            "subfield-ancestors"
        ),
        || sarc.object_property::<Field, Fields, _, _, _>(
            &fields_interface,
            &domains_interface,
            "field-ancestors"
        ),
        || sarc.object_property::<Topic, Topics, _, _, _>(
            &topics_interface,
            &subfields_interface,
            "topic-subfields"
        ),
        || sarc.multi_object_property::<SourceArea, Sources, _, _, _>(
            &sources_interface,
            &area_fields_interface,
            "source-area-fields",
            AreaFields::NAME
        ),
        || sarc.multi_object_property::<Location, Works, _, _, _>(
            &works_interface,
            &sources_interface,
            "work-sources",
            works::atts::locations
        ),
        || sarc.multi_object_property::<WorkTopic, Works, _, _, _>(
            &works_interface,
            &topics_interface,
            "work-topics",
            works::atts::topics
        ),
        || {
            let refs = GenWorker::new(
                GenObjAttWorker::<'_, Works, Works, Vec<NET<Works>>, _, _>::new(
                    &works_interface,
                    &works_interface,
                ),
            )
            .para(sarc.read_csv_objs::<ReferencedWork>(Works::NAME, works::atts::referenced_works))
            .worker
            .take_arr();
            let mut n_inversions = 0usize;
            sarc.add_iter_owned::<VarAttBuilder, _, _>(
                refs.into_vec()
                    .into_iter()
                    .enumerate()
                    .map(|(citing_dm, cited)| {
                        let cy = wyears[citing_dm];
                        let mut out = Vec::new();
                        for refed_wid in cited.into_iter() {
                            if cy > 0 && wyears[refed_wid.to_usize()] > cy {
                                n_inversions += 1;
                            } else {
                                out.push(refed_wid);
                            }
                        }
                        out.into_boxed_slice()
                    }),
                Some("work-references"),
            );
            sarc.declare_link::<Works, Works>("work-references");
            println!("Year inversions (ref year > citing year): {n_inversions}");
        },
    );

    let stowage = Arc::try_unwrap(sarc).ok().unwrap();
    stowage.write_code()?;
    ledger.write_final_manifest(&stowage)?;
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
