use std::{
    any::type_name,
    fs::{create_dir_all, File},
    io::{BufReader, Read, Seek, Write},
    marker::PhantomData,
    os::linux::fs::MetadataExt,
    path::PathBuf,
    sync::Arc,
};

use crate::{
    common::{
        downcast_fun, get_type_name, BackendLoading, ByteArrayInterface, ByteFixArrayInterface,
        Entity, EntityImmutableRefMapperBackend, MainBuilder, MetaIntegrator, UnsignedNumber,
        VariableSizeAttribute, VariableSizeAttributeTraitMeta, ET, MAX_BUF, MAX_NUMBUF,
    },
    CompactEntity, EntityMutableMapperBackend,
};

pub type VaST<E> = <ET<E> as VarSizedAttributeElement>::SubType;

pub struct VarBox<T>(pub Box<[T]>);

pub struct VarAttBuilder {
    files: VattFilePair,
    sizes: Vec<usize>,
    max_size: usize,
    sum_elems: usize,
    name: String,
}

pub struct VattFilePair {
    counts: File,
    targets: File,
}

//TODO:
//create more efficient locators
//e.g. in locators, first few _bits_ tell where to look
//multiple arrays held for small and for larger ones
pub struct VattReadingMapGen<E, LT>
where
    LT: LocationFinder<E>,
    E: VariableSizeAttribute,
    ET<E>: VarSizedAttributeElement,
{
    file_pair: VattFilePair,
    buf: [u8; MAX_BUF],
    locators: LT,
    p: PhantomData<E>,
}

pub type VattReadingMap<E> = VattReadingMapGen<E, Locators<E>>;
pub type VattReadingRefMap<'a, E> = VattReadingMapGen<E, &'a Locators<E>>;
pub type VattReadingArcMap<E> = VattReadingMapGen<E, Arc<Locators<E>>>;

pub struct VattArrPair<E>
where
    E: VariableSizeAttribute,
    <E as Entity>::T: VarSizedAttributeElement,
{
    pub locators: Locators<E>,
    arr: Box<[VaST<E>]>,
}

pub struct VarAttIterator<E>
where
    E: VariableSizeAttribute + ?Sized,
    <E as Entity>::T: VarSizedAttributeElement,
{
    files: VattFilePair,
    size_size: usize,
    buf: [u8; MAX_BUF],
    size_buf: [u8; MAX_NUMBUF],
    p: PhantomData<E>,
}

pub struct NumberWriter<I, F>
where
    I: Iterator<Item = usize>,
    F: Write,
{
    file: F,
    numbers: I,
}

pub struct Locators<E>
where
    E: VariableSizeAttribute,
    <E as Entity>::T: VarSizedAttributeElement,
{
    divided_locs: Box<[E::LocType]>,
    pub divided_sizes: Box<[E::SizeType]>,
}

pub trait VarSizedAttributeElement: ByteArrayInterface {
    const DIVISOR: usize = 1;
    type SubType: ByteFixArrayInterface;
}

pub trait LocationFinder<E: VariableSizeAttribute>
where
    ET<E>: VarSizedAttributeElement,
{
    fn get_via_mut(&self, file_pair: &mut VattFilePair, buf: &mut [u8], k: &usize)
        -> Option<ET<E>>;
}

impl<T> From<Vec<T>> for VarBox<T> {
    fn from(value: Vec<T>) -> Self {
        Self(value.into())
    }
}

impl<T> FromIterator<T> for VarBox<T> {
    fn from_iter<I: IntoIterator<Item = T>>(iter: I) -> Self {
        let v: Vec<T> = iter.into_iter().collect();
        v.into()
    }
}

impl VattFilePair {
    fn open(parent_dir: &PathBuf) -> Self {
        let op = |s: &str| File::open(&parent_dir.join(s)).expect(&format!("{parent_dir:?}/{s}"));
        let counts = op("sizes");
        let targets = op("targets");
        Self { counts, targets }
    }

    fn create(parent_dir: &PathBuf) -> Self {
        let counts = File::create(&parent_dir.join("sizes")).unwrap();
        let targets = File::create(&parent_dir.join("targets")).unwrap();
        Self { counts, targets }
    }
}

