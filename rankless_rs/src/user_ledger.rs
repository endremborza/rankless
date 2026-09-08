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

// ---------------------------------------------------------------------------
// Cross-language boundary: user-ledger/active.jsonl
// Source of truth (writer): src/lib/types/ledger.ts
// Mirror types below — keep in sync when TS types change.
// ---------------------------------------------------------------------------

/// The exported ledger before resolution: events keyed by their subjects, plus the pinned
/// owners. `resolve` is the one decision site; it needs only the id facts `SnapshotIds`
/// gathers from the raw CSVs.
#[derive(Default)]
pub struct UserLedger {
    pub run_id: String,
    owner_pin_orcids: HashSet<String>,
    /// (key, orcid, canonical doi)
    claims: Vec<(String, String, String)>,
    /// (key, orcid, work oa_id)
    disowns: Vec<(String, String, BigId)>,
    /// (key, drop oa_id, keep oa_id)
    author_merges: Vec<(String, BigId, BigId)>,
    work_merges: Vec<(String, BigId, BigId)>,
    skipped: Vec<SkippedEvent>,
}

/// The ids the events name, so the snapshot passes stay membership tests.
#[derive(Default)]
pub struct Referenced {
    pub orcids: HashSet<String>,
    pub authors: HashSet<BigId>,
    pub works: HashSet<BigId>,
    pub dois: HashSet<String>,
}

/// What the raw snapshot holds of the referenced ids.
#[derive(Default)]
pub struct SnapshotIds {
    pub orcid_to_oa: HashMap<String, BigId>,
    pub authors: HashSet<BigId>,
    pub works: HashSet<BigId>,
    pub doi_to_work: HashMap<String, BigId>,
}

/// The tables the CSV reader applies to every row it yields (`csv_iter`): merged ids read
/// as their keep id, drop-side main rows and disowned authorships do not exist. Written by
/// the filter step, loaded by every later one.
#[derive(Default)]
pub struct ResolvedLedger {
    pub run_id: String,
    /// drop oa_id -> keep oa_id, path-compressed
    pub author_aliases: HashMap<BigId, BigId>,
    pub work_aliases: HashMap<BigId, BigId>,
    /// (author oa_id, work oa_id) in keep-id space
    pub removed_edges: HashSet<Edge>,
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

/// On-disk form of `ResolvedLedger`, pairs sorted for determinism.
#[derive(Serialize, Deserialize)]
struct ResolvedLedgerFile {
    run_id: String,
    author_aliases: Vec<Edge>,
    work_aliases: Vec<Edge>,
    removed_edges: Vec<Edge>,
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
    // Never reach the pipeline (revokes are resolved away in export_user_ledger.py; the
    // other two are never written to the ledger), but kept as variants so EventPayload
    // stays a faithful mirror of TS LedgerPayload (see make type-audit).
    Revoke,
    ModerationDecision,
    AddPaperRequest,
}

impl UserLedger {
    pub fn load(ul_dir: &Path) -> io::Result<Self> {
        let mut ul = Self {
            run_id: read_run_id(ul_dir),
            owner_pin_orcids: load_owner_pins(ul_dir)?,
            ..Self::default()
        };
        let active_path = ul_dir.join(ACTIVE_JSONL);
        if active_path.exists() {
            for line in BufReader::new(File::open(&active_path)?).lines() {
                let line = line?;
                let line = line.trim();
                if line.is_empty() {
                    continue;
                }
                match serde_json::from_str::<LedgerEventLine>(line) {
                    Ok(event) => ul.apply_event(event),
                    Err(e) => eprintln!("user_ledger: skipping malformed event: {e}"),
                }
            }
        }
        Ok(ul)
    }

    pub fn referenced(&self) -> Referenced {
        Referenced {
            orcids: self
                .owner_pin_orcids
                .iter()
                .chain(self.claims.iter().map(|(_, o, _)| o))
                .chain(self.disowns.iter().map(|(_, o, _)| o))
                .cloned()
                .collect(),
            authors: self.author_merges.iter().map(|(_, _, k)| *k).collect(),
            works: self
                .work_merges
                .iter()
                .map(|(_, _, k)| *k)
                .chain(self.disowns.iter().map(|(_, _, w)| *w))
                .collect(),
            dois: self.claims.iter().map(|(_, _, d)| d.clone()).collect(),
        }
    }

