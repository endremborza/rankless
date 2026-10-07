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
    common::{oa_id_parse_opt, Stowage, ID_PREFIX, MAIN_NAME},
    csv_writers::{authors, works, CSV_EXTENSION, PART_PREFIX},
    user_ledger::ResolvedLedger,
};

/// The author column of the enrichment tables `extend_csvs` writes beside an entity's own, a
/// bare OpenAlex id.
const ENRICHMENT_ID: &str = "oa_id";

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
/// columns, every row passes through the `Lens` before it is deserialized. A table's first
/// partition ends with the rows the ledger adds to it.
struct PartReader {
    rdr: Reader<StowInner>,
    headers: StringRecord,
    rec: StringRecord,
    lens: Option<Lens>,
    added: Vec<StringRecord>,
    label: String,
}

/// The ledger applied at the read point, so every consumer sees a snapshot in which a
/// merged id is its keep id, drop-side main rows and disowned authorships do not exist, a
/// reassigned authorship names its new author, a granted authorship has a row, a stripped
/// author carries no ORCID, a keep author carries its merged records' counts and a renamed one
/// its name. Column roles come from the table's header, resolved once per partition.
struct Lens {
    ledger: Arc<ResolvedLedger>,
    /// main-table id column: a merge drop side has no row, an author row's cells may rewrite
    main_id: Option<(usize, Ids)>,
    /// authors/main: a stripped row's `orcid`, a keep row's counts, a renamed row's name
    author_cells: Option<AuthorCells>,
    /// work-id columns of a work attribute table, read as their keep id
    work_cols: Vec<usize>,
    /// the bare `oa_id` column of an author enrichment table (`extend_csvs`), read as its keep id
    enrichment_author: Option<usize>,
    ships: Option<Ships>,
}

struct AuthorCells {
    orcid: usize,
    name: usize,
    works: usize,
    cites: usize,
}

/// The authorships table: both ids read in keep space, a disowned edge has no row, a
/// reassigned one names its new author or none, a granted one has a row. An author's repeated
/// rows on a work (a merged record's beside its keep's) all pass; a2 joins their institutions.
struct Ships {
    work: usize,
    author: usize,
    position: usize,
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
    fn open(path: &Path, table: &Table, ledger: Option<&Arc<ResolvedLedger>>, first: bool) -> Self {
        let label = table.label();
        let dec = zstd::Decoder::new(File::open(path).unwrap()).unwrap();
        let mut rdr = ReaderBuilder::new().from_reader(BufReader::new(dec));
        let headers = rdr
            .headers()
            .unwrap_or_else(|e| panic!("csv header error in {label}: {e}"))
            .clone();
        let lens = ledger.and_then(|l| Lens::new(l, table, &headers));
        let added = match &lens {
            Some(lens) if first => lens.granted_rows(headers.len()),
            _ => Vec::new(),
        };
        Self {
            rdr,
            headers,
            rec: StringRecord::new(),
            lens,
            added,
            label,
        }
    }

    fn next<T: DeserializeOwned>(&mut self) -> Option<T> {
        loop {
            match self.rdr.read_record(&mut self.rec) {
                Ok(true) => {}
                Ok(false) => {
                    self.rec = self.added.pop()?;
                    break;
                }
                Err(e) => panic!("csv read error in {}: {e}", self.label),
            }
            if self.lens.as_ref().map_or(true, |l| l.keeps(&mut self.rec)) {
                break;
            }
        }
        Some(
            self.rec
                .deserialize(Some(&self.headers))
                .unwrap_or_else(|e| panic!("csv deser error in {}: {e}", self.label)),
        )
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
        let (mut main_id, mut author_cells, mut work_cols, mut ships, mut enrichment_author) =
            (None, None, Vec::new(), None, None);
        match (table.main.as_str(), table.sub.as_str()) {
            (works::C, MAIN_NAME) if has(Ids::Works) => main_id = Some((col("id"), Ids::Works)),
            (authors::C, MAIN_NAME) => {
                if !(ledger.stripped_orcids.is_empty()
                    && ledger.author_counts.is_empty()
                    && ledger.author_names.is_empty())
                {
                    author_cells = Some(AuthorCells {
                        orcid: col("orcid"),
                        name: col("display_name"),
                        works: col("works_count"),
                        cites: col("cited_by_count"),
                    });
                }
                if has(Ids::Authors) || author_cells.is_some() {
                    main_id = Some((col("id"), Ids::Authors));
                }
            }
            (works::C, works::atts::authorships)
                if has(Ids::Works)
                    || has(Ids::Authors)
                    || !ledger.removed_edges.is_empty()
                    || !ledger.reassigned.is_empty()
                    || !ledger.granted_ships.is_empty() =>
            {
                ships = Some(Ships {
                    work: col("parent_id"),
                    author: col("author"),
                    position: col("position"),
                })
            }
            (works::C, works::atts::referenced_works) if has(Ids::Works) => {
                work_cols = vec![col("parent_id"), col("referenced_work_id")]
            }
            (works::C, works::atts::locations) | (works::C, works::atts::topics)
                if has(Ids::Works) =>
            {
                work_cols = vec![col("parent_id")]
            }
            (authors::C, _) if has(Ids::Authors) => {
                enrichment_author = headers.iter().position(|h| h == ENRICHMENT_ID)
            }
            _ => {}
        }
        if main_id.is_none()
            && work_cols.is_empty()
            && ships.is_none()
            && enrichment_author.is_none()
        {
            return None;
        }
        Some(Self {
            ledger: Arc::clone(ledger),
            main_id,
            author_cells,
            work_cols,
            ships,
            enrichment_author,
        })
    }