impl<E> VarAttIterator<E>
where
    E: Entity + VariableSizeAttribute + ?Sized,
    <E as Entity>::T: VarSizedAttributeElement,
{
    fn new(parent_dir: &PathBuf) -> Self {
        let size_size = E::SizeType::S;
        let att_dir = parent_dir.join(E::NAME);
        Self {
            files: VattFilePair::open(&att_dir),
            size_size,
            buf: [0; MAX_BUF],
            size_buf: [0; MAX_NUMBUF],
            p: PhantomData,
        }
    }
}

impl<I, F> NumberWriter<I, F>
where
    I: Iterator<Item = usize>,
    F: Write,
{
    fn write<N>(mut self) -> String
    where
        N: UnsignedNumber + ByteFixArrayInterface,
    {
        for n in self.numbers {
            let buf = N::from_usize(n).to_fbytes();
            self.file.write(&buf).expect("writing number");
        }
        std::any::type_name::<N>().to_string()
    }

    pub fn write_minimal(self, max_size: usize) -> String {
        if max_size < 2_usize.pow(8) {
            self.write::<u8>()
        } else if max_size < 2_usize.pow(16) {
            self.write::<u16>()
        } else if max_size < 2_usize.pow(32) {
            self.write::<u32>()
        } else if max_size < 2_usize.pow(64) {
            self.write::<u64>()
        } else {
            self.write::<u128>()
        }
    }
}

impl<E, LT> VattReadingMapGen<E, LT>
where
    E: VariableSizeAttribute,
    E::T: VarSizedAttributeElement,
    LT: LocationFinder<E>,
{
    pub fn from_locator(locators: LT, parent: &PathBuf) -> Self {
        let file_pair = VattFilePair::open(&parent.join(E::NAME));
        Self {
            locators,
            buf: [0; MAX_BUF],
            file_pair,
            p: PhantomData,
        }
    }
}

impl<E> Locators<E>
where
    E: VariableSizeAttribute,
    E::T: VarSizedAttributeElement,
{
    fn from_file<R>(counts: &mut R) -> Self
    where
        R: Read,
    {
        let mut size_buf = [0; MAX_NUMBUF];
        let size_slice = &mut size_buf[..E::SizeType::S];
        let mut seek = 0;
        let mut locators_size = Vec::with_capacity(E::N + 1);
        let mut locators_loc = Vec::with_capacity(E::N + 1);

        while let Ok(_) = counts.read_exact(size_slice) {
            let size = E::SizeType::from_fbytes(size_slice);
            locators_size.push(size);
            locators_loc.push(E::LocType::from_usize(seek));
            seek += size.to_usize();
        }
        Self {
            divided_locs: locators_loc.into(),
            divided_sizes: locators_size.into(),
        }
    }

    pub fn empty() -> Self {
        Self {
            divided_sizes: Vec::new().into(),
            divided_locs: Vec::new().into(),
        }
    }
}

impl<E> VattArrPair<E>
where
    E: VariableSizeAttribute,
    ET<E>: VarSizedAttributeElement,
{
    const BL: usize = VaST::<E>::S;
    pub fn get(&self, k: &usize) -> Option<&[VaST<E>]> {
        if *k >= self.locators.divided_locs.len() {
            return None;
        }
        let divided_loc = self.locators.divided_locs[*k].to_usize();
        let divided_size = self.locators.divided_sizes[*k].to_usize();
        let end_i = divided_loc + divided_size;
        Some(&self.arr[divided_loc..end_i])
    }

    pub fn empty() -> Self {
        let locators = Locators {
            divided_sizes: Vec::new().into(),
            divided_locs: Vec::new().into(),
        };
        Self {
            arr: Vec::new().into(),
            locators,
        }
    }

    pub fn from_boxes(value: VarBox<Box<[VaST<E>]>>) -> Self {
        let mut arr = Vec::new();
        let mut divided_sizes = Vec::new();
        let mut divided_locs = Vec::new();
        for b in value.0 {
            divided_locs.push(E::LocType::from_usize(arr.len()));
            divided_sizes.push(E::SizeType::from_usize(b.len()));
            for e in b {
                arr.push(e);
            }
        }

        let locators = Locators {
            divided_sizes: divided_sizes.into(),
            divided_locs: divided_locs.into(),
        };
        Self {
            arr: arr.into(),
            locators,
        }
    }
}

impl VarSizedAttributeElement for String {
    type SubType = u8;
}

