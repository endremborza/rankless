use std::{
    fs::{self, File},
    io::{self, BufRead, BufReader, BufWriter},
    path::Path,
    sync::Arc,
};

use hashbrown::{HashMap, HashSet};
use serde::{Deserialize, Serialize};

use crate::{
    common::{ParsedId, Stowage, MAIN_NAME},
    csv_iter::par_reduce,
    csv_writers::{authors, works},
    oa_structs::{post::Author, Work},
};
use dmove::BigId;

pub const ORCID_PREF: &str = "https://orcid.org/";
/// The derived source's records and manifest, written by `derive-ledger` beside the export.
pub const DERIVED_JSONL: &str = "derived.jsonl";
pub const DERIVED_MANIFEST: &str = "derived_manifest.json";
/// The team's curated events, copied beside the site's by `export_user_ledger.py`.
pub const CURATED_JSONL: &str = "curated.jsonl";

const ACTIVE_JSONL: &str = "active.jsonl";
const APPLIED_MANIFEST: &str = "applied_manifest.json";
const RESOLVED_LEDGER: &str = "resolved_ledger.json";
const SNAPSHOT_MANIFEST: &str = "snapshot_manifest.json";
const OWNER_PINS: &str = "owner_pins.txt";
const DOI_PREFIXES: [&str; 4] = [
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
];

type Edge = (BigId, BigId);
/// (works_count, cited_by_count) of an author record
type Counts = (u32, u32);
/// A user's event is reported under its key; a derived record has none.
type Key = Option<String>;

// ---------------------------------------------------------------------------
// Cross-language boundary: user-ledger/active.jsonl
// Source of truth (writer): src/lib/types/ledger.ts
// Mirror types below — keep in sync when TS types change.
// ---------------------------------------------------------------------------

/// The ledger before resolution: the derived source's records, the curated and the site's
/// events keyed by their subjects, plus the pinned owners. `resolve` is the one decision site; it needs only
/// the id facts `SnapshotIds` gathers from the raw CSVs.
#[derive(Default)]
pub struct UserLedger {
    pub run_id: String,
    owner_pin_orcids: HashSet<String>,
    /// every ORCID an event or record names
    orcids: HashSet<String>,
    /// (key, orcid, canonical doi)
    claims: Vec<(String, String, String)>,
    /// (key, orcid, work oa_id)
    disowns: Vec<(String, String, BigId)>,
    /// (key, author oa_id, fate) in source order, the derived records, then the curated events,
    /// then the site's, so the last entry on a record decides
    author_fates: Vec<(Key, BigId, Fate)>,
    /// (key, drop oa_id, keep oa_id)
    work_merges: Vec<(String, BigId, BigId)>,
    /// The author rows the derived records were read from; the CSVs must hold as many.
    derived_rows: Option<u64>,
    skipped: Vec<SkippedEvent>,
}

/// The ids the events name, so the snapshot passes stay membership tests.
#[derive(Default)]
pub struct Referenced {
    pub orcids: HashSet<String>,
    pub authors: HashSet<BigId>,
    pub works: HashSet<BigId>,
    pub dois: HashSet<String>,
    /// The author-table row count the derived records expect, when there are any.
    pub derived_rows: Option<u64>,
}

/// What the raw snapshot holds of the referenced ids.
#[derive(Default)]
pub struct SnapshotIds {
    /// every raw record carrying a referenced ORCID
    pub orcid_carriers: HashMap<String, Vec<BigId>>,
    pub authors: HashMap<BigId, Counts>,
    pub author_rows: u64,
    pub works: HashSet<BigId>,
    pub doi_to_work: HashMap<String, BigId>,
}

/// The tables the CSV reader applies to every row it yields (`csv_iter`): merged ids read as
/// their keep id, drop-side main rows and disowned authorships do not exist, a stripped author
/// carries no ORCID, a keep author carries its merged records' counts. Written by the filter
/// step, loaded by every later one.
#[derive(Default)]
pub struct ResolvedLedger {
    pub run_id: String,
    /// drop oa_id -> keep oa_id, path-compressed
    pub author_aliases: HashMap<BigId, BigId>,
    pub work_aliases: HashMap<BigId, BigId>,
    /// (author oa_id, work oa_id) in keep-id space
    pub removed_edges: HashSet<Edge>,
    pub stripped_orcids: HashSet<BigId>,
    /// keep oa_id -> its own counts plus every merged record's
    pub author_counts: HashMap<BigId, Counts>,
}

/// Everything the filter step still needs after resolution: the pinned owners whose
/// œuvre is forced, the claims awaiting their credit check, and the decided keys.
pub struct Outcomes {
    pub run_id: String,
    /// Owner oa_ids in keep-id space
    pub pins: HashSet<BigId>,
    pub claims: Vec<PendingClaim>,
    applied: Vec<String>,
    skipped: Vec<SkippedEvent>,
}

