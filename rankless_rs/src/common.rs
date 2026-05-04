use std::fmt::{Debug, Display};
use std::io::{prelude::*, BufWriter};
use std::marker::PhantomData;
use std::num::ParseIntError;
use std::ops::Range;
use std::sync::{Arc, Mutex, MutexGuard};
use std::{
    fs::{create_dir_all, read_dir, File},
    io::{self, BufReader, Write},
    path::{Path, PathBuf},
};

use hashbrown::{HashMap, HashSet};
use serde::Deserialize;
use serde::{de::DeserializeOwned, Serialize};

use dmove::{
    BackendLoading, BigId, ByteFixArrayInterface, CompactEntity, Entity, FixAttBuilder,
    FixAttIterator, FixWriteSizeEntity, LoadedIdMap, Locators, MainBuilder, MappableEntity,
    MarkedAttribute, MetaIntegrator, MmapSlice, NamespacedEntity, UnsignedNumber, VarAttBuilder,
    VarAttIterator, VarBox, VarSizedAttributeElement, VariableSizeAttribute, VattArrPair,
    VattReadingMap, ET, MAA,
};

pub use crate::csv_iter::ObjIter;
pub type BeS<M, E> = <M as BackendSelector<E>>::BE;
pub type NET<E> = <E as NumberedEntity>::T;

pub const MAIN_NAME: &str = "main";
pub const BUILD_LOC: &str = "qc-builds";
pub const SEM_DIR: &str = "semantic-ids";
// pub const A_STAT_PATH: &str = "attribute-statics";
// pub const QC_CONF: &str = "qc-specs";

pub const ID_PREFIX: &str = "https://openalex.org/";
pub const N_PEERS: usize = 10;

pub struct NameMarker;
pub struct NameExtensionMarker;
pub struct DoiMarker;
pub struct SemanticIdMarker;
pub struct MainWorkMarker;
pub struct HitWorkMarker;
pub struct WorkCountMarker;
pub struct CiteCountMarker;
pub struct RefSubfieldsArrayMarker;
pub struct CitSubfieldsArrayMarker;
pub struct YearlyPapersMarker;
pub struct YearlyCitationsMarker;
pub struct InstRelMarker;
pub struct Top3PaperSfMarker;
pub struct Top3CitingSfMarker;
pub struct Top3PaperTopicMarker;
pub struct Top15AuthorMarker;
pub struct Top3CitingTopicMarker;
pub struct Top3JournalMarker;
pub struct Top3AffCountryMarker;
pub struct PeerMarker;
pub struct HIndexMarker;
pub struct YearCentroidMarker;

pub struct EmptyAttributeEntity<T> {
    p: PhantomData<T>,
}

#[macro_export]
macro_rules! add_parsed_id_traits {
    ($($struct:ident),*) => {
        $(impl ParsedId for $struct {
            fn get_parsed_id(&self) -> Option<BigId> {
                oa_id_parse_opt(self.id.as_ref().unwrap())
            }
        }
        )*
    };
}

#[macro_export]
macro_rules! add_strict_parsed_id_traits {
    ($($struct:ident),*) => {
        $(impl ParsedId for $struct {
            fn get_parsed_id(&self) -> Option<BigId> {
                oa_id_parse_opt(&self.id)
            }
        }
        )*
    };
}

#[macro_export]
macro_rules! add_parent_parsed_id_traits {
    ($($struct:ident),*) => {
        $(
        impl ParsedId for $struct {
            fn get_parsed_id(&self) -> Option<BigId> {
                oa_id_parse_opt(self.parent_id.as_ref().unwrap())
            }
        }
        )*
    }
}