    /// A merge applies iff its keep id is in the snapshot: rewriting an absent drop id is
    /// a no-op, while a merge into an absent keep would erase the drop side. A disown
    /// applies iff its owner and work resolve; a claim is settled later, once the reader
    /// shows who is credited on the work.
    pub fn resolve(self, ids: &SnapshotIds) -> (ResolvedLedger, Outcomes) {
        let mut applied = Vec::new();
        let mut skipped = self.skipped;
        let mut skip = |key: String, reason: SkipReason| skipped.push(SkippedEvent { key, reason });

        let mut author_aliases = HashMap::new();
        for (key, drop, keep) in self.author_merges {
            match ids.authors.contains(&keep) {
                true => {
                    author_aliases.insert(drop, keep);
                    applied.push(key);
                }
                false => skip(key, SkipReason::OaIdNotInDataset),
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

        let mut removed_edges = HashSet::new();
        for (key, orcid, work) in self.disowns {
            let Some(&owner) = ids.orcid_to_oa.get(&orcid) else {
                skip(key, SkipReason::OrcidNotInDataset);
                continue;
            };
            if !ids.works.contains(&work) {
                skip(key, SkipReason::OaIdNotInDataset);
                continue;
            }
            removed_edges.insert((author_root(owner), work_root(work)));
            applied.push(key);
        }

        let mut claims = Vec::new();
        for (key, orcid, doi) in self.claims {
            let Some(&work) = ids.doi_to_work.get(&doi) else {
                skip(key, SkipReason::DoiNotInSnapshot);
                continue;
            };
            let Some(&claimant) = ids.orcid_to_oa.get(&orcid) else {
                skip(key, SkipReason::OrcidNotInDataset);
                continue;
            };
            claims.push(PendingClaim {
                key,
                claimant: author_root(claimant),
                work: work_root(work),
            });
        }
        let pins = self
            .owner_pin_orcids
            .iter()
            .filter_map(|orcid| ids.orcid_to_oa.get(orcid))
            .map(|&a| author_root(a))
            .collect();

        let resolved = ResolvedLedger {
            run_id: self.run_id.clone(),
            author_aliases,
            work_aliases,
            removed_edges,
        };
        let outcomes = Outcomes {
            run_id: self.run_id,
            pins,
            claims,
            applied,
            skipped,
        };
        (resolved, outcomes)
    }

    fn apply_event(&mut self, event: LedgerEventLine) {
        let LedgerEventLine {
            key,
            orcid,
            payload,
        } = event;
        let orcid = normalize_orcid(&orcid);
        let mut skip =
            |key: String, reason: SkipReason| self.skipped.push(SkippedEvent { key, reason });
        match payload {
            EventPayload::MergeAuthors { keep, drop } => match (keep.oa_id, drop.oa_id) {
                (Some(k), Some(d)) if k != d => self.author_merges.push((key, d, k)),
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
            // Resolved in export or never emitted; never present in active.jsonl.
            EventPayload::Revoke
            | EventPayload::ModerationDecision
            | EventPayload::AddPaperRequest => {}
        }
    }
}

impl SnapshotIds {
    /// Two passes over the raw main tables (the reader carries no ledger yet), each
    /// skipped when nothing references that table.
    pub fn scan(stowage: &Stowage, refs: Referenced) -> Self {
        let mut ids = Self::default();
        let refs = Arc::new(refs);
        if !(refs.orcids.is_empty() && refs.authors.is_empty()) {
            let r = Arc::clone(&refs);
            let scanned = par_reduce::<Author, SnapshotIds, _, _>(
                stowage,
                authors::C,
                MAIN_NAME,
                move |acc, a| {
                    let Some(oa_id) = a.get_parsed_id() else {
                        return;
                    };
                    if r.authors.contains(&oa_id) {
                        acc.authors.insert(oa_id);
                    }
                    if let Some(orcid) = a.orcid {
                        let orcid = normalize_orcid(&orcid);
                        if r.orcids.contains(&orcid) {
                            acc.orcid_to_oa.insert(orcid, oa_id);
                        }
                    }
                },
                Self::merge,
                Some(10),
            );
            ids.authors = scanned.authors;
            ids.orcid_to_oa = scanned.orcid_to_oa;
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
        a.orcid_to_oa.extend(b.orcid_to_oa);
        a.authors.extend(b.authors);
        a.works.extend(b.works);
        a.doi_to_work.extend(b.doi_to_work);
    }
}

impl ResolvedLedger {
    pub fn is_empty(&self) -> bool {
        self.author_aliases.is_empty()
            && self.work_aliases.is_empty()
            && self.removed_edges.is_empty()
    }

    pub fn save(&self, ul_dir: &Path) -> io::Result<()> {
        let sorted = |it: Box<dyn Iterator<Item = Edge> + '_>| {
            let mut v: Vec<Edge> = it.collect();
            v.sort_unstable();
            v
        };
        let file = ResolvedLedgerFile {
            run_id: self.run_id.clone(),
            author_aliases: sorted(Box::new(self.author_aliases.iter().map(|(&d, &k)| (d, k)))),
            work_aliases: sorted(Box::new(self.work_aliases.iter().map(|(&d, &k)| (d, k)))),
            removed_edges: sorted(Box::new(self.removed_edges.iter().copied())),
        };
        write_json(&ul_dir.join(RESOLVED_LEDGER), &file)
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
        let file: ResolvedLedgerFile = serde_json::from_str(&raw)
            .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;
        let snapshot_run = read_run_id(ul_dir);
        if file.run_id != snapshot_run {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!(
                    "{RESOLVED_LEDGER} is from run {:?} but the snapshot manifest says {snapshot_run:?} — re-run the filter step",
                    file.run_id
                ),
            ));
        }
        Ok(Self {
            run_id: file.run_id,
            author_aliases: file.author_aliases.into_iter().collect(),
            work_aliases: file.work_aliases.into_iter().collect(),
            removed_edges: file.removed_edges.into_iter().collect(),
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
    let path = ul_dir.join(OWNER_PINS);
    if !path.exists() {
        return Ok(HashSet::new());
    }
    Ok(fs::read_to_string(&path)?
        .lines()
        .map(str::trim)
        .filter(|l| !l.is_empty())
        .map(normalize_orcid)
        .collect())
}

fn normalize_orcid(orcid: &str) -> String {
    orcid.strip_prefix(ORCID_PREF).unwrap_or(orcid).to_string()
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

fn write_json<T: serde::Serialize>(path: &Path, val: &T) -> io::Result<()> {
    serde_json::to_writer_pretty(BufWriter::new(File::create(path)?), val)
        .map_err(|e| io::Error::new(io::ErrorKind::Other, e))
}

#[cfg(test)]
mod tests {
    use super::*;

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
        let event: LedgerEventLine = serde_json::from_str(
            r#"{"key":"x|merge_authors|h","orcid":"x","payload":{"kind":"merge_authors","keep":{"oa_id":10},"drop":{"oa_id":20}}}"#,
        )
        .unwrap();
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
        let event: LedgerEventLine = serde_json::from_str(
            r#"{"key":"0-1|claim_paper|h","orcid":"0-1","payload":{"kind":"claim_paper","work":{"oa_id":null,"doi":"https://doi.org/10.1000/XYZ"}}}"#,
        )
        .unwrap();
        ul.apply_event(event);
        assert_eq!(
            ul.claims,
            vec![(
                "0-1|claim_paper|h".to_string(),
                "0-1".to_string(),
                "10.1000/xyz".to_string()
            )]
        );

        let no_doi: LedgerEventLine = serde_json::from_str(
            r#"{"key":"0-1|claim_paper|h2","orcid":"0-1","payload":{"kind":"claim_paper","work":{"oa_id":5,"doi":null}}}"#,
        )
        .unwrap();
        ul.apply_event(no_doi);
        assert_eq!(ul.skipped.len(), 1);
        assert_eq!(ul.skipped[0].reason, SkipReason::MissingOaIdOrOrcid);
    }

    #[test]
    fn resolve_requires_keep_and_settles_in_keep_space() {
        let mut ul = UserLedger::default();
        for line in [
            r#"{"key":"o|merge_authors|a","orcid":"o","payload":{"kind":"merge_authors","keep":{"oa_id":1},"drop":{"oa_id":2}}}"#,
            r#"{"key":"o|merge_authors|b","orcid":"o","payload":{"kind":"merge_authors","keep":{"oa_id":9},"drop":{"oa_id":3}}}"#,
            r#"{"key":"o|merge_papers|c","orcid":"o","payload":{"kind":"merge_papers","keep":{"oa_id":10,"doi":null},"drop":{"oa_id":11,"doi":null}}}"#,
            r#"{"key":"o|disown_paper|d","orcid":"o","payload":{"kind":"disown_paper","work":{"oa_id":11,"doi":null}}}"#,
            r#"{"key":"o|claim_paper|e","orcid":"o","payload":{"kind":"claim_paper","work":{"oa_id":null,"doi":"10.1/x"}}}"#,
        ] {
            ul.apply_event(serde_json::from_str(line).unwrap());
        }
        ul.owner_pin_orcids.insert("o".into());
        let ids = SnapshotIds {
            orcid_to_oa: [("o".to_string(), 2u64)].into_iter().collect(),
            authors: [1].into_iter().collect(),
            works: [10, 11].into_iter().collect(),
            doi_to_work: [("10.1/x".to_string(), 11u64)].into_iter().collect(),
        };
        let (resolved, outcomes) = ul.resolve(&ids);
        assert_eq!(resolved.author_aliases, [(2, 1)].into_iter().collect());
        assert_eq!(resolved.work_aliases, [(11, 10)].into_iter().collect());
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