/// A claim applies iff the claimant is credited on the work once the ledger is applied.
pub struct PendingClaim {
    pub key: String,
    pub claimant: BigId,
    pub work: BigId,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkippedEvent {
    pub key: String,
    pub reason: SkipReason,
}

#[derive(Deserialize)]
struct WorkSubject {
    oa_id: Option<BigId>,
    doi: Option<String>,
}

#[derive(Deserialize)]
struct AuthorSubject {
    oa_id: Option<BigId>,
}

#[derive(Deserialize)]
struct LedgerEventLine {
    /// Merge-stable logical id (`orcid|kind|subject_hash`); the pipeline references events
    /// by this, never by the renumberable event_id. Written by export_user_ledger.py.
    key: String,
    orcid: String,
    payload: EventPayload,
}

#[derive(Deserialize)]
struct DerivedManifestFile {
    author_rows: u64,
}

/// On-disk form of `ResolvedLedger`, pairs sorted for determinism.
#[derive(Serialize, Deserialize)]
struct ResolvedLedgerFile {
    run_id: String,
    author_aliases: Vec<Edge>,
    work_aliases: Vec<Edge>,
    removed_edges: Vec<Edge>,
    stripped_orcids: Vec<BigId>,
    author_counts: Vec<(BigId, Counts)>,
}

// ---------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SkipReason {
    MissingOaId,
    MissingOaIdOrOrcid,
    OrcidNotInDataset,
    OaIdNotInDataset,
    DoiNotInSnapshot,
    ClaimantNotAttributed,
}

/// Mirrors TS `LedgerPayload`; `kind` is the discriminant tag.
#[derive(Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
enum EventPayload {
    MergeAuthors {
        keep: AuthorSubject,
        drop: AuthorSubject,
    },
    MergePapers {
        keep: WorkSubject,
        drop: WorkSubject,
    },
    DisownPaper {
        work: WorkSubject,
    },
    ClaimPaper {
        work: WorkSubject,
    },
    /// The record is not this ORCID's person: its `orcid` cell reads empty.
    StripOrcid {
        author: AuthorSubject,
    },
    // Never reach the pipeline (revokes are resolved away in export_user_ledger.py; the
    // other two are never written to the ledger), but kept as variants so EventPayload
    // stays a faithful mirror of TS LedgerPayload (see make type-audit).
    Revoke,
    ModerationDecision,
    AddPaperRequest,
}

/// What the ledger does to an author record.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Fate {
    /// merged into the keep
    Merge(BigId),
    /// its `orcid` cell reads empty
    Strip,
}

impl UserLedger {
    pub fn load(ul_dir: &Path) -> io::Result<Self> {
        let mut ul = Self {
            run_id: read_run_id(ul_dir),
            owner_pin_orcids: load_owner_pins(ul_dir)?,
            ..Self::default()
        };
        let derived = ul_dir.join(DERIVED_JSONL);
        if derived.exists() {
            for line in read_lines(&derived)? {
                ul.apply_derived(serde_json::from_str(&line).map_err(invalid)?)?;
            }
            let manifest: DerivedManifestFile =
                serde_json::from_str(&fs::read_to_string(ul_dir.join(DERIVED_MANIFEST))?)
                    .map_err(invalid)?;
            ul.derived_rows = Some(manifest.author_rows);
        }
        for line in read_lines(&ul_dir.join(CURATED_JSONL))? {
            ul.apply_event(serde_json::from_str(&line).map_err(invalid)?);
        }
        for line in read_lines(&ul_dir.join(ACTIVE_JSONL))? {
            match serde_json::from_str::<LedgerEventLine>(&line) {
                Ok(event) => ul.apply_event(event),
                Err(e) => eprintln!("user_ledger: skipping malformed event: {e}"),
            }
        }
        Ok(ul)
    }

    pub fn referenced(&self) -> Referenced {
        Referenced {
            orcids: self.owner_pin_orcids.union(&self.orcids).cloned().collect(),
            authors: self
                .author_fates
                .iter()
                .flat_map(|&(_, id, fate)| match fate {
                    Fate::Merge(keep) => vec![id, keep],
                    Fate::Strip => vec![],
                })
                .collect(),
            works: self
                .work_merges
                .iter()
                .map(|(_, _, k)| *k)
                .chain(self.disowns.iter().map(|(_, _, w)| *w))
                .collect(),
            dois: self.claims.iter().map(|(_, _, d)| d.clone()).collect(),
            derived_rows: self.derived_rows,
        }
    }

