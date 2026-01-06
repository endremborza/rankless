use std::any::type_name;
use std::fs::{self, File};
use std::hash::Hash;
use std::io::{BufReader, Read, Seek, SeekFrom, Write};
use std::marker::PhantomData;
use std::path::PathBuf;

use hashbrown::{HashMap, HashSet};

use crate::common::{
    get_type_name, BackendLoading, Entity, EntityMutableMapperBackend, MainBuilder, MappableEntity,
    MappableEntityTraitMeta, MetaIntegrator, UnsignedNumber,
};
use crate::{
    ByteFixArrayInterface, EntityImmutableMapperBackend, EntityImmutableRefMapperBackend,
    FixWriteSizeEntity,
};

const MAX_MAP_BUF: usize = 0x100;

pub struct UniqueMap<K, V> {
    map_path: PathBuf,
    extensions: Vec<u8>,
    extension_set: HashSet<K>,
    main_buf: [u8; MAX_MAP_BUF],
    key_size: usize,
    full_size: usize,
    p: PhantomData<V>,
}

pub struct DiscoMapEntityBuilder<K, V> {
    map: UniqueMap<K, V>,
    name: String,
}

impl<E, K> BackendLoading<E> for UniqueMap<K, E::FWT>
where
    E: FixWriteSizeEntity,
    K: ByteFixArrayInterface + Hash + Eq,
{
    fn load_backend(path: &PathBuf) -> Self {
        UniqueMap::new(path.join(E::NAME))
    }
}

impl<E, K> BackendLoading<E> for HashMap<K, E::FWT>
where
    E: FixWriteSizeEntity,
    K: ByteFixArrayInterface + Hash + Eq,
{
    fn load_backend(path: &PathBuf) -> Self {
        <UniqueMap<K, E::FWT> as BackendLoading<E>>::load_backend(path).to_map()
    }
}

impl<E, V> EntityMutableMapperBackend<E> for UniqueMap<E::KeyType, V>
where
    E: MappableEntity + FixWriteSizeEntity<FWT = V> + Entity<T = V>,
    <E as MappableEntity>::KeyType: Hash + Eq,
    E::KeyType: ByteFixArrayInterface,
    V: ByteFixArrayInterface,
{
    fn get_via_mut(&mut self, k: &E::KeyType) -> Option<E::T> {
        self.get(k)
    }
}

impl<E> EntityImmutableRefMapperBackend<E> for HashMap<E::KeyType, E::T>
where
    E: MappableEntity,
    E::KeyType: Hash + Eq,
{
    fn get_ref_via_immut(&self, k: &E::KeyType) -> Option<&E::T> {
        self.get(k)
    }
}

impl<E> EntityImmutableMapperBackend<E> for HashMap<E::KeyType, E::T>
where
    E: MappableEntity + Entity,
    <E as Entity>::T: UnsignedNumber,
    <E as MappableEntity>::KeyType: Hash + Eq,
{
    fn get_via_immut(&self, k: &E::KeyType) -> Option<E::T> {
        match self.get(k) {
            Some(v) => Some(*v),
            None => None,
        }
    }
}

impl<K, V> MetaIntegrator<(K, V)> for DiscoMapEntityBuilder<K, V>
where
    K: ByteFixArrayInterface + Eq + Hash,
    V: ByteFixArrayInterface,
    (K, V): Copy,
{
    fn setup(builder: &MainBuilder, name: &str) -> Self {
        let rfile = builder.parent_root.join(name);
        if rfile.is_file() {
            fs::remove_file(&rfile).unwrap();
        }
        let map = UniqueMap::<K, V>::new(rfile);
        Self {
            map,
            name: name.to_string(),
        }
    }

    fn add_elem(&mut self, e: &(K, V)) {
        self.map.push(*e);
    }

    fn add_elem_owned(&mut self, e: (K, V)) {
        self.map.push(e);
    }

    fn post(mut self, builder: &mut MainBuilder) {
        self.map.extend();
        let n =
            file_record_count(&File::open(self.map.map_path).unwrap(), self.map.full_size) as usize;
        let camel_name = builder.add_simple_etrait(&self.name, type_name::<V>(), n, false);
        let mappable_type = get_type_name::<K>();
        builder
            .meta_elems
            .push(MappableEntityTraitMeta::meta(&camel_name, &mappable_type));
    }
}