impl<T> VarSizedAttributeElement for Box<[T]>
where
    T: ByteFixArrayInterface,
{
    const DIVISOR: usize = T::S;
    type SubType = T;
}

impl<T> MetaIntegrator<T> for VarAttBuilder
where
    T: VarSizedAttributeElement,
{
    fn setup(builder: &MainBuilder, name: &str) -> Self {
        let att_dir = builder.parent_root.join(name);
        create_dir_all(&att_dir).unwrap();
        let files = VattFilePair::create(&att_dir);
        Self {
            files,
            sizes: Vec::new(),
            max_size: 0,
            sum_elems: 0,
            name: name.to_string(),
        }
    }

    fn add_elem(&mut self, e: &T) {
        let barr = e.to_bytes();
        self.files.targets.write(&barr).expect("target writing");
        let current_size = barr.len() / T::DIVISOR;
        if current_size > self.max_size {
            self.max_size = current_size
        }
        self.sum_elems += current_size;
        self.sizes.push(current_size);
    }
    fn post(self, builder: &mut MainBuilder) {
        //NOTE: all sizes need to fit into memory
        //if that's infeasable, sizes usize
        // let n = S::N;
        // assert_eq!(sizes.len(), n);
        let n = self.sizes.len();
        let number_writer = NumberWriter {
            file: self.files.counts,
            numbers: self.sizes.into_iter(),
        };
        let size_scale = number_writer.write_minimal(self.max_size);
        let se = self.sum_elems;
        let loc_scale = downcast_fun!(type_name, se,);
        let camel_name = builder.add_simple_etrait(&self.name, &get_type_name::<T>(), n, true);
        builder
            .meta_elems
            .push(VariableSizeAttributeTraitMeta::meta(
                &camel_name,
                &size_scale,
                &loc_scale,
            ));
    }
}

impl<E> BackendLoading<E> for VarAttIterator<E>
where
    E: VariableSizeAttribute,
    <E as Entity>::T: VarSizedAttributeElement,
{
    fn load_backend(path: &PathBuf) -> Self {
        VarAttIterator::<E>::new(path)
    }
}

impl<E> BackendLoading<E> for VarBox<E::T>
where
    E: VariableSizeAttribute,
    <E as Entity>::T: VarSizedAttributeElement,
{
    fn load_backend(path: &PathBuf) -> Self {
        VarAttIterator::<E>::new(path).collect::<Vec<E::T>>().into()
    }
}

impl<E> BackendLoading<E> for VattArrPair<E>
where
    E: VariableSizeAttribute,
    <E as Entity>::T: VarSizedAttributeElement,
{
    fn load_backend(path: &PathBuf) -> Self {
        let parent_dir = path.join(E::NAME);
        let file_pair = VattFilePair::open(&parent_dir);
        let mut count_br = BufReader::new(file_pair.counts);
        let mut target_br = BufReader::new(file_pair.targets);
        let locators = Locators::<E>::from_file(&mut count_br);
        let elem_size: usize = size_of::<<E::T as VarSizedAttributeElement>::SubType>();
        let cap_b = std::fs::metadata(parent_dir.join("targets"))
            .unwrap()
            .st_size()
            .to_usize();
        let mut v = Vec::with_capacity(cap_b / elem_size);
        let mut buf = [0; MAX_BUF];
        let bufr = &mut buf[0..Self::BL];
        while let Ok(_) = target_br.read_exact(bufr) {
            v.push(E::subtype_from_buf(bufr))
        }

        let loclsize = locators.divided_locs.len() * size_of::<E::LocType>() / 1_000_000;
        let locssize = locators.divided_sizes.len() * size_of::<E::SizeType>() / 1_000_000;
        let locsum = loclsize + locssize;
        let arrsum = v.len() * elem_size / 1_000_000;
        println!(
            "got vatt pair {} -\tlocators:{loclsize}+{locssize}={locsum}MB;\tarr:{arrsum}MB;\tsum:{}MB",
            E::NAME,
            locsum + arrsum,
        );
        Self {
            locators,
            arr: v.into(),
        }
    }
}