    /// A merge applies iff its keep id is in the snapshot: rewriting an absent drop id is
    /// a no-op, while a merge into an absent keep would erase the drop side. The last fate
    /// recorded on an author record decides, so a user's event replaces a derived record's.
    /// A disown applies iff its owner and work resolve; a claim is settled later, once the
    /// reader shows who is credited on the work. Fails on a stale derived file and when an
    /// ORCID would still resolve to more than one author.
    pub fn resolve(self, ids: &SnapshotIds) -> io::Result<(ResolvedLedger, Outcomes)> {
        if let Some(rows) = self.derived_rows {
            if rows != ids.author_rows {
                return Err(invalid(format!(
                    "{DERIVED_JSONL} was derived from {rows} author rows, the CSVs hold {} — rerun derive-ledger",
                    ids.author_rows
                )));
            }
        }
        let mut applied = Vec::new();
        let mut skipped = self.skipped;
        let mut skip = |key: String, reason: SkipReason| skipped.push(SkippedEvent { key, reason });

        let mut fates: HashMap<BigId, (Fate, Key)> = HashMap::new();
        for (key, id, fate) in self.author_fates {
            fates.insert(id, (fate, key));
        }
        let mut author_aliases = HashMap::new();
        let mut stripped_orcids = HashSet::new();
        for (id, (fate, key)) in fates {
            let ok = match fate {
                Fate::Merge(keep) if ids.authors.contains_key(&keep) => {
                    author_aliases.insert(id, keep);
                    true
                }
                Fate::Merge(_) => false,
                Fate::Strip => {
                    stripped_orcids.insert(id);
                    true
                }
            };
            match (key, ok) {
                (Some(key), true) => applied.push(key),
                (Some(key), false) => skip(key, SkipReason::OaIdNotInDataset),
                (None, true) => {}
                (None, false) => {
                    return Err(invalid(format!(
                        "{DERIVED_JSONL} merges {id} into an author the CSVs lack"
                    )))
                }
            }
        }
        path_compress(&mut author_aliases);
        let mut work_aliases = HashMap::new();
        for (key, drop, keep) in self.work_merges {
            match ids.works.contains(&keep) {
                true => {
                    work_aliases.insert(drop, keep);
                    applied.push(key);
                }
                false => skip(key, SkipReason::OaIdNotInDataset),
            }
        }
        path_compress(&mut work_aliases);
        let author_root = |a: BigId| author_aliases.get(&a).copied().unwrap_or(a);
        let work_root = |w: BigId| work_aliases.get(&w).copied().unwrap_or(w);

        let mut author_counts: HashMap<BigId, Counts> = HashMap::new();
        for (&drop, &keep) in &author_aliases {
            let total = author_counts
                .entry(keep)
                .or_insert_with(|| ids.authors.get(&keep).copied().unwrap_or_default());
            if let Some(&(works, cites)) = ids.authors.get(&drop) {
                total.0 = total.0.saturating_add(works);
                total.1 = total.1.saturating_add(cites);
            }
        }

        let mut orcid_to_oa = HashMap::new();
        for (orcid, carriers) in &ids.orcid_carriers {
            let mut owners: Vec<BigId> = carriers
                .iter()
                .filter(|&c| !stripped_orcids.contains(c))
                .map(|&c| author_root(c))
                .collect();
            owners.sort_unstable();
            owners.dedup();
            match owners.as_slice() {
                [] => {}
                [one] => {
                    orcid_to_oa.insert(orcid.clone(), *one);
                }
                many => {
                    return Err(invalid(format!(
                        "ORCID {orcid} still resolves to {} authors {many:?} — the derived records do not cover it, rerun derive-ledger",
                        many.len()
                    )))
                }
            }
        }

        let mut removed_edges = HashSet::new();
        for (key, orcid, work) in self.disowns {
            let Some(&owner) = orcid_to_oa.get(&orcid) else {
                skip(key, SkipReason::OrcidNotInDataset);
                continue;
            };
            if !ids.works.contains(&work) {
                skip(key, SkipReason::OaIdNotInDataset);
                continue;
            }
            removed_edges.insert((owner, work_root(work)));
            applied.push(key);
        }

        let mut claims = Vec::new();
        for (key, orcid, doi) in self.claims {
            let Some(&work) = ids.doi_to_work.get(&doi) else {
                skip(key, SkipReason::DoiNotInSnapshot);
                continue;
            };
            let Some(&claimant) = orcid_to_oa.get(&orcid) else {
                skip(key, SkipReason::OrcidNotInDataset);
                continue;
            };
            claims.push(PendingClaim {
                key,
                claimant,
                work: work_root(work),
            });
        }
        let pins = self
            .owner_pin_orcids
            .iter()
            .filter_map(|orcid| orcid_to_oa.get(orcid))
            .copied()
            .collect();

        let resolved = ResolvedLedger {
            run_id: self.run_id.clone(),
            author_aliases,
            work_aliases,
            removed_edges,
            stripped_orcids,
            author_counts,
        };
        let outcomes = Outcomes {
            run_id: self.run_id,
            pins,
            claims,
            applied,
            skipped,
        };
        Ok((resolved, outcomes))
    }