#[macro_export]
macro_rules! make_interface_struct {
    // 4-category compat: delegates to 5-category with empty loc group
    ($IT:ident, $($e_key:ident > $e_t:ty),*;$($f_key:ident => $f_t:ty),*; $($v_key:ident -> $v_t:ty),*; $($m_key:ident >> $m_t:ty),*) => {
        $crate::make_interface_struct!($IT, $($e_key > $e_t),*; $($f_key => $f_t),*; $($v_key -> $v_t),*;; $($m_key >> $m_t),*);
    };
    // 5-category canonical (e, f, v, loc, m)
    ($IT:ident, $($e_key:ident > $e_t:ty),*;$($f_key:ident => $f_t:ty),*; $($v_key:ident -> $v_t:ty),*; $($loc_key:ident loc $loc_t:ty),*; $($m_key:ident >> $m_t:ty),*) => {
        pub struct $IT {
            $(pub $e_key: BeS<QuickAttPair, MAA<$e_t, MainWorkMarker>>,)*
            $(pub $f_key: BeS<QuickestBox, $f_t>,)*
            $(pub $v_key: BeS<QuickAttPair, $v_t>,)*
            $(pub $loc_key: std::sync::Arc<dmove::Locators<$loc_t>>,)*
            $(pub $m_key: BeS<QuickMap, $m_t>,)*
        }

        impl $IT {
            fn new(stowage: std::sync::Arc<Stowage>) -> Self {
                $(
                    let stowage_clone = std::sync::Arc::clone(&stowage);
                    let $e_key = std::thread::spawn(move || {
                        <$e_t as WorkLoader>::load_work_interface(stowage_clone)
                    });
                )*
                $(
                    let stowage_clone = std::sync::Arc::clone(&stowage);
                    let $f_key = std::thread::spawn(move || {
                        stowage_clone.get_entity_interface::<$f_t, QuickestBox>()
                    });
                )*
                $(
                    let stowage_clone = std::sync::Arc::clone(&stowage);
                    let $v_key = std::thread::spawn(move || {
                        stowage_clone.get_entity_interface::<$v_t, QuickAttPair>()
                    });
                )*
                $(
                    let stowage_clone = std::sync::Arc::clone(&stowage);
                    let $loc_key = std::thread::spawn(move || {
                        $crate::common::get_locator::<$loc_t>(&stowage_clone)
                    });
                )*
                $(
                    let stowage_clone = std::sync::Arc::clone(&stowage);
                    let $m_key = std::thread::spawn(move || {
                        stowage_clone.get_entity_interface::<$m_t, QuickMap>()
                    });
                )*
                Self {
                    $($e_key: $e_key.join().expect("Thread panicked"),)*
                    $($f_key: $f_key.join().expect("Thread panicked"),)*
                    $($v_key: $v_key.join().expect("Thread panicked"),)*
                    $($loc_key: $loc_key.join().expect("Thread panicked"),)*
                    $($m_key: $m_key.join().expect("Thread panicked"),)*
                }
            }

            pub fn fake() -> Self {
                Self {
                    $($f_key: Vec::new().into(),)*
                    $($e_key: VattArrPair::empty(),)*
                    $($v_key: VattArrPair::empty(),)*
                    $($loc_key: dmove::Locators::<$loc_t>::empty().into(),)*
                    $($m_key: HashMap::new().into(),)*
                }
            }
        }
    };
}

pub fn get_locator<E>(stowage: &Stowage) -> std::sync::Arc<Locators<E>>
where
    Locators<E>: BackendLoading<E>,
    E: NamespacedEntity + VariableSizeAttribute,
    ET<E>: VarSizedAttributeElement,
{
    let path = stowage.path_from_ns(E::NS);
    <Locators<E> as BackendLoading<E>>::load_backend(&path).into()
}

macro_rules! pathfields_fn {
    ($struct:ident, $($k:ident),*) => {

        pub struct $struct {
            $(pub $k: PathBuf,)*
        }

        impl $struct {
            pub fn new(root_path: &str) -> Self{
                $(
                    let $k = Path::new(root_path).join(stringify!($k).replace("_","-"));
                    let _d = &$k;
                    create_dir_all(&$k).unwrap_or_else(|_| {println!("can't create {_d:?} directory");});
                )*

                Self {
                    $(
                        $k,
                    )*
                }
            }
        }
    };
}

pub struct Stowage {
    pub paths: PathCollection,
    current_ns: String,
    builder: Option<Mutex<MainBuilder>>,
}

//TODO/clarity: this is sort of a mess - could be just generic types
pub struct QuickestNumbered {}
pub struct QuickMap {}
pub struct QuickestBox {}
pub struct MmapBox {}
pub struct QuickAttPair {}
pub struct QuickestVBox {}
pub struct VarFile {}
pub struct ReadIter {}
pub struct ReadFixIter {}
pub struct IterCompactElement {}

#[derive(Deserialize)]
pub struct SemanticElem {
    pub id: BigId,
    pub semantic_id: String,
}

pub trait BackendSelector<E>
where
    E: Entity,
{
    type BE;
}

pub trait MarkedBackendLoader<Mark>: Entity {
    type BE;

    fn load(stowage: &Stowage) -> Self::BE;
}

