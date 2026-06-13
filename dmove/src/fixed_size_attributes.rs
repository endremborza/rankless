use std::{
    fs::File,
    io::{self, BufReader, BufWriter, Read, Seek, SeekFrom, Write},
    marker::PhantomData,
    path::PathBuf,
};

use memmap2::Mmap;

use crate::{
    common::{
        get_type_name, get_uscale, ByteFixArrayInterface, Entity, MainBuilder, MappableEntity,
        MetaIntegrator, MAX_FIXBUF,
    },
    BackendLoading, CompactEntity, EntityImmutableRefMapperBackend, EntityMutableMapperBackend,
    UnsignedNumber, VarAttBuilder,
};

type DowncastablePrefixed = Box<[(bool, usize)]>;

pub struct FixAttBuilder {
    writer: BufWriter<File>,
    n: usize,
    name: String,
}

pub struct DowncastingBuilder {
    arr: Vec<usize>,
    max: usize,
    name: String,
}

pub struct DowncastingPrefixedVarBuilder {
    arr: Vec<DowncastablePrefixed>,
    max: usize,
    name: String,
}

pub struct FixAttIterator<E>
where
    E: FixWriteSizeEntity,
{
    reader: BufReader<File>,
    buf: [u8; MAX_FIXBUF],
    p: PhantomData<E>,
}

pub struct MmapSlice<V> {
    mmap: Mmap,
    _marker: PhantomData<V>,
}

pub trait FixWriteSizeEntity: Entity {
    const WS: usize;
    type FWT: ByteFixArrayInterface;
}

impl<E> FixWriteSizeEntity for E
where
    E: Entity,
    E::T: ByteFixArrayInterface,
{
    const WS: usize = E::T::S;
    type FWT = E::T;
}

impl<E> EntityMutableMapperBackend<E> for File
where
    E: Entity + MappableEntity<KeyType = usize>,
{
    fn get_via_mut(&mut self, k: &<E as MappableEntity>::KeyType) -> Option<<E as Entity>::T> {
        let pos = SeekFrom::Start(*k as u64);
        self.seek(pos).unwrap();
        todo!()
    }
}

impl<E, V> BackendLoading<E> for Box<[V]>
where
    E: FixWriteSizeEntity<FWT = V> + Entity<T = V>,
    V: ByteFixArrayInterface,
{
    fn load_backend(path: &PathBuf) -> Self {
        let mut out = Vec::with_capacity(E::N + 1);
        let fp = path.join(E::NAME);
        let mut br = BufReader::new(File::open(&fp).expect(fp.to_str().unwrap()));
        let size: usize = E::WS;
        let mut buf: [u8; MAX_FIXBUF] = [0; MAX_FIXBUF];
        while let Ok(_) = br.read_exact(&mut buf[..size]) {
            out.push(E::FWT::from_fbytes(&buf[..size]));
        }
        out.into()
    }
}

impl<E> BackendLoading<E> for FixAttIterator<E>
where
    E: FixWriteSizeEntity,
{
    fn load_backend(path: &PathBuf) -> Self {
        let full_path = path.join(E::NAME);
        let file = File::open(&full_path).expect(full_path.to_str().unwrap());
        Self {
            reader: BufReader::new(file),
            buf: [0; MAX_FIXBUF],
            p: PhantomData,
        }
    }
}

impl<V: ByteFixArrayInterface> MmapSlice<V> {
    pub fn row(&self, idx: usize) -> V {
        let start = idx * V::S;
        V::from_fbytes(&self.mmap[start..start + V::S])
    }

    pub fn len(&self) -> usize {
        self.mmap.len() / V::S
    }
}

impl<E: ByteFixArrayInterface, const AS: usize> MmapSlice<[E; AS]> {
    pub fn elem(&self, row: usize, col: usize) -> E {
        let start = (row * AS + col) * E::S;
        E::from_fbytes(&self.mmap[start..start + E::S])
    }
}

impl<E, V> BackendLoading<E> for MmapSlice<V>
where
    E: FixWriteSizeEntity<FWT = V> + Entity<T = V>,
    V: ByteFixArrayInterface,
{
    fn load_backend(path: &PathBuf) -> Self {
        let fp = path.join(E::NAME);
        let file = File::open(&fp).expect(fp.to_str().unwrap());
        let mmap = unsafe { Mmap::map(&file).expect(fp.to_str().unwrap()) };
        Self {
            mmap,
            _marker: PhantomData,
        }
    }
}