    fn apply_event(&mut self, event: LedgerEventLine) {
        let LedgerEventLine {
            key,
            orcid,
            payload,
        } = event;
        let orcid = normalize_orcid(&orcid);
        if !orcid.is_empty() {
            self.orcids.insert(orcid.clone());
        }
        let mut skip =
            |key: String, reason: SkipReason| self.skipped.push(SkippedEvent { key, reason });
        match payload {
            EventPayload::MergeAuthors { keep, drop } => match (keep.oa_id, drop.oa_id) {
                (Some(k), Some(d)) if k != d => {
                    self.author_fates.push((Some(key), d, Fate::Merge(k)))
                }
                _ => skip(key, SkipReason::MissingOaId),
            },
            EventPayload::MergePapers { keep, drop } => match (keep.oa_id, drop.oa_id) {
                (Some(k), Some(d)) if k != d => self.work_merges.push((key, d, k)),
                _ => skip(key, SkipReason::MissingOaId),
            },
            EventPayload::DisownPaper { work } => match work.oa_id {
                Some(w) if !orcid.is_empty() => self.disowns.push((key, orcid, w)),
                _ => skip(key, SkipReason::MissingOaIdOrOrcid),
            },
            EventPayload::ClaimPaper { work } => match work.doi {
                Some(doi) if !orcid.is_empty() => {
                    self.claims.push((key, orcid, canonical_doi(&doi)))
                }
                _ => skip(key, SkipReason::MissingOaIdOrOrcid),
            },
            EventPayload::StripOrcid { author } => match author.oa_id {
                Some(a) => self.author_fates.push((Some(key), a, Fate::Strip)),
                None => skip(key, SkipReason::MissingOaId),
            },
            // Resolved in export or never emitted; never present in active.jsonl.
            EventPayload::Revoke
            | EventPayload::ModerationDecision
            | EventPayload::AddPaperRequest => {}
        }
    }

    /// A derived line is machine-written: anything but a complete merge or strip is an error.
    fn apply_derived(&mut self, event: LedgerEventLine) -> io::Result<()> {
        let (id, fate) = match event.payload {
            EventPayload::MergeAuthors {
                keep: AuthorSubject { oa_id: Some(k) },
                drop: AuthorSubject { oa_id: Some(d) },
            } if k != d => (d, Fate::Merge(k)),
            EventPayload::StripOrcid {
                author: AuthorSubject { oa_id: Some(a) },
            } => (a, Fate::Strip),
            _ => {
                return Err(invalid(format!(
                    "{DERIVED_JSONL}: {} is not a complete merge or strip",
                    event.key
                )))
            }
        };
        self.author_fates.push((None, id, fate));
        self.orcids.insert(normalize_orcid(&event.orcid));
        Ok(())
    }
}

impl SnapshotIds {
    /// Two passes over the raw main tables (the reader carries no ledger yet), each
    /// skipped when nothing references that table.
    pub fn scan(stowage: &Stowage, refs: Referenced) -> Self {
        let mut ids = Self::default();
        let refs = Arc::new(refs);
        if !(refs.orcids.is_empty() && refs.authors.is_empty() && refs.derived_rows.is_none()) {
            let r = Arc::clone(&refs);
            let scanned = par_reduce::<Author, SnapshotIds, _, _>(
                stowage,
                authors::C,
                MAIN_NAME,
                move |acc, a| {
                    acc.author_rows += 1;
                    let Some(oa_id) = a.get_parsed_id() else {
                        return;
                    };
                    if r.authors.contains(&oa_id) {
                        acc.authors.insert(
                            oa_id,
                            (a.works_count.unwrap_or(0), a.cited_by_count.unwrap_or(0)),
                        );
                    }
                    if let Some(orcid) = a.orcid {
                        let orcid = normalize_orcid(&orcid);
                        if r.orcids.contains(&orcid) {
                            acc.orcid_carriers.entry(orcid).or_default().push(oa_id);
                        }
                    }
                },
                Self::merge,
                Some(10),
            );
            ids.authors = scanned.authors;
            ids.author_rows = scanned.author_rows;
            ids.orcid_carriers = scanned.orcid_carriers;
            for carriers in ids.orcid_carriers.values_mut() {
                carriers.sort_unstable();
            }
        }
        if !(refs.works.is_empty() && refs.dois.is_empty()) {
            let r = Arc::clone(&refs);
            let scanned = par_reduce::<Work, SnapshotIds, _, _>(
                stowage,
                works::C,
                MAIN_NAME,
                move |acc, w| {
                    let Some(oa_id) = w.get_parsed_id() else {
                        return;
                    };
                    if r.works.contains(&oa_id) {
                        acc.works.insert(oa_id);
                    }
                    if let Some(doi) = w.doi.as_deref().map(canonical_doi) {
                        if r.dois.contains(&doi) {
                            acc.doi_to_work.insert(doi, oa_id);
                        }
                    }
                },
                Self::merge,
                Some(10),
            );
            ids.works = scanned.works;
            ids.doi_to_work = scanned.doi_to_work;
        }
        ids
    }