pub trait WorkLoader: MarkedAttribute<MainWorkMarker>
where
    MAA<Self, MainWorkMarker>: CompactEntity + VariableSizeAttribute + NamespacedEntity,
    ET<MAA<Self, MainWorkMarker>>: VarSizedAttributeElement,
{
    fn load_work_interface(stowage: Arc<Stowage>) -> BeS<QuickAttPair, MAA<Self, MainWorkMarker>> {
        stowage.get_entity_interface::<MAA<Self, MainWorkMarker>, QuickAttPair>()
    }
}

pub trait NumberedEntity: MappableEntity<KeyType = BigId> {
    type T: UnsignedNumber + DeserializeOwned + Serialize + Ord + Copy + Display;
}

pub trait MainEntity: NumberedEntity + Entity<T = NET<Self>> {}

pathfields_fn!(
    PathCollection,
    entity_csvs,
    filter_steps,
    cache,
    user_ledger
);

pub trait ParsedId {
    fn get_parsed_id(&self) -> Option<BigId>;
}

impl Stowage {
    pub fn new(root_path: &str) -> Self {
        Self {
            paths: PathCollection::new(root_path),
            current_ns: "".to_string(),
            builder: None,
        }
    }

    pub fn set_namespace(&mut self, ns: &'static str) {
        self.current_ns = ns.to_string();
        let path = self.path_from_ns(&self.current_ns);
        create_dir_all(&path).unwrap();
        self.builder = Some(Mutex::new(MainBuilder::new(&path)));
    }

    pub fn write_code(&self) -> io::Result<usize> {
        let suffix = self.current_ns.replace("-", "_");
        self.mu_bu().write_code(&code_path(&suffix))
    }

    pub fn get_out_csv_path(&self) -> &str {
        self.paths.entity_csvs.to_str().unwrap()
    }

    pub fn get_filter_dir(&self, step_id: u8) -> PathBuf {
        let out_root = self.paths.filter_steps.join(step_id.to_string());
        create_dir_all(&out_root).unwrap();
        out_root
    }

    pub fn get_last_filter(&self, entity_type: &str) -> Option<HashSet<BigId>> {
        let mut out_path = None;

        if !self.paths.entity_csvs.join(entity_type).exists() {
            println!("no such type {entity_type}");
            return None;
        }
        let dirs = match read_dir(&self.paths.filter_steps) {
            Err(_) => vec![],
            Ok(rdir) => {
                let mut v: Vec<PathBuf> = rdir.map(|e| e.unwrap().path()).collect();
                v.sort();
                v
            }
        };
        for edir in dirs {
            let maybe_path = edir.join(entity_type);
            if maybe_path.exists() {
                out_path = Some(maybe_path);
            }
        }
        match out_path {
            Some(pb) => {
                let mut out = HashSet::new();
                let mut br: [u8; 8] = [0; std::mem::size_of::<BigId>()];
                let mut file = File::open(pb).unwrap();
                while let Ok(_) = file.read_exact(&mut br) {
                    out.insert(BigId::from_be_bytes(br));
                }
                Some(out)
            }
            None => None,
        }
    }

    pub fn write_filter<'a, T>(&self, step_id: u8, entity_type: &str, id_iter: T) -> io::Result<()>
    where
        T: Iterator<Item = BigId>,
    {
        let mut file = File::create(self.get_filter_dir(step_id).join(entity_type))?;
        for e in id_iter {
            file.write_all(&e.to_be_bytes())?;
        }
        Ok(())
    }

    pub fn add_iter_owned<B, I, T>(&self, iter: I, name_o: Option<&str>)
    where
        B: MetaIntegrator<T>,
        I: Iterator<Item = T>,
    {
        let name = name_o.unwrap(); //TODO - temp
        B::add_iter_owned(&self.builder.as_ref().unwrap(), iter, &name);
        self.mu_bu().declare_ns(&name, &self.current_ns);
    }

    pub fn add_barr<B, T>(&self, barr: Box<[T]>, name: &str)
    where
        B: MetaIntegrator<T>,
    {
        self.add_iter_owned::<B, _, T>(barr.into_vec().into_iter(), Some(name));
    }

    pub fn add_barr_of_vecs<T>(&self, barr: Box<[Vec<T>]>, name: &str)
    where
        VarAttBuilder: MetaIntegrator<Box<[T]>>,
    {
        self.add_iter_owned::<VarAttBuilder, _, Box<[T]>>(
            barr.into_vec().into_iter().map(|e| e.into_boxed_slice()),
            Some(name),
        );
    }

    pub fn declare_link<S: Entity, T: Entity>(&self, name: &str) {
        self.mu_bu().declare_link::<S, T>(name);
    }

