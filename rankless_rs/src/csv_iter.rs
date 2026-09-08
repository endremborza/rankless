use std::{
    collections::VecDeque,
    fs::{read_dir, File},
    io::BufReader,
    marker::PhantomData,
    path::{Path, PathBuf},
    sync::Arc,
};

use csv::{Reader, ReaderBuilder, StringRecord};
use dmove::{para::map_reduce, BigId};
use hashbrown::HashMap;
use serde::de::DeserializeOwned;

use crate::{
    common::{oa_id_parse_opt, Stowage, MAIN_NAME},
    csv_writers::{authors, works, CSV_EXTENSION, PART_PREFIX},
    user_ledger::ResolvedLedger,
};

type StowInner = BufReader<zstd::Decoder<'static, BufReader<File>>>;

pub struct ObjIter<T>
where
    T: DeserializeOwned,
{
    current: Option<PartReader>,
    remaining: VecDeque<PathBuf>,
    table: Table,
    ledger: Option<Arc<ResolvedLedger>>,
    item: PhantomData<fn() -> T>,
}

/// One entity CSV table, `<main>/<sub>.part-*.csv.zst`.
struct Table {
    main: String,
    sub: String,
}

/// One partition; when the stowage carries a ledger and the table has ledger-bearing
/// columns, every row passes through the `Lens` before it is deserialized.
struct PartReader {
    rdr: Reader<StowInner>,
    headers: StringRecord,
    rec: StringRecord,
    lens: Option<Lens>,
    label: String,
}

/// The ledger applied at the read point, so every consumer sees a snapshot in which a
/// merged id is its keep id and drop-side main rows and disowned authorships do not
/// exist. Column roles come from the table's header, resolved once per partition.
struct Lens {
    ledger: Arc<ResolvedLedger>,
    /// (column, alias table): merged ids read as their keep id
    aliased: Vec<(usize, Ids)>,
    /// main-table id column: a merge drop side has no row
    dropped: Option<(usize, Ids)>,
    /// (author column, work column) of the authorships table: a disowned edge has no row
    edge: Option<(usize, usize)>,
}

#[derive(Clone, Copy)]
enum Ids {
    Authors,
    Works,
}

impl<T: DeserializeOwned> ObjIter<T> {
    pub fn new(stowage: &Stowage, main_path: &str, sub_path: &str) -> Self {
        let table = Table::new(main_path, sub_path);
        let paths = part_paths(&stowage.paths.entity_csvs, &table);
        ObjIter {
            current: None,
            remaining: paths.into(),
            table,
            ledger: stowage.ledger.clone(),
            item: PhantomData,
        }
    }
}

impl Table {
    fn new(main: &str, sub: &str) -> Self {
        Self {
            main: main.to_string(),
            sub: sub.to_string(),
        }
    }

    fn label(&self) -> String {
        format!("{}/{}", self.main, self.sub)
    }
}

impl PartReader {
    fn open(path: &Path, table: &Table, ledger: Option<&Arc<ResolvedLedger>>) -> Self {
        let label = table.label();
        let dec = zstd::Decoder::new(File::open(path).unwrap()).unwrap();
        let mut rdr = ReaderBuilder::new().from_reader(BufReader::new(dec));
        let headers = rdr
            .headers()
            .unwrap_or_else(|e| panic!("csv header error in {label}: {e}"))
            .clone();
        let lens = ledger.and_then(|l| Lens::new(l, table, &headers));
        Self {
            rdr,
            headers,
            rec: StringRecord::new(),
            lens,
            label,
        }
    }

    fn next<T: DeserializeOwned>(&mut self) -> Option<T> {
        loop {
            match self.rdr.read_record(&mut self.rec) {
                Ok(true) => {}
                Ok(false) => return None,
                Err(e) => panic!("csv read error in {}: {e}", self.label),
            }
            if let Some(lens) = &self.lens {
                if !lens.keeps(&mut self.rec) {
                    continue;
                }
            }
            return Some(
                self.rec
                    .deserialize(Some(&self.headers))
                    .unwrap_or_else(|e| panic!("csv deser error in {}: {e}", self.label)),
            );
        }
    }
}