    fn merge(a: &mut Self, b: Self) {
        for (orcid, carriers) in b.orcid_carriers {
            a.orcid_carriers.entry(orcid).or_default().extend(carriers);
        }
        a.authors.extend(b.authors);
        a.author_rows += b.author_rows;
        a.works.extend(b.works);
        a.doi_to_work.extend(b.doi_to_work);
    }
}

impl ResolvedLedger {
    pub fn author_root(&self, a: BigId) -> BigId {
        self.author_aliases.get(&a).copied().unwrap_or(a)
    }

    pub fn work_root(&self, w: BigId) -> BigId {
        self.work_aliases.get(&w).copied().unwrap_or(w)
    }

    pub fn is_empty(&self) -> bool {
        self.author_aliases.is_empty()
            && self.work_aliases.is_empty()
            && self.removed_edges.is_empty()
            && self.stripped_orcids.is_empty()
            && self.author_counts.is_empty()
    }

    pub fn save(&self, ul_dir: &Path) -> io::Result<()> {
        fn sorted<T: Ord>(it: impl Iterator<Item = T>) -> Vec<T> {
            let mut v: Vec<T> = it.collect();
            v.sort_unstable();
            v
        }
        let file = ResolvedLedgerFile {
            run_id: self.run_id.clone(),
            author_aliases: sorted(self.author_aliases.iter().map(|(&d, &k)| (d, k))),
            work_aliases: sorted(self.work_aliases.iter().map(|(&d, &k)| (d, k))),
            removed_edges: sorted(self.removed_edges.iter().copied()),
            stripped_orcids: sorted(self.stripped_orcids.iter().copied()),
            author_counts: sorted(self.author_counts.iter().map(|(&a, &c)| (a, c))),
        };
        serde_json::to_writer(
            BufWriter::new(File::create(ul_dir.join(RESOLVED_LEDGER))?),
            &file,
        )
        .map_err(io::Error::other)
    }

    /// Refuses a missing or stale file: the filter step of the current snapshot export
    /// must have run.
    pub fn load(ul_dir: &Path) -> io::Result<Self> {
        let raw = fs::read_to_string(ul_dir.join(RESOLVED_LEDGER)).map_err(|_| {
            io::Error::new(
                io::ErrorKind::NotFound,
                format!("{RESOLVED_LEDGER} missing — the filter step must run first"),
            )
        })?;
        let file: ResolvedLedgerFile = serde_json::from_str(&raw).map_err(invalid)?;
        let snapshot_run = read_run_id(ul_dir);
        if file.run_id != snapshot_run {
            return Err(invalid(format!(
                "{RESOLVED_LEDGER} is from run {:?} but the snapshot manifest says {snapshot_run:?} — re-run the filter step",
                file.run_id
            )));
        }
        Ok(Self {
            run_id: file.run_id,
            author_aliases: file.author_aliases.into_iter().collect(),
            work_aliases: file.work_aliases.into_iter().collect(),
            removed_edges: file.removed_edges.into_iter().collect(),
            stripped_orcids: file.stripped_orcids.into_iter().collect(),
            author_counts: file.author_counts.into_iter().collect(),
        })
    }
}

impl Outcomes {
    /// `credited`: (author, work) pairs the applied ledger yields for the claimants.
    ///
    /// Cross-language boundary: applied_manifest.json (Rust → TS)
    /// Mirror: src/lib/types/ledger.ts — AppliedManifest
    pub fn write_manifest(&self, ul_dir: &Path, credited: &HashSet<Edge>) -> io::Result<()> {
        let mut applied = self.applied.clone();
        let mut skipped = self.skipped.clone();
        for claim in &self.claims {
            match credited.contains(&(claim.claimant, claim.work)) {
                true => applied.push(claim.key.clone()),
                false => skipped.push(SkippedEvent {
                    key: claim.key.clone(),
                    reason: SkipReason::ClaimantNotAttributed,
                }),
            }
        }
        applied.sort_unstable();
        skipped.sort_unstable_by(|a, b| a.key.cmp(&b.key));
        let manifest = serde_json::json!({
            "run_id": self.run_id,
            "snapshot_at": self.run_id,
            "applied_keys": applied,
            "skipped": skipped,
        });
        write_json(&ul_dir.join(APPLIED_MANIFEST), &manifest)?;
        println!(
            "applied_manifest: {} applied, {} skipped",
            applied.len(),
            skipped.len()
        );
        Ok(())
    }
}

/// Bare DOI: the resolver URL OpenAlex prefixes onto the works-CSV `doi` column
/// removed, case untouched (a2 serves this form).
pub fn strip_doi_prefix(doi: &str) -> &str {
    let trimmed = doi.trim();
    for pref in DOI_PREFIXES {
        if trimmed
            .get(..pref.len())
            .map_or(false, |head| head.eq_ignore_ascii_case(pref))
        {
            return &trimmed[pref.len()..];
        }
    }
    trimmed
}