impl<E> BackendLoading<E> for VattReadingMap<E>
where
    E: VariableSizeAttribute,
    <E as Entity>::T: VarSizedAttributeElement,
{
    fn load_backend(path: &PathBuf) -> Self {
        let mut file_pair = VattFilePair::open(&path.join(E::NAME));
        let buf = [0; MAX_BUF];

        Self {
            locators: Locators::<E>::from_file(&mut file_pair.counts),
            file_pair,
            buf,
            p: PhantomData,
        }
    }
}

impl<E> BackendLoading<E> for Locators<E>
where
    E: VariableSizeAttribute,
    E::T: VarSizedAttributeElement,
{
    fn load_backend(path: &PathBuf) -> Self {
        let mut file_pair = VattFilePair::open(&path.join(E::NAME));
        Self::from_file(&mut file_pair.counts)
    }
}

impl<E> EntityImmutableRefMapperBackend<E> for VarBox<E::T>
where
    E: CompactEntity,
{
    fn get_ref_via_immut(&self, k: &usize) -> Option<&<E as Entity>::T> {
        Some(&self.0[*k])
    }
}

impl<E, LT> EntityMutableMapperBackend<E> for VattReadingMapGen<E, LT>
where
    E: CompactEntity + VariableSizeAttribute,
    ET<E>: VarSizedAttributeElement,
    LT: LocationFinder<E>,
{
    fn get_via_mut(&mut self, k: &usize) -> Option<<E as Entity>::T> {
        self.locators
            .get_via_mut(&mut self.file_pair, &mut self.buf, k)
    }
}

impl<E> Iterator for VarAttIterator<E>
where
    E: VariableSizeAttribute + Entity,
    <E as Entity>::T: VarSizedAttributeElement,
{
    type Item = E::T;
    fn next(&mut self) -> Option<Self::Item> {
        let size_slice = &mut self.size_buf[..self.size_size];

        if let Ok(_) = self.files.counts.read_exact(size_slice) {
            let e = from_buf::<E>(
                E::full_size_from_buf(size_slice),
                &mut self.files.targets,
                &mut self.buf,
            );
            return Some(e);
        }
        None
    }
}

impl<E> LocationFinder<E> for Locators<E>
where
    E: VariableSizeAttribute,
    ET<E>: VarSizedAttributeElement,
{
    fn get_via_mut(
        &self,
        file_pair: &mut VattFilePair,
        buf: &mut [u8],
        k: &usize,
    ) -> Option<ET<E>> {
        if *k >= self.divided_locs.len() {
            return None;
        }
        let divided_seek = &self.divided_locs[*k];
        let divided_size = &self.divided_sizes[*k];
        let full_seek = (divided_seek.to_usize() * E::T::DIVISOR) as u64;
        file_pair
            .targets
            .seek(std::io::SeekFrom::Start(full_seek))
            .expect(&format!("ran out of file for {}", E::NAME));
        Some(from_buf::<E>(
            E::full_size_from_st(*divided_size),
            &mut file_pair.targets,
            buf,
        ))
    }
}

impl<T, E> LocationFinder<E> for Arc<T>
where
    E: VariableSizeAttribute,
    ET<E>: VarSizedAttributeElement,
    T: LocationFinder<E>,
{
    fn get_via_mut(
        &self,
        file_pair: &mut VattFilePair,
        buf: &mut [u8],
        k: &usize,
    ) -> Option<ET<E>> {
        T::get_via_mut(self, file_pair, buf, k)
    }
}

impl<T> Default for VarBox<T> {
    fn default() -> Self {
        Self(Vec::new().into_boxed_slice())
    }
}

fn from_buf<E>(full_size: usize, targets: &mut File, buf: &mut [u8]) -> E::T
where
    E: Entity,
    E::T: ByteArrayInterface,
{
    if full_size <= buf.len() {
        let content_slice = &mut buf[..full_size];
        targets.read_exact(content_slice).unwrap();
        return E::T::from_bytes(content_slice);
    }
    let mut remaining_count = full_size;
    let mut bvec: Vec<u8> = Vec::new();
    while remaining_count > 0 {
        let endidx = if remaining_count > MAX_BUF {
            MAX_BUF
        } else {
            remaining_count
        };
        let content_slice = &mut buf[..endidx];
        targets.read_exact(content_slice).unwrap();
        bvec.extend(content_slice.iter());
        remaining_count -= endidx;
    }
    <E as Entity>::T::from_bytes(&bvec)
}
