use std::{
    collections::VecDeque,
    fs::{read_dir, File},
    io::BufReader,
    path::{Path, PathBuf},
    sync::Arc,
};

use csv::{DeserializeRecordsIntoIter, ReaderBuilder};
use dmove::para::map_reduce;
use serde::de::DeserializeOwned;

use crate::csv_writers::{CSV_EXTENSION, PART_PREFIX};

type StowInner = BufReader<zstd::Decoder<'static, BufReader<File>>>;

pub struct ObjIter<T>
where
    T: DeserializeOwned,
{
    current: Option<DeserializeRecordsIntoIter<StowInner, T>>,
    remaining: VecDeque<PathBuf>,
    label: String,
}

impl<T: DeserializeOwned> ObjIter<T> {
    pub fn from_dir(root: &Path, main_path: &str, sub_path: &str) -> Self {
        let paths = part_paths(root, main_path, sub_path);
        ObjIter {
            current: None,
            remaining: paths.into(),
            label: format!("{main_path}/{sub_path}"),
        }
    }
}

impl<T: DeserializeOwned> Iterator for ObjIter<T> {
    type Item = T;

    fn next(&mut self) -> Option<T> {
        loop {
            if let Some(r) = &mut self.current {
                if let Some(rec) = r.next() {
                    return Some(rec.expect(&format!("csv deser error in {}", self.label)));
                }
            }
            let path = self.remaining.pop_front()?;
            let dec = zstd::Decoder::new(File::open(&path).unwrap()).unwrap();
            self.current = Some(
                ReaderBuilder::new()
                    .from_reader(BufReader::new(dec))
                    .into_deserialize(),
            );
        }
    }
}

/// Each partition is processed in its own thread (map), producing a local `Acc`.
/// All threads complete before any merging happens, avoiding per-record synchronization.
pub(crate) fn par_reduce<T, Acc, MapFn, ReduceFn>(
    root: &Path,
    main_path: &str,
    sub_path: &str,
    inner_fn: MapFn,
    reduce_fn: ReduceFn,
    n_threads: Option<usize>,
) -> Acc
where
    T: DeserializeOwned + Send,
    Acc: Default + Send + 'static,
    MapFn: Fn(&mut Acc, T) + Send + Sync + 'static,
    ReduceFn: FnMut(&mut Acc, Acc) + Send + Sync + Copy + 'static,
{
    let paths = part_paths(root, main_path, sub_path);
    let inner_fn = Arc::new(inner_fn);
    let acc_from_path = move |acc: &mut Acc, path: PathBuf| {
        let dec = zstd::Decoder::new(File::open(&path).unwrap()).unwrap();
        for rec in ReaderBuilder::new()
            .from_reader(BufReader::new(dec))
            .into_deserialize::<T>()
        {
            inner_fn(acc, rec.expect("csv deser error"));
        }
    };
    map_reduce(
        paths.into_iter(),
        move |a, s| acc_from_path(a, s),
        reduce_fn,
        n_threads,
    )
}

fn part_paths(root: &Path, main_path: &str, sub_path: &str) -> Vec<PathBuf> {
    let dir = root.join(main_path);
    let prefix = format!("{}.{PART_PREFIX}", sub_path);
    let mut paths: Vec<PathBuf> = read_dir(&dir)
        .unwrap_or_else(|_| panic!("{main_path}/{sub_path} dir missing"))
        .filter_map(|e| e.ok().map(|e| e.path()))
        .filter(|p| {
            p.file_name()
                .and_then(|n| n.to_str())
                .map(|n| n.starts_with(&prefix) && n.ends_with(CSV_EXTENSION))
                .unwrap_or(false)
        })
        .collect();
    assert!(
        !paths.is_empty(),
        "no partitions found for {main_path}/{sub_path}"
    );
    paths.sort();
    paths
}