/// Mirror of canonicalDoi in src/lib/utils/identifiers.ts (claim subjects store this
/// form); also applied to the works-CSV `doi` column so the two sides join.
pub fn canonical_doi(doi: &str) -> String {
    strip_doi_prefix(doi).to_lowercase()
}

pub fn normalize_orcid(orcid: &str) -> String {
    orcid.strip_prefix(ORCID_PREF).unwrap_or(orcid).to_string()
}

fn invalid(e: impl Into<Box<dyn std::error::Error + Send + Sync>>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, e)
}

/// The non-empty lines of a file that may not exist.
fn read_lines(path: &Path) -> io::Result<Vec<String>> {
    if !path.exists() {
        return Ok(Vec::new());
    }
    BufReader::new(File::open(path)?)
        .lines()
        .filter(|l| l.as_ref().map_or(true, |l| !l.trim().is_empty()))
        .collect()
}

fn read_run_id(ul_dir: &Path) -> String {
    let path = ul_dir.join(SNAPSHOT_MANIFEST);
    if !path.exists() {
        return String::new();
    }
    fs::read_to_string(&path)
        .ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| v["run_id"].as_str().map(String::from))
        .unwrap_or_default()
}

fn load_owner_pins(ul_dir: &Path) -> io::Result<HashSet<String>> {
    Ok(read_lines(&ul_dir.join(OWNER_PINS))?
        .iter()
        .map(|l| normalize_orcid(l.trim()))
        .collect())
}

fn find_root(id: BigId, map: &HashMap<BigId, BigId>) -> BigId {
    let mut cur = id;
    loop {
        match map.get(&cur) {
            Some(&next) if next != cur => cur = next,
            _ => return cur,
        }
    }
}

fn path_compress(map: &mut HashMap<BigId, BigId>) {
    let keys: Vec<BigId> = map.keys().copied().collect();
    for k in keys {
        let root = find_root(k, map);
        map.insert(k, root);
    }
}

