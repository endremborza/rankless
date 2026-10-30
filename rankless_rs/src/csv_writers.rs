use csv::Writer;
use flate2::read::GzDecoder;
use serde::{de::DeserializeOwned, Deserialize};
use std::fs::{create_dir_all, read_dir, remove_file, File};
use std::io::{self, BufRead, BufReader, BufWriter};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;

use crate::common::Stowage;
use crate::oa_structs::{
    AssociatedInstitution, Author, Authorship, Biblio, Field, FieldLike, Geo, IdCountDecorated,
    IdTrait, Institution, Location, OpenAccess, Positioned, Publisher, Source, SubField,
    SummaryStats, Topic, Work, WorkTopic,
};

const MAX_PARTITION_ROWS: usize = 2_000_000;
pub const CSV_EXTENSION: &str = ".csv.zst";
pub const PART_PREFIX: &str = "part-";

type ZstWriter = Writer<Box<dyn io::Write + Send>>;

macro_rules! sub_write {
    ($parent:ident, $writer_name:ident, $field_name: ident) => {
        let parent_id = $parent.get_id();
        if let Some(ref mut child) = $parent.$field_name {
            child.parent_id = Some(parent_id.clone());
            $writer_name.serialize(child).unwrap();
        }
    };
}
macro_rules! sub_multi_write {
    ($parent:ident, $writer_name:ident, $field_name: ident) => {
        let parent_id = $parent.get_id();
        if let Some(children) = &mut $parent.$field_name {
            for (i, record) in children.iter_mut().enumerate() {
                record.parent_id = Some(parent_id.clone());
                record.set_position(i);
                $writer_name.serialize(record).unwrap();
            }
        }
    };
}
macro_rules! create_csv_struct {
    ($struct_name:ident, $($rest:ident),*) => {
        pub struct $struct_name {
            out_dir: PathBuf,
            counter: Arc<AtomicU32>,
            row_count: usize,
            $($rest: ZstWriter),*
        }

        impl $struct_name {
            const TABLES: &'static [&'static str] = &[$(stringify!($rest)),*];

            pub fn new(out_dir: PathBuf, counter: Arc<AtomicU32>) -> Self {
                let part = counter.fetch_add(1, Ordering::Relaxed);
                $( let $rest = get_writer(&out_dir, stringify!($rest), part).unwrap(); )*
                Self { out_dir, counter, row_count: 0, $($rest),* }
            }

            fn rotate(&mut self) {
                let part = self.counter.fetch_add(1, Ordering::Relaxed);
                self.row_count = 0;
                $( self.$rest = get_writer(&self.out_dir, stringify!($rest), part).unwrap(); )*
            }
        }
    };
}

trait LineWriter: Send {
    fn write_line(&mut self, line: &str);
}