    pub fn declare<E, Marker>(&self, name: &str) {
        self.mu_bu().declare_marked_attribute::<E, Marker>(&name);
    }

    pub fn declare_iter<B, I, E, S, M>(&self, iter: I, name: &str)
    where
        B: MetaIntegrator<E>,
        I: Iterator<Item = E>,
    {
        self.add_iter_owned::<B, I, E>(iter, Some(name));
        self.declare::<S, M>(name)
    }

    pub fn ditf<Marker, E, T>(&self, v: Vec<T>, suff: &str)
    where
        E: Entity,
        T: ByteFixArrayInterface,
    {
        self.declare_iter::<FixAttBuilder, _, _, E, Marker>(
            v.into_iter(),
            &format!("{}-{suff}", E::NAME),
        );
    }

    pub fn read_csv_objs<T: DeserializeOwned>(
        &self,
        main_path: &str,
        sub_path: &str,
    ) -> ObjIter<T> {
        ObjIter::from_dir(&self.paths.entity_csvs, main_path, sub_path)
    }

    pub fn get_entity_interface<E, Marker>(&self) -> Marker::BE
    where
        Marker: BackendSelector<E>,
        E: MarkedBackendLoader<Marker, BE = Marker::BE>,
    {
        E::load(self)
    }

    pub fn get_marked_interface<E, AttMarker, BeMarker>(&self) -> BeMarker::BE
    where
        E: Entity + MarkedAttribute<AttMarker>,
        BeMarker: BackendSelector<E::AttributeEntity>,
        MAA<E, AttMarker>: MarkedBackendLoader<BeMarker, BE = BeMarker::BE>,
    {
        self.get_entity_interface::<MAA<E, AttMarker>, BeMarker>()
    }

    pub fn path_from_ns(&self, ns: &str) -> PathBuf {
        self.paths.entity_csvs.parent().unwrap().join(ns)
    }

    pub fn mu_bu(&self) -> MutexGuard<'_, MainBuilder> {
        self.builder.as_ref().unwrap().lock().unwrap()
    }
}

impl<E> NumberedEntity for E
where
    E: MappableEntity<KeyType = BigId>,
    ET<E>: UnsignedNumber + Serialize + DeserializeOwned,
{
    type T = ET<E>;
}

impl<E> MainEntity for E where E: Entity<T = NET<E>> + NumberedEntity {}

impl<E, BeMarker> MarkedBackendLoader<BeMarker> for E
where
    E: NamespacedEntity,
    BeMarker: BackendSelector<E>,
    BeMarker::BE: BackendLoading<E>,
{
    type BE = BeMarker::BE;
    fn load(stowage: &Stowage) -> Self::BE {
        let path = stowage.path_from_ns(E::NS);
        let now = std::time::Instant::now();
        let out = BeMarker::BE::load_backend(&path);
        println!(
            "loaded {} from {path:?} in {}s",
            E::NAME,
            now.elapsed().as_secs()
        );
        out
    }
}

impl<T, BeMarker> MarkedBackendLoader<BeMarker> for EmptyAttributeEntity<T>
where
    BeMarker: BackendSelector<Self>,
    BeMarker::BE: Default,
{
    type BE = BeMarker::BE;
    fn load(_: &Stowage) -> Self::BE {
        Self::BE::default()
    }
}

impl<E> BackendSelector<E> for QuickestNumbered
where
    E: MainEntity,
{
    type BE = LoadedIdMap<NET<E>>;
}

impl<E> BackendSelector<E> for QuickMap
where
    E: FixWriteSizeEntity + MappableEntity,
{
    type BE = HashMap<<E as MappableEntity>::KeyType, E::T>;
}

impl<E> BackendSelector<E> for QuickestBox
where
    E: CompactEntity,
{
    type BE = Box<[E::T]>;
}

impl<E> BackendSelector<E> for MmapBox
where
    E: FixWriteSizeEntity,
{
    type BE = MmapSlice<E::T>;
}

impl<E> BackendSelector<E> for QuickestVBox
where
    E: CompactEntity,
{
    type BE = VarBox<E::T>;
}

impl<E> BackendSelector<E> for QuickAttPair
where
    E: CompactEntity + VariableSizeAttribute,
    E::T: VarSizedAttributeElement,
{
    type BE = VattArrPair<E>;
}

impl<E> BackendSelector<E> for VarFile
where
    E: CompactEntity + VariableSizeAttribute,
    E::T: VarSizedAttributeElement,
{
    type BE = VattReadingMap<E>;
}