pub(crate) fn write_json<T: serde::Serialize>(path: &Path, val: &T) -> io::Result<()> {
    serde_json::to_writer_pretty(BufWriter::new(File::create(path)?), val).map_err(io::Error::other)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn line(json: &str) -> LedgerEventLine {
        serde_json::from_str(json).unwrap()
    }

    fn carriers(pairs: &[(&str, &[BigId])]) -> HashMap<String, Vec<BigId>> {
        pairs
            .iter()
            .map(|(o, ids)| (o.to_string(), ids.to_vec()))
            .collect()
    }

    fn counts(ids: &[BigId]) -> HashMap<BigId, Counts> {
        ids.iter().map(|&i| (i, (1, 1))).collect()
    }

    #[test]
    fn path_compress_chain() {
        let mut m: HashMap<u64, u64> = [(1, 2), (2, 3)].into_iter().collect();
        path_compress(&mut m);
        assert_eq!(m[&1], 3);
        assert_eq!(m[&2], 3);
    }

    #[test]
    fn path_compress_flat() {
        let mut m: HashMap<u64, u64> = [(1, 5), (2, 5)].into_iter().collect();
        path_compress(&mut m);
        assert_eq!(m[&1], 5);
        assert_eq!(m[&2], 5);
    }

    #[test]
    fn normalize_orcid_strips_prefix() {
        assert_eq!(
            normalize_orcid("https://orcid.org/0000-0001-2345-6789"),
            "0000-0001-2345-6789"
        );
        assert_eq!(
            normalize_orcid("0000-0001-2345-6789"),
            "0000-0001-2345-6789"
        );
    }

    #[test]
    fn apply_event_merge_authors() {
        let event = line(
            r#"{"key":"x|merge_authors|h","orcid":"x","payload":{"kind":"merge_authors","keep":{"oa_id":10},"drop":{"oa_id":20}}}"#,
        );
        assert!(matches!(
            event.payload,
            EventPayload::MergeAuthors {
                keep: AuthorSubject { oa_id: Some(10) },
                drop: AuthorSubject { oa_id: Some(20) }
            }
        ));
    }

    #[test]
    fn claim_paper_collects_canonical_doi() {
        let mut ul = UserLedger::default();
        ul.apply_event(line(
            r#"{"key":"0-1|claim_paper|h","orcid":"0-1","payload":{"kind":"claim_paper","work":{"oa_id":null,"doi":"https://doi.org/10.1000/XYZ"}}}"#,
        ));
        assert_eq!(
            ul.claims,
            vec![(
                "0-1|claim_paper|h".to_string(),
                "0-1".to_string(),
                "10.1000/xyz".to_string()
            )]
        );
        ul.apply_event(line(
            r#"{"key":"0-1|claim_paper|h2","orcid":"0-1","payload":{"kind":"claim_paper","work":{"oa_id":5,"doi":null}}}"#,
        ));
        assert_eq!(ul.skipped.len(), 1);
        assert_eq!(ul.skipped[0].reason, SkipReason::MissingOaIdOrOrcid);
    }

    #[test]
    fn resolve_requires_keep_and_settles_in_keep_space() {
        let mut ul = UserLedger::default();
        for l in [
            r#"{"key":"o|merge_authors|a","orcid":"o","payload":{"kind":"merge_authors","keep":{"oa_id":1},"drop":{"oa_id":2}}}"#,
            r#"{"key":"o|merge_authors|b","orcid":"o","payload":{"kind":"merge_authors","keep":{"oa_id":9},"drop":{"oa_id":3}}}"#,
            r#"{"key":"o|merge_papers|c","orcid":"o","payload":{"kind":"merge_papers","keep":{"oa_id":10,"doi":null},"drop":{"oa_id":11,"doi":null}}}"#,
            r#"{"key":"o|disown_paper|d","orcid":"o","payload":{"kind":"disown_paper","work":{"oa_id":11,"doi":null}}}"#,
            r#"{"key":"o|claim_paper|e","orcid":"o","payload":{"kind":"claim_paper","work":{"oa_id":null,"doi":"10.1/x"}}}"#,
        ] {
            ul.apply_event(line(l));
        }
        ul.owner_pin_orcids.insert("o".into());
        let ids = SnapshotIds {
            orcid_carriers: carriers(&[("o", &[2])]),
            authors: [(1, (4, 40)), (2, (3, 30))].into_iter().collect(),
            author_rows: 5,
            works: [10, 11].into_iter().collect(),
            doi_to_work: [("10.1/x".to_string(), 11u64)].into_iter().collect(),
        };
        let (resolved, outcomes) = ul.resolve(&ids).unwrap();
        assert_eq!(resolved.author_aliases, [(2, 1)].into_iter().collect());
        assert_eq!(resolved.work_aliases, [(11, 10)].into_iter().collect());
        // the keep row carries both records' counts
        assert_eq!(resolved.author_counts, [(1, (7, 70))].into_iter().collect());
        // the owner's own id and the disowned work both read in keep space
        assert_eq!(resolved.removed_edges, [(1, 10)].into_iter().collect());
        assert_eq!(outcomes.pins, [1].into_iter().collect());
        assert_eq!(outcomes.claims.len(), 1);
        assert_eq!(
            (outcomes.claims[0].claimant, outcomes.claims[0].work),
            (1, 10)
        );
        assert_eq!(outcomes.applied.len(), 3);
        assert_eq!(outcomes.skipped.len(), 1);
        assert_eq!(outcomes.skipped[0].key, "o|merge_authors|b");
    }

    #[test]
    fn derived_records_decide_first_and_user_events_replace_them() {
        let mut ul = UserLedger::default();
        for l in [
            r#"{"key":"2|merge_authors|1","orcid":"o","kind":"merge_authors","source":"derived","reason":"most_works","payload":{"kind":"merge_authors","keep":{"oa_id":1},"drop":{"oa_id":2}}}"#,
            r#"{"key":"3|merge_authors|1","orcid":"o","kind":"merge_authors","source":"derived","reason":"most_works","payload":{"kind":"merge_authors","keep":{"oa_id":1},"drop":{"oa_id":3}}}"#,
            r#"{"key":"4|strip_orcid|","orcid":"o","kind":"strip_orcid","source":"derived","reason":"name_mismatch","payload":{"kind":"strip_orcid","author":{"oa_id":4}}}"#,
            r#"{"key":"5|strip_orcid|","orcid":"o","kind":"strip_orcid","source":"derived","reason":"over_work_bound","payload":{"kind":"strip_orcid","author":{"oa_id":5}}}"#,
        ] {
            ul.apply_derived(line(l)).unwrap();
        }
        ul.derived_rows = Some(6);
        // the user says 3 is not their record after all, and 4 is
        ul.apply_event(line(
            r#"{"key":"o|strip_orcid|x","orcid":"o","payload":{"kind":"strip_orcid","author":{"oa_id":3}}}"#,
        ));
        ul.apply_event(line(
            r#"{"key":"o|merge_authors|y","orcid":"o","payload":{"kind":"merge_authors","keep":{"oa_id":1},"drop":{"oa_id":4}}}"#,
        ));
        ul.owner_pin_orcids.insert("o".into());
        let refs = ul.referenced();
        assert_eq!(refs.derived_rows, Some(6));
        assert!(refs.orcids.contains("o"));
        assert_eq!(refs.authors, [1, 2, 3, 4].into_iter().collect());
        let ids = SnapshotIds {
            orcid_carriers: carriers(&[("o", &[1, 2, 3, 4, 5])]),
            authors: counts(&[1, 2, 3, 4]),
            author_rows: 6,
            ..Default::default()
        };
        let (resolved, outcomes) = ul.resolve(&ids).unwrap();
        assert_eq!(
            resolved.author_aliases,
            [(2, 1), (4, 1)].into_iter().collect()
        );
        assert_eq!(resolved.stripped_orcids, [3, 5].into_iter().collect());
        assert_eq!(resolved.author_counts, [(1, (3, 3))].into_iter().collect());
        assert_eq!(outcomes.pins, [1].into_iter().collect());
        assert_eq!(outcomes.applied.len(), 2);
        assert!(outcomes.skipped.is_empty());
    }

    #[test]
    fn load_reads_the_derived_then_the_curated_then_the_site_records() {
        let dir = std::env::temp_dir().join(format!("user-ledger-load-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let merge = |key: &str, keep: BigId, drop: BigId| {
            format!(
                r#"{{"key":"{key}","orcid":"o","payload":{{"kind":"merge_authors","keep":{{"oa_id":{keep}}},"drop":{{"oa_id":{drop}}}}}}}"#
            ) + "\n"
        };
        fs::write(dir.join(DERIVED_JSONL), merge("o|merge_authors|2", 1, 2)).unwrap();
        fs::write(dir.join(DERIVED_MANIFEST), r#"{"author_rows": 5}"#).unwrap();
        // a same-name record without an ORCID folded into a record the derived source merges
        fs::write(
            dir.join(CURATED_JSONL),
            merge("o|merge_authors|c7", 2, 7) + &merge("o|merge_authors|c8", 1, 8),
        )
        .unwrap();
        fs::write(dir.join(ACTIVE_JSONL), merge("o|merge_authors|s9", 1, 9)).unwrap();
        let ul = UserLedger::load(&dir).unwrap();
        fs::remove_dir_all(&dir).unwrap();

        let order: Vec<(Option<&str>, BigId)> = ul
            .author_fates
            .iter()
            .map(|(key, id, _)| (key.as_deref(), *id))
            .collect();
        assert_eq!(
            order,
            vec![
                (None, 2),
                (Some("o|merge_authors|c7"), 7),
                (Some("o|merge_authors|c8"), 8),
                (Some("o|merge_authors|s9"), 9)
            ]
        );
        let ids = SnapshotIds {
            orcid_carriers: carriers(&[("o", &[1, 2])]),
            authors: counts(&[1, 2, 7, 8, 9]),
            author_rows: 5,
            ..Default::default()
        };
        let (resolved, outcomes) = ul.resolve(&ids).unwrap();
        assert_eq!(
            resolved.author_aliases,
            [(2, 1), (7, 1), (8, 1), (9, 1)].into_iter().collect()
        );
        assert_eq!(outcomes.applied.len(), 3);
    }

    #[test]
    fn a_derived_line_is_a_complete_merge_or_strip() {
        let mut ul = UserLedger::default();
        for l in [
            r#"{"key":"k","orcid":"o","payload":{"kind":"merge_authors","keep":{"oa_id":1},"drop":{"oa_id":null}}}"#,
            r#"{"key":"k","orcid":"o","payload":{"kind":"disown_paper","work":{"oa_id":1,"doi":null}}}"#,
        ] {
            assert!(ul.apply_derived(line(l)).is_err());
        }
        assert!(ul.author_fates.is_empty());
    }

    #[test]
    fn an_orcid_on_two_authors_after_resolution_is_an_error() {
        let mut ul = UserLedger::default();
        ul.owner_pin_orcids.insert("o".into());
        let ids = SnapshotIds {
            orcid_carriers: carriers(&[("o", &[1, 2])]),
            authors: counts(&[1, 2]),
            author_rows: 2,
            ..Default::default()
        };
        assert!(ul.resolve(&ids).is_err());
        let mut ul = UserLedger::default();
        ul.derived_rows = Some(3);
        let ids = SnapshotIds {
            author_rows: 2,
            ..Default::default()
        };
        assert!(ul.resolve(&ids).is_err());
    }

    #[test]
    fn canonical_doi_forms() {
        assert_eq!(canonical_doi("10.1000/xyz"), "10.1000/xyz");
        assert_eq!(
            canonical_doi(" https://dx.doi.org/10.1000/XYZ "),
            "10.1000/xyz"
        );
        // the CSV column keeps its case; a bare or short doi survives intact
        assert_eq!(strip_doi_prefix("https://doi.org/10.1/XYZ"), "10.1/XYZ");
        assert_eq!(strip_doi_prefix("10.1/x"), "10.1/x");
    }

    #[test]
    fn apply_event_unknown_kind_errors() {
        let result = serde_json::from_str::<LedgerEventLine>(
            r#"{"key":"x|unknown|h","orcid":"x","payload":{"kind":"unknown_future_kind"}}"#,
        );
        assert!(result.is_err());
    }
}