macro_rules! create_complex_writers {
    ($($t_name: ident - $mod_name: ident; $($rest_key:ident => $rest_value: ident)&*; $($rest_single_key:ident -> $rest_single_value: ident)&*; $($rest_inner_key: ident)&*),*) => {

        $(pub mod $mod_name {

            use super::*;

            #[allow(dead_code)]
            pub const C: &str = stringify!($mod_name);

            #[allow(dead_code, non_upper_case_globals)]
            pub mod atts {
                $(pub const $rest_key: &str = stringify!($rest_key);)*
                $(pub const $rest_single_key: &str = stringify!($rest_single_key);)*
                $(pub const $rest_inner_key: &str = stringify!($rest_inner_key);)*
            }

            #[derive(Deserialize, Debug)]
            pub struct Decorated {
                #[serde(flatten)]
                child: IdCountDecorated<$t_name>,
                $( $rest_key: Option<Vec<$rest_value>>, )*
                $( $rest_single_key: Option<$rest_single_value>, )*
            }

            impl IdTrait for Decorated
            {
                fn get_id(&self) -> String {
                    self.child.get_id()
                }
            }

            create_csv_struct!(ModWriter, main, ids, counts $(, $rest_key)* $(, $rest_single_key)* $(, $rest_inner_key)*);

            impl LineWriter for ModWriter {
                fn write_line(&mut self, line: &str) {
                    #[allow(unused_mut)]
                    let mut outer: Decorated = deserialize_verbose(line);
                    if outer.get_id() == String::new() { return }

                    $(let $rest_key = &mut self.$rest_key;)*
                    $(sub_multi_write!(outer, $rest_key, $rest_key);)*

                    $(let $rest_single_key = &mut self.$rest_single_key;)*
                    $(sub_write!(outer, $rest_single_key, $rest_single_key);)*

                    let mut parent: IdCountDecorated<$t_name> = outer.child;

                    $(let $rest_inner_key = &mut self.$rest_inner_key;)*
                    let _child = &mut parent.child;
                    $(sub_multi_write!(_child, $rest_inner_key, $rest_inner_key);)*

                    let id_writer = &mut self.ids;
                    let cb_writer = &mut self.counts;
                    sub_write!(parent, id_writer, ids);
                    sub_multi_write!(parent, cb_writer, counts_by_year);
                    self.main.serialize(parent.child).unwrap();

                    self.row_count += 1;
                    if self.row_count >= MAX_PARTITION_ROWS {
                        self.rotate();
                    }
                }
            }

            pub fn write(in_root_str: &str, out_root_str: &str) -> io::Result<()> {
                let slug = stringify!($mod_name);
                let out_dir = Path::new(out_root_str).join(slug);
                create_dir_all(&out_dir)?;
                remove_parts(&out_dir, ModWriter::TABLES)?;
                write_entity_parallel(
                    Path::new(in_root_str),
                    slug,
                    |counter| ModWriter::new(out_dir.clone(), counter),
                )
            }
        })*
    };
}
macro_rules! macwrite {
    ($inp:ident, $outp:ident, $($modname:ident),*) => {
        $(
            $modname::write($inp, $outp)?;
        )*
    };
}

create_complex_writers!(
    Source - sources;;;,
    Publisher - publishers;;;,
    Author - authors;; summary_stats -> SummaryStats;,
    Topic - topics;;;,
    Field - fields;;;,
    FieldLike - domains;;;,
    SubField - subfields;;;,
    Institution - institutions; associated_institution => AssociatedInstitution; geo -> Geo;,
    Work - works;
    topics => WorkTopic &
    locations => Location &
    authorships => Authorship;
    biblio -> Biblio &
    open_access -> OpenAccess;
    referenced_works
);

/// The part files of `table` in `dir`, in directory order.
pub fn table_parts(dir: &Path, table: &str) -> io::Result<Vec<PathBuf>> {
    let prefix = format!("{table}.{PART_PREFIX}");
    let mut parts = Vec::new();
    for entry in read_dir(dir)? {
        let path = entry?.path();
        let named = path.file_name().and_then(|n| n.to_str());
        if named.is_some_and(|n| n.starts_with(&prefix) && n.ends_with(CSV_EXTENSION)) {
            parts.push(path);
        }
    }
    Ok(parts)
}

fn get_writer(root: &Path, fname: &str, part: u32) -> io::Result<ZstWriter> {
    let path = root.join(format!("{}.{PART_PREFIX}{part:04}{CSV_EXTENSION}", fname));
    let enc: Box<dyn io::Write + Send> =
        Box::new(zstd::Encoder::new(BufWriter::new(File::create(path)?), 3)?.auto_finish());
    Ok(Writer::from_writer(enc))
}

/// Readers take every part of a table in the directory, so parts a previous run wrote beyond this
/// run's count would be read as records; tables other writers keep there (`extend_csvs`) stay.
fn remove_parts(out_dir: &Path, tables: &[&str]) -> io::Result<()> {
    for table in tables {
        for part in table_parts(out_dir, table)? {
            remove_file(part)?;
        }
    }
    Ok(())
}

