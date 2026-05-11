use csv::Writer;
use flate2::read::GzDecoder;
use serde::{de::DeserializeOwned, Deserialize};
use std::fs::{create_dir_all, read_dir, File};
use std::io::{self, BufRead, BufReader, BufWriter};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;

use crate::common::Stowage;
use crate::oa_structs::{
    Ancestor, AssociatedInstitution, Author, Authorship, Biblio, Concept, Field, FieldLike, Geo,
    IdCountDecorated, IdTrait, Institution, Location, OpenAccess, Positioned, Publisher,
    RelatedConcept, Source, SubField, SummaryStats, Topic, Work, WorkTopic,
};

const MAX_PARTITION_ROWS: usize = 5_000_000;
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
    Concept - concepts; ancestors => Ancestor & related_concepts => RelatedConcept;;,
    Institution - institutions; associated_institution => AssociatedInstitution; geo -> Geo;,
    Work - works;
    topics => WorkTopic &
    locations => Location &
    authorships => Authorship;
    biblio -> Biblio &
    open_access -> OpenAccess;
    referenced_works
);

fn get_writer(root: &Path, fname: &str, part: u32) -> io::Result<ZstWriter> {
    let path = root.join(format!("{}.{PART_PREFIX}{part:04}{CSV_EXTENSION}", fname));
    let enc: Box<dyn io::Write + Send> =
        Box::new(zstd::Encoder::new(BufWriter::new(File::create(path)?), 3)?.auto_finish());
    Ok(Writer::from_writer(enc))
}

fn fill_with_files(path: &Path, v: &mut Vec<PathBuf>, extension: &str) -> io::Result<()> {
    if path.is_dir() {
        for entry in read_dir(path)? {
            let sub_path = entry?.path();
            fill_with_files(&sub_path, v, extension)?;
        }
    } else if let Some(ext) = path.extension() {
        if ext == extension {
            v.push(path.to_path_buf());
        }
    }
    Ok(())
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
    let mut gz_files: Vec<PathBuf> = vec![];
    fill_with_files(&in_root.join(slug), &mut gz_files, "gz")?;

    let n = std::thread::available_parallelism()
        .unwrap()
        .get()
        .min(gz_files.len().max(1));
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
        concepts,
        works,
        authors,
        publishers,
        sources
    );
    Ok(())
}