impl<K, V> UniqueMap<K, V>
where
    K: ByteFixArrayInterface + Hash + Eq,
    V: ByteFixArrayInterface,
{
    pub fn new<T>(id_map_path: T) -> Self
    where
        PathBuf: From<T>,
    {
        let map_path = PathBuf::from(id_map_path);
        if !map_path.is_file() {
            File::create(&map_path).unwrap();
        }
        Self {
            map_path,
            extensions: vec![],
            extension_set: HashSet::new(),
            key_size: K::S,
            full_size: K::S + V::S,
            main_buf: [0; MAX_MAP_BUF],
            p: PhantomData,
        }
    }

    pub fn extend(&mut self) {
        let mut full_record_vec: Vec<u8> = Vec::new();
        let mut record_buffer = &mut self.main_buf[..self.full_size];
        let mut br = BufReader::new(File::open(&self.map_path).unwrap());
        loop {
            if let Ok(_) = br.read_exact(&mut record_buffer) {
                full_record_vec.extend(record_buffer.iter());
            } else {
                break;
            }
        }
        full_record_vec.extend(&self.extensions);
        let sorted_record_vec = chunk_sort(full_record_vec, self.full_size);
        File::create(&self.map_path)
            .unwrap()
            .write(&sorted_record_vec)
            .unwrap();
    }

    pub fn push(&mut self, e: (K, V)) {
        let id = e.0;
        if let None = self.get(&id) {
            if !self.extension_set.contains(&id) {
                self.extensions.extend(id.to_fbytes());
                self.extensions.extend(e.1.to_fbytes());
                self.extension_set.insert(id);
            }
        }
    }

    pub fn get(&mut self, k: &K) -> Option<V> {
        let hfile = File::open(&self.map_path).unwrap();

        let k_arr = k.to_fbytes();
        let rec_u64: u64 = self.full_size as u64;

        let (key_buffer, value_buffer) =
            self.main_buf[..self.full_size].split_at_mut(self.key_size);
        let mut seek_blocks_l: u64 = 0;
        let mut seek_blocks_r: u64 = file_record_count(&hfile, self.full_size);
        let mut seek_mid = (seek_blocks_r + seek_blocks_l) / 2;

        let mut reader = hfile;
        // let mut reader = BufReader::new(&hfile);
        'outer: loop {
            reader.seek(SeekFrom::Start(seek_mid * rec_u64)).unwrap();
            if let Err(_e) = reader.read_exact(key_buffer) {
                break;
            }
            for i in 0..self.key_size {
                if key_buffer[i] < k_arr[i] {
                    seek_blocks_l = seek_mid + 1;
                    break;
                } else if key_buffer[i] > k_arr[i] {
                    if seek_mid == 0 {
                        break 'outer;
                    }
                    seek_blocks_r = seek_mid - 1;
                    break;
                } else if i == (self.key_size - 1) {
                    reader.read_exact(value_buffer).unwrap();
                    return Some(V::from_fbytes(value_buffer));
                }
            }
            if seek_blocks_l > seek_blocks_r {
                break;
            } else {
                seek_mid = (seek_blocks_r + seek_blocks_l) / 2;
            }
        }
        None
    }

    pub fn to_map(&mut self) -> HashMap<K, V> {
        let mut record_buffer = &mut self.main_buf[..self.full_size];
        let mut br = BufReader::new(File::open(&self.map_path).unwrap());
        let mut out = HashMap::new();
        loop {
            if let Ok(_) = br.read_exact(&mut record_buffer) {
                let (karr, varr) = record_buffer.split_at(self.key_size);
                out.insert(K::from_fbytes(karr), V::from_fbytes(varr));
            } else {
                break;
            }
        }
        out
    }
}