impl<E> BackendSelector<E> for ReadIter
where
    E: Entity + VariableSizeAttribute,
    <E as Entity>::T: VarSizedAttributeElement,
{
    type BE = VarAttIterator<E>;
}

impl<E> BackendSelector<E> for ReadFixIter
where
    E: FixWriteSizeEntity,
{
    type BE = FixAttIterator<E>;
}

impl<E> BackendSelector<E> for IterCompactElement
where
    E: CompactEntity,
{
    type BE = Range<E::T>;
}

impl<E> WorkLoader for E
where
    E: MarkedAttribute<MainWorkMarker>,
    MAA<Self, MainWorkMarker>: CompactEntity + VariableSizeAttribute + NamespacedEntity,
    ET<MAA<Self, MainWorkMarker>>: VarSizedAttributeElement,
{
}

impl<T> Entity for EmptyAttributeEntity<T> {
    const NAME: &str = "nothing";
    const N: usize = 0;
    type T = T;
}

impl<T> VariableSizeAttribute for EmptyAttributeEntity<T>
where
    T: VarSizedAttributeElement,
{
    type SizeType = u8;
    type LocType = u8;
}

impl<T> MappableEntity for EmptyAttributeEntity<T> {
    type KeyType = usize;
}

pub fn oa_id_parse_res(id: &str) -> Result<BigId, ParseIntError> {
    id[(ID_PREFIX.len() + 1)..].parse::<u64>()
}

pub fn oa_id_parse_opt(id: &str) -> Option<BigId> {
    match oa_id_parse_res(id) {
        Ok(i) => Some(i),
        Err(_) => None,
    }
}

pub fn oa_id_parse(id: &str) -> BigId {
    oa_id_parse_res(id).expect(id)
}

pub fn field_id_parse(id: &str) -> u64 {
    id.split("/").last().unwrap().parse::<u64>().expect(id)
}

fn get_compressed_buf<P>(
    file_name: P,
) -> io::Result<BufReader<zstd::Decoder<'static, BufReader<File>>>>
where
    P: AsRef<Path>,
{
    Ok(BufReader::new(zstd::Decoder::new(File::open(file_name)?)?))
}

pub fn read_buf_path<T, P>(fp: P) -> Result<T, bincode::Error>
where
    T: DeserializeOwned,
    P: AsRef<Path>,
{
    let mut buf = get_compressed_buf(fp)?;
    bincode::deserialize_from(&mut buf)
}

pub fn write_buf_path<T, P>(obj: T, fp: P) -> Result<(), io::Error>
where
    T: Serialize,
    P: AsRef<Path> + Debug,
{
    let enc = zstd::Encoder::new(BufWriter::new(File::create(&fp)?), 3)?.auto_finish();
    let mut bufw = BufWriter::new(enc);
    bincode::serialize_into(&mut bufw, &obj).map_err(|e| io::Error::new(io::ErrorKind::Other, e))
}

pub fn read_json_path<T, P>(fp: P) -> Result<T, io::Error>
where
    T: DeserializeOwned,
    P: AsRef<Path>,
{
    let mut buf = get_compressed_buf(fp)?;
    match serde_json::from_reader(&mut buf) {
        Ok(br) => Ok(br),
        Err(_e) => Err(io::Error::from_raw_os_error(22)),
    }
}

pub fn short_string_to_u64(input: &str) -> BigId {
    let mut padded_input = [0u8; 8];
    let l = input.len().min(8);
    padded_input[..l].copy_from_slice(&input.as_bytes()[..l]);
    BigId::from_le_bytes(padded_input)
}

pub fn init_empty_slice<E: Entity, T: Default>() -> Box<[T]> {
    (0..E::N + 1)
        .map(|_| T::default())
        .collect::<Vec<T>>()
        .into()
}

pub fn code_path(suffix: &str) -> String {
    //TODO: this WET knows gen path :(
    format!("rankless_rs/src/gen/{}.rs", suffix)
}

pub fn reverse_id<E>(stowage: &Stowage) -> Box<[BigId]>
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn buf_path_roundtrip() {
        let path = "/tmp/test-buf-path-roundtrip.zst";
        let data: Vec<u64> = vec![1, 2, 3, 42, u64::MAX];
        write_buf_path(data.clone(), path).unwrap();
        let loaded: Vec<u64> = read_buf_path(path).unwrap();
        assert_eq!(data, loaded);
        fs::remove_file(path).unwrap();
    }
}