    fn aliases(&self, ids: Ids) -> &HashMap<BigId, BigId> {
        match ids {
            Ids::Authors => &self.ledger.author_aliases,
            Ids::Works => &self.ledger.work_aliases,
        }
    }

    /// The granted authorships as rows of the authorships table, last first: the ids and the
    /// position, every other cell empty.
    fn granted_rows(&self, width: usize) -> Vec<StringRecord> {
        let Some(s) = &self.ships else {
            return Vec::new();
        };
        self.ledger
            .granted_ships
            .iter()
            .rev()
            .map(|g| {
                let mut fields = vec![String::new(); width];
                fields[s.work] = format!("{ID_PREFIX}W{}", g.work);
                fields[s.author] = format!("{ID_PREFIX}A{}", g.author);
                fields[s.position] = g.position.to_string();
                StringRecord::from(fields)
            })
            .collect()
    }

    /// Rewrites the row in place; false when the row does not exist under the ledger.
    fn keeps(&self, rec: &mut StringRecord) -> bool {
        let ledger = &self.ledger;
        let mut rewritten: Vec<(usize, String)> = Vec::new();
        if let Some((c, ids)) = self.main_id {
            if let Some(id) = oa_id_parse_opt(&rec[c]) {
                if self.aliases(ids).contains_key(&id) {
                    return false;
                }
                if let Some(cells) = &self.author_cells {
                    if ledger.stripped_orcids.contains(&id) {
                        rewritten.push((cells.orcid, String::new()));
                    }
                    if let Some(&(works, cites)) = ledger.author_counts.get(&id) {
                        rewritten.push((cells.works, works.to_string()));
                        rewritten.push((cells.cites, cites.to_string()));
                    }
                    if let Some(name) = ledger.author_names.get(&id) {
                        rewritten.push((cells.name, name.clone()));
                    }
                }
            }
        }
        for &c in &self.work_cols {
            if let Some(root) = oa_id_parse_opt(&rec[c]).and_then(|id| ledger.work_aliases.get(&id))
            {
                rewritten.push((c, with_id(&rec[c], *root)));
            }
        }
        if let Some(c) = self.enrichment_author {
            if let Some(keep) = rec[c]
                .parse::<BigId>()
                .ok()
                .and_then(|id| ledger.author_aliases.get(&id))
            {
                rewritten.push((c, keep.to_string()));
            }
        }
        if let Some(s) = &self.ships {
            if let (Some(work), Some(author)) = (
                oa_id_parse_opt(&rec[s.work]),
                oa_id_parse_opt(&rec[s.author]),
            ) {
                let (work_root, author_root) = (ledger.work_root(work), ledger.author_root(author));
                let Some(named) = ledger.row_author((author_root, work_root)) else {
                    return false;
                };
                if work_root != work {
                    rewritten.push((s.work, with_id(&rec[s.work], work_root)));
                }
                match named {
                    Some(a) if a != author => {
                        rewritten.push((s.author, with_id(&rec[s.author], a)))
                    }
                    Some(_) => {}
                    None => rewritten.push((s.author, String::new())),
                }
            }
        }
        if !rewritten.is_empty() {
            let mut fields: Vec<String> = rec.iter().map(str::to_owned).collect();
            for (c, s) in rewritten {
                fields[c] = s;
            }
            *rec = StringRecord::from(fields);
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
            let first = self.current.is_none();
            self.current = Some(PartReader::open(
                &path,
                &self.table,
                self.ledger.as_ref(),
                first,
            ));
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
    let acc_from_path = move |acc: &mut Acc, (i, path): (usize, PathBuf)| {
        let mut part = PartReader::open(&path, &table, ledger.as_ref(), i == 0);
        while let Some(rec) = part.next::<T>() {
            inner_fn(acc, rec);
        }
    };
    map_reduce(
        paths.into_iter().enumerate(),
        acc_from_path,
        reduce_fn,
        n_threads,
    )
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
    use crate::{oa_structs::post::Authorship, user_ledger::GrantedShip};

    fn lens(table: &Table, header: &[&str], ledger: ResolvedLedger) -> Lens {
        Lens::new(
            &Arc::new(ledger),
            table,
            &StringRecord::from(header.to_vec()),
        )
        .unwrap()
    }

    /// A row whose id cells carry the OpenAlex prefix, as the CSVs do.
    fn row(fields: &[&str]) -> StringRecord {
        StringRecord::from(
            fields
                .iter()
                .map(|f| match f.chars().next() {
                    Some('A' | 'W') if f[1..].chars().all(|c| c.is_ascii_digit()) => {
                        format!("{ID_PREFIX}{f}")
                    }
                    _ => f.to_string(),
                })
                .collect::<Vec<_>>(),
        )
    }

    #[test]
    fn a_stripped_author_loses_its_orcid_and_a_keep_carries_the_summed_counts() {
        let ledger = ResolvedLedger {
            author_aliases: [(2, 1)].into_iter().collect(),
            stripped_orcids: [3].into_iter().collect(),
            author_counts: [(1, (12, 340))].into_iter().collect(),
            ..Default::default()
        };
        let table = Table::new(authors::C, MAIN_NAME);
        let header = [
            "id",
            "orcid",
            "display_name",
            "works_count",
            "cited_by_count",
        ];
        let lens = lens(&table, &header, ledger);
        let mut keep = row(&["A1", "0000-1", "Kim Keep", "7", "300"]);
        assert!(lens.keeps(&mut keep));
        assert_eq!(&keep[3], "12");
        assert_eq!(&keep[4], "340");
        assert_eq!(&keep[1], "0000-1");
        let mut drop = row(&["A2", "0000-1", "K. Keep", "5", "40"]);
        assert!(!lens.keeps(&mut drop));
        let mut stripped = row(&["A3", "0000-1", "Ann Other", "9", "10"]);
        assert!(lens.keeps(&mut stripped));
        assert_eq!(&stripped[1], "");
        assert_eq!(&stripped[3], "9");
    }

    #[test]
    fn an_enrichment_row_on_a_merged_author_reads_as_the_keep() {
        let ledger = ResolvedLedger {
            author_aliases: [(2, 1)].into_iter().collect(),
            ..Default::default()
        };
        let table = Table::new(authors::C, "nobel");
        let lens = lens(&table, &["oa_id", "category", "year"], ledger);
        let mut laureate = StringRecord::from(vec!["2", "1", "1990"]);
        assert!(lens.keeps(&mut laureate));
        assert_eq!(&laureate[0], "1");
        let mut other = StringRecord::from(vec!["5", "2", "2001"]);
        assert!(lens.keeps(&mut other));
        assert_eq!(&other[0], "5");
    }

    #[test]
    fn a_merged_authors_rows_read_as_the_keep() {
        let ledger = ResolvedLedger {
            author_aliases: [(2, 1)].into_iter().collect(),
            ..Default::default()
        };
        let table = Table::new(works::C, works::atts::authorships);
        let header = ["parent_id", "author", "institutions", "position"];
        let lens = lens(&table, &header, ledger);
        let mut twin = row(&["W10", "A2", "I7", "1"]);
        assert!(lens.keeps(&mut twin), "the drop's row stays, as the keep's");
        assert_eq!(&twin[1], format!("{ID_PREFIX}A1"));
        assert_eq!(&twin[2], "I7");
        let mut other = row(&["W10", "A5", "", "2"]);
        assert!(lens.keeps(&mut other));
        assert_eq!(&other[1], format!("{ID_PREFIX}A5"));
    }

    #[test]
    fn a_disowned_edge_has_no_row_and_a_merged_work_reads_as_its_keep() {
        let ledger = ResolvedLedger {
            work_aliases: [(11, 10)].into_iter().collect(),
            removed_edges: [(3, 10)].into_iter().collect(),
            ..Default::default()
        };
        let table = Table::new(works::C, works::atts::authorships);
        let header = ["parent_id", "author", "institutions", "position"];
        let lens = lens(&table, &header, ledger);
        let mut disowned = row(&["W11", "A3", "", "0"]);
        assert!(
            !lens.keeps(&mut disowned),
            "the edge is removed in keep space"
        );
        let mut merged = row(&["W11", "A4", "", "1"]);
        assert!(lens.keeps(&mut merged));
        assert_eq!(&merged[0], format!("{ID_PREFIX}W10"));
        assert_eq!(&merged[1], format!("{ID_PREFIX}A4"));
    }

    #[test]
    fn a_reassigned_row_names_its_new_author_or_none_and_a_renamed_author_reads_so() {
        let ledger = ResolvedLedger {
            author_aliases: [(2, 1)].into_iter().collect(),
            reassigned: [((1, 10), Some(7)), ((1, 11), None)].into_iter().collect(),
            author_names: [(1, "Kim Keep".to_string())].into_iter().collect(),
            ..Default::default()
        };
        let ships = Table::new(works::C, works::atts::authorships);
        let header = ["parent_id", "author", "institutions", "position"];
        let ship_lens = lens(&ships, &header, ledger.clone());
        // the edge is matched in keep space, the row keeps its affiliation and position
        let mut moved = row(&["W10", "A2", "I7", "3"]);
        assert!(ship_lens.keeps(&mut moved));
        assert_eq!(moved, row(&["W10", "A7", "I7", "3"]));
        let mut unnamed = row(&["W11", "A1", "I7", "0"]);
        assert!(ship_lens.keeps(&mut unnamed));
        assert_eq!(unnamed, row(&["W11", "", "I7", "0"]));
        let mut other = row(&["W12", "A1", "", "0"]);
        assert!(ship_lens.keeps(&mut other));
        assert_eq!(&other[1], format!("{ID_PREFIX}A1"));

        let authors = Table::new(authors::C, MAIN_NAME);
        let header = [
            "id",
            "orcid",
            "display_name",
            "works_count",
            "cited_by_count",
        ];
        let author_lens = lens(&authors, &header, ledger);
        let mut keep = row(&["A1", "0000-1", "K. Keep", "7", "300"]);
        assert!(author_lens.keeps(&mut keep));
        assert_eq!(&keep[2], "Kim Keep");
        assert_eq!(&keep[1], "0000-1");
    }

    #[test]
    fn a_granted_authorship_is_a_row_of_its_own() {
        let ship = |author, work, position| GrantedShip {
            author,
            work,
            position,
        };
        let ledger = ResolvedLedger {
            granted_ships: vec![ship(3, 10, 2), ship(4, 11, 0)],
            ..Default::default()
        };
        let table = Table::new(works::C, works::atts::authorships);
        let header = ["parent_id", "author", "institutions", "position"];
        let lens = lens(&table, &header, ledger);
        // popped from the end, so they read in the ledger's order
        assert_eq!(
            lens.granted_rows(header.len()),
            vec![row(&["W11", "A4", "", "0"]), row(&["W10", "A3", "", "2"])]
        );
        let mut listed = row(&["W10", "A5", "I7", "0"]);
        assert!(lens.keeps(&mut listed));
        assert_eq!(&listed[1], format!("{ID_PREFIX}A5"));
        let other = Table::new(works::C, works::atts::locations);
        assert!(Lens::new(
            &lens.ledger,
            &other,
            &StringRecord::from(vec!["parent_id", "source"])
        )
        .is_none());
    }

    #[test]
    fn the_first_partition_ends_with_the_granted_rows() {
        let dir = std::env::temp_dir().join(format!("csv-iter-granted-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("authorships.part-0000.csv.zst");
        let csv = format!(
            "parent_id,author,institutions,position\n{ID_PREFIX}W10,{ID_PREFIX}A5,,0\n{ID_PREFIX}W10,,,1\n"
        );
        std::fs::write(&path, zstd::encode_all(csv.as_bytes(), 0).unwrap()).unwrap();
        let ledger = Arc::new(ResolvedLedger {
            granted_ships: vec![GrantedShip {
                author: 3,
                work: 10,
                position: 2,
            }],
            ..Default::default()
        });
        let table = Table::new(works::C, works::atts::authorships);
        let read = |first: bool| {
            let mut part = PartReader::open(&path, &table, Some(&ledger), first);
            std::iter::from_fn(|| part.next::<Authorship>())
                .map(|ship| (ship.author_id, ship.position))
                .collect::<Vec<_>>()
        };
        let listed = vec![(Some(format!("{ID_PREFIX}A5")), 0), (None, 1)];
        let mut with_grant = listed.clone();
        with_grant.push((Some(format!("{ID_PREFIX}A3")), 2));
        assert_eq!(read(true), with_grant);
        assert_eq!(read(false), listed);
        std::fs::remove_dir_all(&dir).unwrap();
    }

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