impl Lens {
    fn new(ledger: &Arc<ResolvedLedger>, table: &Table, headers: &StringRecord) -> Option<Self> {
        if ledger.is_empty() || headers.is_empty() {
            return None;
        }
        let col = |name: &str| {
            headers
                .iter()
                .position(|h| h == name)
                .unwrap_or_else(|| panic!("{}: no `{name}` column", table.label()))
        };
        let has = |ids: Ids| match ids {
            Ids::Authors => !ledger.author_aliases.is_empty(),
            Ids::Works => !ledger.work_aliases.is_empty(),
        };
        let (mut aliased, mut dropped, mut edge) = (Vec::new(), None, None);
        match (table.main.as_str(), table.sub.as_str()) {
            (works::C, MAIN_NAME) => dropped = Some((col("id"), Ids::Works)),
            (authors::C, MAIN_NAME) => dropped = Some((col("id"), Ids::Authors)),
            (works::C, works::atts::authorships) => {
                let (work, author) = (col("parent_id"), col("author"));
                aliased = vec![(work, Ids::Works), (author, Ids::Authors)];
                if !ledger.removed_edges.is_empty() {
                    edge = Some((author, work));
                }
            }
            (works::C, works::atts::referenced_works) => {
                aliased = vec![
                    (col("parent_id"), Ids::Works),
                    (col("referenced_work_id"), Ids::Works),
                ]
            }
            (works::C, works::atts::locations) | (works::C, works::atts::topics) => {
                aliased = vec![(col("parent_id"), Ids::Works)]
            }
            _ => return None,
        }
        aliased.retain(|&(_, ids)| has(ids));
        dropped = dropped.filter(|&(_, ids)| has(ids));
        if aliased.is_empty() && dropped.is_none() && edge.is_none() {
            return None;
        }
        Some(Self {
            ledger: Arc::clone(ledger),
            aliased,
            dropped,
            edge,
        })
    }

    fn aliases(&self, ids: Ids) -> &HashMap<BigId, BigId> {
        match ids {
            Ids::Authors => &self.ledger.author_aliases,
            Ids::Works => &self.ledger.work_aliases,
        }
    }

    /// Rewrites the row in place; false when the row does not exist under the ledger.
    fn keeps(&self, rec: &mut StringRecord) -> bool {
        if let Some((c, ids)) = self.dropped {
            if let Some(id) = oa_id_parse_opt(&rec[c]) {
                if self.aliases(ids).contains_key(&id) {
                    return false;
                }
            }
        }
        let rewritten: Vec<(usize, String)> = self
            .aliased
            .iter()
            .filter_map(|&(c, ids)| {
                let root = self.aliases(ids).get(&oa_id_parse_opt(&rec[c])?)?;
                Some((c, with_id(&rec[c], *root)))
            })
            .collect();
        if !rewritten.is_empty() {
            let mut fields: Vec<String> = rec.iter().map(str::to_owned).collect();
            for (c, s) in rewritten {
                fields[c] = s;
            }
            *rec = StringRecord::from(fields);
        }
        if let Some((ac, wc)) = self.edge {
            if let (Some(a), Some(w)) = (oa_id_parse_opt(&rec[ac]), oa_id_parse_opt(&rec[wc])) {
                if self.ledger.removed_edges.contains(&(a, w)) {
                    return false;
                }
            }
        }
        true
    }
}

impl<T: DeserializeOwned> Iterator for ObjIter<T> {
    type Item = T;

    fn next(&mut self) -> Option<T> {
        loop {
            if let Some(part) = &mut self.current {
                if let Some(rec) = part.next() {
                    return Some(rec);
                }
            }
            let path = self.remaining.pop_front()?;
            self.current = Some(PartReader::open(&path, &self.table, self.ledger.as_ref()));
        }
    }
}

/// Each partition is processed in its own thread (map), producing a local `Acc`.
/// All threads complete before any merging happens, avoiding per-record synchronization.
pub(crate) fn par_reduce<T, Acc, MapFn, ReduceFn>(
    stowage: &Stowage,
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
    let table = Table::new(main_path, sub_path);
    let paths = part_paths(&stowage.paths.entity_csvs, &table);
    let ledger = stowage.ledger.clone();
    let inner_fn = Arc::new(inner_fn);
    let acc_from_path = move |acc: &mut Acc, path: PathBuf| {
        let mut part = PartReader::open(&path, &table, ledger.as_ref());
        while let Some(rec) = part.next::<T>() {
            inner_fn(acc, rec);
        }
    };
    map_reduce(paths.into_iter(), acc_from_path, reduce_fn, n_threads)
}

/// The id string with its numeric tail replaced, whatever prefix the column carries.
fn with_id(field: &str, id: BigId) -> String {
    let cut = field
        .rfind(|c: char| !c.is_ascii_digit())
        .map_or(0, |p| p + 1);
    format!("{}{id}", &field[..cut])
}

fn part_paths(root: &Path, table: &Table) -> Vec<PathBuf> {
    let dir = root.join(&table.main);
    let prefix = format!("{}.{PART_PREFIX}", table.sub);
    let mut paths: Vec<PathBuf> = read_dir(&dir)
        .unwrap_or_else(|_| panic!("{} dir missing", table.label()))
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
        "no partitions found for {}",
        table.label()
    );
    paths.sort();
    paths
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn with_id_keeps_the_prefix() {
        assert_eq!(
            with_id("https://openalex.org/W12", 7),
            "https://openalex.org/W7"
        );
        assert_eq!(with_id("A1", 22), "A22");
        assert_eq!(with_id("33", 4), "4");
    }
}