pub fn chunk_sort(a: Vec<u8>, size: usize) -> Vec<u8> {
    let n = a.len();
    if n == 0 {
        return a;
    }
    let ok = n % size == 0;
    assert!(ok, "n must be a multiple of size ({n} % {size} != 0)");
    let k = n / size;
    let mut idxs: Vec<usize> = (0..k).map(|i| i * size).collect();
    idxs.sort_by(|&i, &j| a[i..i + size].cmp(&a[j..j + size]));

    let mut out = Vec::with_capacity(n);
    let mut last_chunk: Option<&[u8]> = None;
    for off in idxs {
        let chunk = &a[off..off + size];
        let should_write = match last_chunk {
            None => true,
            Some(prev) => prev != chunk,
        };
        if should_write {
            out.extend_from_slice(chunk);
            last_chunk = Some(chunk);
        }
    }
    out
}

fn file_record_count(file: &File, record_size: usize) -> u64 {
    file.metadata().unwrap().len() / (record_size as u64)
}

#[cfg(test)]
mod chunk_test {
    use super::chunk_sort;

    #[test]
    fn ch_srt() {
        let a: Vec<u8> = vec![0, 1, 3, 10, 2, 5, 1, 20];
        let sorted = chunk_sort(a, 2);
        assert_eq!(sorted, vec![0, 1, 1, 20, 2, 5, 3, 10]);
    }

    #[test]
    fn ch_srt_eq() {
        let a: Vec<u8> = vec![0, 1, 0, 1];
        let sorted = chunk_sort(a, 2);
        assert_eq!(sorted, vec![0, 1]);
    }

    #[test]
    fn test_merge_simple_equiv() {
        let a: Vec<u8> = vec![1, 1, 2, 2];
        let sorted = chunk_sort(a, 2);
        assert_eq!(sorted, vec![1, 1, 2, 2]);
    }

    #[test]
    fn test_chunk_sort_in_place_simple() {
        let data = vec![3, 3, 1, 1, 2, 2];
        let sorted = chunk_sort(data, 2);
        assert_eq!(sorted, vec![1, 1, 2, 2, 3, 3]);
    }

    #[test]
    fn test_chunk_sort_wrapper() {
        let data = vec![9, 9, 8, 8, 7, 7, 6, 6, 5, 5];
        let sorted = chunk_sort(data, 2);
        assert_eq!(sorted, vec![5, 5, 6, 6, 7, 7, 8, 8, 9, 9]);
    }

    #[test]
    fn test_dedup_equal_chunks() {
        let data = vec![1, 1, 1, 1, 1, 1];
        let sorted = chunk_sort(data, 2);
        assert_eq!(sorted, vec![1, 1]);
    }
}

#[cfg(test)]
mod map_test {
    use std::{
        fs::{create_dir_all, remove_dir_all, remove_file},
        path::PathBuf,
        str::FromStr,
    };

    use hashbrown::HashMap;
    use rand::{rngs::StdRng, Rng, SeedableRng};

    use crate::UniqueMap;

    #[test]
    fn test_unique_map() {
        let mut rng = StdRng::seed_from_u64(42);
        let path = PathBuf::from_str("/tmp/dm-map-test/map-blob").unwrap();
        remove_file(&path).unwrap_or(());
        create_dir_all(&path.parent().unwrap()).unwrap();
        let mut map = UniqueMap::<u32, u16>::new(&path);
        let mut cmp_map: HashMap<u32, u16> = HashMap::new();
        (0..200_000).for_each(|_| {
            let tup = (rng.gen(), rng.gen());
            map.push(tup.clone());
            if !cmp_map.contains_key(&tup.0) {
                cmp_map.insert(tup.0, tup.1);
            }
        });
        map.extend();

        let now = std::time::Instant::now();

        for (k, v) in cmp_map.iter() {
            assert_eq!(*v, map.get(k).unwrap());
        }

        println!("got in {}", now.elapsed().as_millis());
        assert_eq!(cmp_map, map.to_map());

        remove_dir_all(path.parent().unwrap()).unwrap();
    }
}