impl<T> MetaIntegrator<T> for FixAttBuilder
where
    T: ByteFixArrayInterface,
{
    fn setup(builder: &MainBuilder, name: &str) -> Self {
        assert!(T::S <= MAX_FIXBUF);
        let full_path = builder.parent_root.join(name);
        let file = File::create(&full_path).expect(full_path.to_str().unwrap());
        let writer = BufWriter::new(file);
        Self {
            n: 0,
            writer,
            name: name.to_string(),
        }
    }

    fn add_elem(&mut self, e: &T) {
        self.writer.write(&e.to_fbytes()).unwrap();
        self.n += 1;
    }
    fn post(mut self, builder: &mut MainBuilder) {
        self.writer.flush().unwrap();
        builder.add_simple_etrait(&self.name, &get_type_name::<T>(), self.n, true);
    }
}

impl MetaIntegrator<usize> for DowncastingBuilder {
    fn setup(_builder: &MainBuilder, name: &str) -> Self {
        Self {
            arr: Vec::new(),
            max: 0,
            name: name.to_string(),
        }
    }

    fn add_elem(&mut self, e: &usize) {
        if *e > self.max {
            self.max = *e;
        }
        self.arr.push(*e)
    }

    fn post(self, builder: &mut MainBuilder) {
        let n = self.max;
        let scale_name = get_uscale(n);
        builder.add_simple_etrait(&self.name, &scale_name, self.arr.len(), true);

        let name = &self.name;
        let arr = self.arr;
        crate::common::downcast_fun!(casted_write, n, name, arr, builder).unwrap();
    }
}

impl MetaIntegrator<DowncastablePrefixed> for DowncastingPrefixedVarBuilder {
    fn setup(_builder: &MainBuilder, name: &str) -> Self {
        Self {
            arr: Vec::new(),
            max: 0,
            name: name.to_string(),
        }
    }

    fn add_elem(&mut self, e: &DowncastablePrefixed) {
        for (_, sube) in e {
            if *sube > self.max {
                self.max = *sube;
            }
        }
        self.arr.push(e.clone());
    }
    fn post(self, builder: &mut MainBuilder) {
        //NOTE: everything needs to fit into memory
        let n = self.max << 1;
        let name = &self.name;
        let arr = self.arr;
        crate::common::downcast_fun!(casted_prefixer, n, name, arr, builder);
    }
}

impl<E> EntityImmutableRefMapperBackend<E> for Box<[E::T]>
where
    E: CompactEntity,
{
    fn get_ref_via_immut(&self, k: &usize) -> Option<&E::T> {
        Some(&self[*k])
    }
}

impl<E> Iterator for FixAttIterator<E>
where
    E: FixWriteSizeEntity,
    <E as Entity>::T: ByteFixArrayInterface,
{
    type Item = E::T;
    fn next(&mut self) -> Option<Self::Item> {
        let buf = &mut self.buf[..E::WS];
        if let Ok(_) = self.reader.read_exact(buf) {
            return Some(<E as Entity>::T::from_fbytes(buf));
        }
        None
    }
}

pub fn reverse_prefixed_n(prefixed_n: usize) -> (bool, usize) {
    ((prefixed_n & 1) == 1, prefixed_n >> 1)
}

fn casted_write<T>(name: &str, arr: Vec<usize>, builder: &MainBuilder) -> io::Result<()>
where
    T: UnsignedNumber,
{
    let full_path = builder.parent_root.join(name);
    let file = File::create(&full_path).expect(full_path.to_str().unwrap());
    let mut writer = BufWriter::new(file);
    for us in arr.into_iter() {
        let buf = T::from_usize(us).to_fbytes();
        writer.write(&buf)?;
    }
    writer.flush()
}

fn casted_prefixer<T>(name: &str, arr: Vec<DowncastablePrefixed>, builder: &mut MainBuilder)
where
    T: UnsignedNumber,
{
    let mut vatt_sub_builder = <VarAttBuilder as MetaIntegrator<Box<[T]>>>::setup(builder, name);
    for raw_arr in arr.into_iter() {
        let boarr: Vec<T> = raw_arr
            .into_vec()
            .into_iter()
            .map(|(b, n)| T::from_usize((n << 1) + (b as usize)))
            .collect();
        <VarAttBuilder as MetaIntegrator<Box<[T]>>>::add_elem_owned(
            &mut vatt_sub_builder,
            boarr.into_boxed_slice(),
        );
    }
    <VarAttBuilder as MetaIntegrator<Box<[T]>>>::post(vatt_sub_builder, builder)
}