/// The gz parts inside the entity's `updated_date=…` partition dirs; files beside the partitions
/// (`manifest.json`, the `deleted_ids.csv.gz` CSV) are not records.
fn partition_parts(entity_dir: &Path) -> io::Result<Vec<PathBuf>> {
    let mut parts = vec![];
    if !entity_dir.is_dir() {
        return Ok(parts);
    }
    for partition in read_dir(entity_dir)? {
        let partition = partition?.path();
        if !partition.is_dir() {
            continue;
        }
        for part in read_dir(&partition)? {
            let part = part?.path();
            if part.extension().is_some_and(|ext| ext == "gz") {
                parts.push(part);
            }
        }
    }
    Ok(parts)
}

fn deserialize_verbose<T: DeserializeOwned>(s: &str) -> T {
    let deserializer = &mut serde_json::Deserializer::from_str(s);
    let result: Result<T, _> = serde_path_to_error::deserialize(deserializer);
    match result {
        Ok(r) => return r,
        Err(err) => {
            println!("err: {:?}", err);
            println!("s: {}", s);
            panic!("verbose err: {}", err);
        }
    }
}

fn write_entity_parallel<W, F>(in_root: &Path, slug: &str, make_writer: F) -> io::Result<()>
where
    W: LineWriter,
    F: Fn(Arc<AtomicU32>) -> W + Sync,
{
    let entity_dir = in_root.join(slug);
    let gz_files = partition_parts(&entity_dir)?;
    if gz_files.is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::NotFound,
            format!("no .gz input under {}", entity_dir.display()),
        ));
    }

    let n = std::thread::available_parallelism()
        .unwrap()
        .get()
        .min(gz_files.len());
    let counter = Arc::new(AtomicU32::new(0));

    std::thread::scope(|s| {
        let make_writer = &make_writer;
        let handles: Vec<_> = (0..n)
            .map(|i| {
                let files_of_writer: Vec<_> = gz_files
                    .iter()
                    .enumerate()
                    .filter(|(j, _)| j % n == i)
                    .map(|(_, p)| p.clone())
                    .collect();
                let counter = Arc::clone(&counter);
                s.spawn(move || -> io::Result<()> {
                    let mut writer = make_writer(counter);
                    for path in files_of_writer {
                        let decoder = GzDecoder::new(File::open(&path)?);
                        for line in BufReader::new(decoder).lines() {
                            writer.write_line(&line?);
                        }
                    }
                    Ok(())
                })
            })
            .collect();
        for h in handles {
            h.join().unwrap()?;
        }
        Ok(())
    })
}

pub fn write_csvs(in_root_str: &str, stowage: &Stowage) -> io::Result<()> {
    let out_root_str = &stowage.get_out_csv_path();
    macwrite!(
        in_root_str,
        out_root_str,
        fields,
        domains,
        subfields,
        topics,
        institutions,
        works,
        authors,
        publishers,
        sources
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use flate2::{write::GzEncoder, Compression};
    use std::io::Write;

    #[test]
    fn a_rerun_leaves_no_part_of_the_last_run() {
        let root = std::env::temp_dir().join(format!("csv-writers-rerun-{}", std::process::id()));
        let partition = root.join("in/fields/updated_date=2026-10-14");
        create_dir_all(&partition).unwrap();
        let mut gz = GzEncoder::new(
            File::create(partition.join("part_0000.gz")).unwrap(),
            Compression::fast(),
        );
        writeln!(
            gz,
            r#"{{"id": "https://openalex.org/fields/17", "display_name": "Computer Science", "domain": {{"id": "https://openalex.org/domains/3"}}}}"#
        )
        .unwrap();
        gz.finish().unwrap();
        let out = root.join("out/fields");
        create_dir_all(&out).unwrap();
        let stale = out.join(format!("main.{PART_PREFIX}0099{CSV_EXTENSION}"));
        let kept = out.join(format!("nobel.{PART_PREFIX}0000{CSV_EXTENSION}"));
        File::create(&stale).unwrap();
        File::create(&kept).unwrap();

        fields::write(
            root.join("in").to_str().unwrap(),
            root.join("out").to_str().unwrap(),
        )
        .unwrap();

        assert!(!stale.exists());
        assert!(kept.exists());
        assert!(out
            .join(format!("main.{PART_PREFIX}0000{CSV_EXTENSION}"))
            .exists());
        std::fs::remove_dir_all(&root).unwrap();
    }
}
