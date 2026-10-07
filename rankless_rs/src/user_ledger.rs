use std::{
    fs::{self, File},
    io::{self, BufRead, BufReader, BufWriter},
    path::Path,
    sync::Arc,
};

use hashbrown::{HashMap, HashSet};
use serde::{Deserialize, Serialize};
use wiretypes::wire;

use crate::{
    common::{ParsedId, Stowage, MAIN_NAME},
    csv_iter::par_reduce,
    csv_writers::{authors, works},
    metrics::WORK_SCREEN,
    oa_structs::{post::Author, Work},
};
use dmove::BigId;

pub const ORCID_PREF: &str = "https://orcid.org/";
/// The derived source's records, written by `derive-ledger` beside the export.
pub const DERIVED_JSONL: &str = "derived.jsonl";
/// The derived source's manifest, written beside its records.
#[wire]
pub const DERIVED_MANIFEST: &str = "derived_manifest.json";
/// The team's curated events, copied beside the site's by `export_user_ledger.py`.
#[wire]
pub const CURATED_JSONL: &str = "curated.jsonl";
/// The site's active events, one per line, as the export writes them.
#[wire]
pub const ACTIVE_JSONL: &str = "active.jsonl";
/// The export's run id, event ids and events per source.
#[wire]
pub const SNAPSHOT_MANIFEST: &str = "snapshot_manifest.json";
/// The pinned owners' ORCIDs, one per line.
#[wire]
pub const OWNER_PINS: &str = "owner_pins.txt";
/// What the filter step applied and skipped of the ledger, read by the site.
#[wire]
pub const APPLIED_MANIFEST: &str = "applied_manifest.json";
/// The filter step's private sidecar: the forced œuvre's aggregates and forced-only work ids.
#[wire]
pub const FORCED_WORKS: &str = "forced_works.json";

const RESOLVED_LEDGER: &str = "resolved_ledger.json";
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
// Cross-language boundary: the events of `ACTIVE_JSONL`. The `#[wire]` types below generate the
// site's and Python's definitions (docs/type-generation.md).
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
    /// (key, orcid, the work as the claim names it, forced: a curated claim)
    claims: Vec<(String, String, ClaimedWork, bool)>,
    /// (key, orcid, work oa_id)
    disowns: Vec<(String, String, BigId)>,
    /// (key, author oa_id, fate) in source order, the derived records, then the curated events,
    /// then the site's, so the last entry on a record decides
    author_fates: Vec<(Key, BigId, Fate)>,
    /// (key, drop oa_id, the merge into its keep) in source order
    work_merges: Vec<(Key, BigId, Fate)>,
    /// (key, work oa_id, the author the row is taken from, the author it goes to)
    reassigns: Vec<(String, BigId, BigId, Option<BigId>)>,
    /// (key, author oa_id, display name) in source order
    names: Vec<(Key, BigId, String)>,
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
    /// every work record carrying a referenced DOI, with its citation count
    pub doi_works: HashMap<String, Vec<(BigId, u64)>>,
}

/// The tables the CSV reader applies to every row it yields (`csv_iter`): merged ids read as
/// their keep id, drop-side main rows and disowned authorships do not exist, a reassigned
/// authorship names its new author or none, a granted authorship has a row, a stripped author
/// carries no ORCID, a keep author carries its merged records' counts, a renamed author its
/// name. Written by the filter step, loaded by every later one.
#[derive(Clone, Default)]
pub struct ResolvedLedger {
    pub run_id: String,
    /// drop oa_id -> keep oa_id, path-compressed
    pub author_aliases: HashMap<BigId, BigId>,
    pub work_aliases: HashMap<BigId, BigId>,
    /// (author oa_id, work oa_id) in keep-id space
    pub removed_edges: HashSet<Edge>,
    /// the authorship rows that name another author, or none, in keep-id space
    pub reassigned: HashMap<Edge, Option<BigId>>,
    /// the forced claims' authorships the snapshot lacks, in keep-id space
    pub granted_ships: Vec<GrantedShip>,
    pub stripped_orcids: HashSet<BigId>,
    /// keep oa_id -> its own counts plus every merged record's
    pub author_counts: HashMap<BigId, Counts>,
    /// author oa_id -> the display name it reads with, in keep-id space
    pub author_names: HashMap<BigId, String>,
}

/// Everything the filter step still needs after resolution: the pinned owners whose
/// œuvre is forced, the events that are settled against the authorship rows, and the
/// decided keys.
pub struct Outcomes {
    pub run_id: String,
    /// Owner oa_ids in keep-id space
    pub pins: HashSet<BigId>,
    pub claims: Vec<PendingClaim>,
    /// Merge keeps whose records are each within `WORK_SCREEN.max_author_papers`: their counts
    /// sum one person's records, so step 20's bound does not apply to them.
    pub bound_exempt: HashSet<BigId>,
    /// the disowns and reassignments, each applied when its row exists
    takings: Vec<PendingTaking>,
    report: Report,
}

/// A claim applies once the reader shows the claimant credited on a record of the work. A
/// forced one, which the curated ledger makes, is granted a row where the applied ledger leaves
/// the claimant on no record of it (`Outcomes::grants`), and its paper rides through the
/// screens; a site claim is a status line.
pub struct PendingClaim {
    pub key: String,
    pub claimant: BigId,
    /// the claimed work's records in keep-id space, the most cited first
    pub works: Vec<BigId>,
    pub forced: bool,
}

/// An event that takes an authorship row off an author.
struct PendingTaking {
    key: String,
    edge: Edge,
}

/// The events decided so far, by logical key.
#[derive(Default)]
struct Report {
    applied: Vec<String>,
    skipped: Vec<SkippedEvent>,
}

/// An authorship the ledger adds: a forced claimant's row on the claimed work, placed after
/// the rows the snapshot lists, with no affiliation.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct GrantedShip {
    pub author: BigId,
    pub work: BigId,
    pub position: u16,
}

/// The records' fates as settled: the aliases are acyclic and path-compressed.
struct Settled {
    aliases: HashMap<BigId, BigId>,
    stripped: HashSet<BigId>,
    /// records whose derived or stripping fate a later entry replaced: the ORCID on their row
    /// is not theirs, whatever became of them
    unclaimed: HashSet<BigId>,
}

#[wire]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkippedEvent {
    pub key: String,
    pub reason: SkipReason,
}

/// A work as a ledger event names it, written by the site and by `pyscripts/ledger_ids.py`. The
/// pipeline reads `oa_id` and `doi`, so a line carrying only those parses.
#[wire]
#[derive(Serialize, Deserialize)]
pub struct WorkSubject {
    pub oa_id: Option<BigId>,
    pub doi: Option<String>,
    pub dm_id_at_creation: Option<usize>,
    pub semantic_id_at_creation: Option<String>,
    pub run_id_at_creation: Option<String>,
    #[serde(default)]
    pub display_snapshot: WorkSnapshot,
}

/// An author record as a ledger event names it; the pipeline reads `oa_id`.
#[wire]
#[derive(Serialize, Deserialize)]
pub struct AuthorSubject {
    pub oa_id: Option<BigId>,
    pub orcid: Option<String>,
    pub dm_id_at_creation: Option<usize>,
    pub semantic_id_at_creation: Option<String>,
    pub run_id_at_creation: Option<String>,
    #[serde(default)]
    pub display_snapshot: AuthorSnapshot,
}

/// What the claimant saw of a work when creating the event.
#[wire]
#[derive(Serialize, Deserialize, Default)]
pub struct WorkSnapshot {
    pub title: String,
    pub year: Option<u16>,
}

#[wire]
#[derive(Serialize, Deserialize, Default)]
pub struct AuthorSnapshot {
    pub display_name: String,
}

/// `APPLIED_MANIFEST`, read by the site: what the run applied and why it skipped the rest,
/// events named by their logical key.
#[wire]
#[derive(Serialize)]
pub struct AppliedManifest {
    pub run_id: String,
    pub snapshot_at: String,
    pub applied_keys: Vec<String>,
    pub skipped: Vec<SkippedEvent>,
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
    reassigned: Vec<(Edge, Option<BigId>)>,
    granted_ships: Vec<GrantedShip>,
    stripped_orcids: Vec<BigId>,
    author_counts: Vec<(BigId, Counts)>,
    author_names: Vec<(BigId, String)>,
}

// ---------------------------------------------------------------------------

#[wire]
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SkipReason {
    MissingOaId,
    MissingOaIdOrOrcid,
    OrcidNotInDataset,
    OaIdNotInDataset,
    DoiNotInSnapshot,
    ClaimantNotAttributed,
    /// the author has no row on the work to disown or reassign
    AuthorNotOnWork,
    /// the claimed work does not pass the screens, so the claimant's row is not served
    WorkScreened,
    /// a later event decides the same record or row
    Superseded,
    /// the keep already merges into the drop
    MergeCycle,
}

/// What a ledger event does, as the site stores it and `ACTIVE_JSONL` carries it; `kind` is the
/// tag.
#[wire]
#[derive(Serialize, Deserialize)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum EventPayload {
    MergeAuthors {
        keep: AuthorSubject,
        drop: AuthorSubject,
        #[serde(skip_serializing_if = "Option::is_none")]
        note: Option<String>,
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
    /// The work's authorship row on `author` is another person's: it reads as `to`'s, or as an
    /// unresolved row when no record is named. Names records by OpenAlex id, so it needs no
    /// ORCID; written by the curated ledger only.
    ReassignPaper {
        work: WorkSubject,
        author: AuthorSubject,
        #[serde(default, skip_serializing_if = "Option::is_none")]
        to: Option<AuthorSubject>,
    },
    /// The record reads with this display name; written by the derived and the curated ledger.
    NameAuthor {
        author: AuthorSubject,
        name: String,
    },
    // The last three never reach the pipeline: revokes resolve away in export_user_ledger.py
    // and the other two are never written to the ledger.
    Revoke {
        /// The revoked event's logical key, which a DB merge leaves stable (an event_id is
        /// renumbered).
        target_key: String,
        #[serde(skip_serializing_if = "Option::is_none")]
        reason: Option<String>,
    },
    ModerationDecision {
        target_event_id: i64,
        decision: ModerationVerdict,
        #[serde(skip_serializing_if = "Option::is_none")]
        reason: Option<String>,
    },
    AddPaperRequest {
        work_claim: serde_json::Map<String, serde_json::Value>,
    },
}

#[wire]
#[derive(Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ModerationVerdict {
    Accepted,
    Rejected,
}

/// What the ledger does to an author or a work record.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Fate {
    /// merged into the keep
    Merge(BigId),
    /// its `orcid` cell reads empty
    Strip,
}

/// A work as a claim names it: by its DOI, which several records may carry, and by the record
/// the claimant saw, which stands for the paper when the snapshot has the DOI on none.
#[derive(Debug, PartialEq, Eq)]
struct ClaimedWork {
    doi: Option<String>,
    record: Option<BigId>,
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
            ul.apply_curated(serde_json::from_str(&line).map_err(invalid)?);
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
        let merged = |fates: &[(Key, BigId, Fate)]| -> Vec<BigId> {
            fates
                .iter()
                .flat_map(|&(_, id, fate)| match fate {
                    Fate::Merge(keep) => vec![id, keep],
                    Fate::Strip => vec![],
                })
                .collect()
        };
        let keyed_names = self.names.iter().filter(|(key, ..)| key.is_some());
        Referenced {
            orcids: self.owner_pin_orcids.union(&self.orcids).cloned().collect(),
            authors: merged(&self.author_fates)
                .into_iter()
                .chain(
                    self.reassigns
                        .iter()
                        .flat_map(|&(_, _, from, to)| [Some(from), to])
                        .flatten(),
                )
                .chain(keyed_names.map(|(_, id, _)| *id))
                .collect(),
            works: merged(&self.work_merges)
                .into_iter()
                .chain(self.disowns.iter().map(|(_, _, w)| *w))
                .chain(self.reassigns.iter().map(|(_, w, ..)| *w))
                .chain(self.claims.iter().filter_map(|(_, _, c, _)| c.record))
                .collect(),
            dois: self
                .claims
                .iter()
                .filter_map(|(_, _, c, _)| c.doi.clone())
                .collect(),
            derived_rows: self.derived_rows,
        }
    }

    /// A merge applies iff its keep id is in the snapshot: rewriting an absent drop id is
    /// a no-op, while a merge into an absent keep would erase the drop side. The last such
    /// fate recorded on a record decides, so a user's event replaces a derived record's, and a
    /// merge that would close a cycle is refused. A disown or a reassignment is recorded once
    /// its ids resolve and a claim once its work and claimant do; all three are settled later,
    /// against the authorship rows (`Outcomes`). Fails on a stale derived file and when an ORCID
    /// would still resolve to more than one author.
    pub fn resolve(self, ids: &SnapshotIds) -> io::Result<(ResolvedLedger, Outcomes)> {
        if let Some(rows) = self.derived_rows {
            if rows != ids.author_rows {
                return Err(invalid(format!(
                    "{DERIVED_JSONL} was derived from {rows} author rows, the CSVs hold {} — rerun derive-ledger",
                    ids.author_rows
                )));
            }
        }
        let mut report = Report {
            applied: Vec::new(),
            skipped: self.skipped,
        };
        let authors = settle(
            self.author_fates,
            |a| ids.authors.contains_key(&a),
            &mut report,
        )?;
        let works = settle(self.work_merges, |w| ids.works.contains(&w), &mut report)?;
        let (author_aliases, work_aliases) = (authors.aliases, works.aliases);
        let author_root = |a: BigId| author_aliases.get(&a).copied().unwrap_or(a);
        let work_root = |w: BigId| work_aliases.get(&w).copied().unwrap_or(w);
        // An unclaimed record that stays a record of its own shows no ORCID either.
        let mut stripped_orcids = authors.stripped;
        stripped_orcids.extend(
            authors
                .unclaimed
                .iter()
                .filter(|a| !author_aliases.contains_key(*a)),
        );

        let within_bound = |a: &BigId| {
            ids.authors
                .get(a)
                .map_or(true, |&(works, _)| works <= WORK_SCREEN.max_author_papers)
        };
        let mut author_counts: HashMap<BigId, Counts> = HashMap::new();
        let mut over_bound = HashSet::new();
        for (&drop, &keep) in &author_aliases {
            let total = author_counts
                .entry(keep)
                .or_insert_with(|| ids.authors.get(&keep).copied().unwrap_or_default());
            if let Some(&(works, cites)) = ids.authors.get(&drop) {
                total.0 = total.0.saturating_add(works);
                total.1 = total.1.saturating_add(cites);
            }
            if !(within_bound(&drop) && within_bound(&keep)) {
                over_bound.insert(keep);
            }
        }
        let bound_exempt = author_counts
            .keys()
            .filter(|k| !over_bound.contains(*k))
            .copied()
            .collect();

        let mut orcid_to_oa = HashMap::new();
        for (orcid, carriers) in &ids.orcid_carriers {
            // A stripped keep does not own the ORCID through the records merged into it.
            let mut owners: Vec<BigId> = carriers
                .iter()
                .filter(|&c| !stripped_orcids.contains(c) && !authors.unclaimed.contains(c))
                .map(|&c| author_root(c))
                .filter(|root| !(stripped_orcids.contains(root) && carriers.contains(root)))
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

        let mut takings = Vec::new();
        let mut removed_edges = HashSet::new();
        for (key, orcid, work) in self.disowns {
            let Some(&owner) = orcid_to_oa.get(&orcid) else {
                report.skip(key, SkipReason::OrcidNotInDataset);
                continue;
            };
            if !ids.works.contains(&work) {
                report.skip(key, SkipReason::OaIdNotInDataset);
                continue;
            }
            let edge = (owner, work_root(work));
            removed_edges.insert(edge);
            takings.push(PendingTaking { key, edge });
        }
        let mut reassigning: HashMap<Edge, (String, Option<BigId>)> = HashMap::new();
        for (key, work, from, to) in self.reassigns {
            if !ids.works.contains(&work) || to.is_some_and(|t| !ids.authors.contains_key(&t)) {
                report.skip(key, SkipReason::OaIdNotInDataset);
                continue;
            }
            let edge = (author_root(from), work_root(work));
            if let Some((earlier, _)) = reassigning.insert(edge, (key, to.map(author_root))) {
                report.skip(earlier, SkipReason::Superseded);
            }
        }
        let mut reassigned = HashMap::new();
        for (edge, (key, to)) in reassigning {
            reassigned.insert(edge, to);
            takings.push(PendingTaking { key, edge });
        }

        let mut claims = Vec::new();
        for (key, orcid, claimed, forced) in self.claims {
            let by_doi = claimed.doi.as_ref().and_then(|doi| ids.doi_works.get(doi));
            let mut records: Vec<(BigId, u64)> = match (by_doi, claimed.record) {
                (Some(records), _) => records.clone(),
                (None, Some(w)) if ids.works.contains(&w) => vec![(w, 0)],
                (None, _) => {
                    let reason = match claimed.doi {
                        Some(_) => SkipReason::DoiNotInSnapshot,
                        None => SkipReason::OaIdNotInDataset,
                    };
                    report.skip(key, reason);
                    continue;
                }
            };
            let Some(&claimant) = orcid_to_oa.get(&orcid) else {
                report.skip(key, SkipReason::OrcidNotInDataset);
                continue;
            };
            records.sort_unstable_by_key(|&(w, cites)| (std::cmp::Reverse(cites), w));
            let mut works: Vec<BigId> = Vec::with_capacity(records.len());
            for (w, _) in records {
                let root = work_root(w);
                if !works.contains(&root) {
                    works.push(root);
                }
            }
            claims.push(PendingClaim {
                key,
                claimant,
                works,
                forced,
            });
        }

        let mut naming: HashMap<BigId, (Key, String)> = HashMap::new();
        for (key, author, name) in self.names {
            match key {
                Some(key) if !ids.authors.contains_key(&author) => {
                    report.skip(key, SkipReason::OaIdNotInDataset);
                    continue;
                }
                _ => {}
            }
            if let Some((Some(earlier), _)) = naming.insert(author_root(author), (key, name)) {
                report.skip(earlier, SkipReason::Superseded);
            }
        }
        let mut author_names = HashMap::new();
        for (author, (key, name)) in naming {
            report.applied.extend(key);
            author_names.insert(author, name);
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
            reassigned,
            granted_ships: Vec::new(),
            stripped_orcids,
            author_counts,
            author_names,
        };
        let outcomes = Outcomes {
            run_id: self.run_id,
            pins,
            claims,
            bound_exempt,
            takings,
            report,
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
            EventPayload::MergeAuthors { keep, drop, .. } => match (keep.oa_id, drop.oa_id) {
                (Some(k), Some(d)) if k != d => {
                    self.author_fates.push((Some(key), d, Fate::Merge(k)))
                }
                _ => skip(key, SkipReason::MissingOaId),
            },
            EventPayload::MergePapers { keep, drop } => match (keep.oa_id, drop.oa_id) {
                (Some(k), Some(d)) if k != d => {
                    self.work_merges.push((Some(key), d, Fate::Merge(k)))
                }
                _ => skip(key, SkipReason::MissingOaId),
            },
            EventPayload::DisownPaper { work } => match work.oa_id {
                Some(w) if !orcid.is_empty() => self.disowns.push((key, orcid, w)),
                _ => skip(key, SkipReason::MissingOaIdOrOrcid),
            },
            EventPayload::ClaimPaper { work } => match (work.doi, work.oa_id) {
                (None, None) => skip(key, SkipReason::MissingOaIdOrOrcid),
                _ if orcid.is_empty() => skip(key, SkipReason::MissingOaIdOrOrcid),
                (doi, record) => {
                    let doi = doi.as_deref().map(canonical_doi);
                    self.claims
                        .push((key, orcid, ClaimedWork { doi, record }, false))
                }
            },
            EventPayload::StripOrcid { author } => match author.oa_id {
                Some(a) => self.author_fates.push((Some(key), a, Fate::Strip)),
                None => skip(key, SkipReason::MissingOaId),
            },
            EventPayload::ReassignPaper { work, author, to } => {
                match (work.oa_id, author.oa_id, to.map(|t| t.oa_id)) {
                    (Some(_), Some(_), Some(None)) => skip(key, SkipReason::MissingOaId),
                    (Some(w), Some(f), to) if to.flatten() != Some(f) => {
                        self.reassigns.push((key, w, f, to.flatten()))
                    }
                    _ => skip(key, SkipReason::MissingOaId),
                }
            }
            EventPayload::NameAuthor { author, name } => match author.oa_id {
                Some(a) if !name.trim().is_empty() => {
                    self.names.push((Some(key), a, name.trim().to_string()))
                }
                _ => skip(key, SkipReason::MissingOaId),
            },
            // Resolved in export or never emitted; never present in `ACTIVE_JSONL`.
            EventPayload::Revoke { .. }
            | EventPayload::ModerationDecision { .. }
            | EventPayload::AddPaperRequest { .. } => {}
        }
    }

    /// A curated event: the team's word, so its claim is forced.
    fn apply_curated(&mut self, event: LedgerEventLine) {
        let claims = self.claims.len();
        self.apply_event(event);
        if let Some(claim) = self.claims.get_mut(claims) {
            claim.3 = true;
        }
    }

    /// A derived line is machine-written: anything but a complete author or paper merge, strip
    /// or name is an error.
    fn apply_derived(&mut self, event: LedgerEventLine) -> io::Result<()> {
        match event.payload {
            EventPayload::MergeAuthors {
                keep: AuthorSubject { oa_id: Some(k), .. },
                drop: AuthorSubject { oa_id: Some(d), .. },
                ..
            } if k != d => self.author_fates.push((None, d, Fate::Merge(k))),
            EventPayload::MergePapers {
                keep: WorkSubject { oa_id: Some(k), .. },
                drop: WorkSubject { oa_id: Some(d), .. },
            } if k != d => self.work_merges.push((None, d, Fate::Merge(k))),
            EventPayload::StripOrcid {
                author: AuthorSubject { oa_id: Some(a), .. },
            } => self.author_fates.push((None, a, Fate::Strip)),
            EventPayload::NameAuthor {
                author: AuthorSubject { oa_id: Some(a), .. },
                name,
            } if !name.is_empty() => self.names.push((None, a, name)),
            _ => {
                return Err(invalid(format!(
                    "{DERIVED_JSONL}: {} is not a complete author or paper merge, strip or name",
                    event.key
                )))
            }
        }
        let orcid = normalize_orcid(&event.orcid);
        if !orcid.is_empty() {
            self.orcids.insert(orcid);
        }
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
                            let cites = w.cited_by_count.unwrap_or(0);
                            acc.doi_works.entry(doi).or_default().push((oa_id, cites));
                        }
                    }
                },
                Self::merge,
                Some(10),
            );
            ids.works = scanned.works;
            ids.doi_works = scanned.doi_works;
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
        for (doi, works) in b.doi_works {
            a.doi_works.entry(doi).or_default().extend(works);
        }
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
            && self.reassigned.is_empty()
            && self.granted_ships.is_empty()
            && self.stripped_orcids.is_empty()
            && self.author_counts.is_empty()
            && self.author_names.is_empty()
    }

    /// Who an authorship row in keep-id space reads as: `None` when the row does not exist
    /// under the ledger, else the author it names, if any.
    pub fn row_author(&self, edge: Edge) -> Option<Option<BigId>> {
        if self.removed_edges.contains(&edge) {
            return None;
        }
        Some(self.reassigned.get(&edge).copied().unwrap_or(Some(edge.0)))
    }

    /// `seen`: authorship rows as the merges alone leave them. Returns them as the whole ledger
    /// reads them.
    pub fn credit(&self, seen: &HashSet<Edge>) -> HashSet<Edge> {
        seen.iter()
            .filter_map(|&e| Some((self.row_author(e)??, e.1)))
            .collect()
    }

    /// The ledger with every authorship row still on the author the merges leave it with: what
    /// the events that take or grant a row are settled against.
    pub fn merges_only(&self) -> Self {
        Self {
            removed_edges: HashSet::new(),
            reassigned: HashMap::new(),
            granted_ships: Vec::new(),
            ..self.clone()
        }
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
            reassigned: sorted(self.reassigned.iter().map(|(&e, &to)| (e, to))),
            granted_ships: self.granted_ships.clone(),
            stripped_orcids: sorted(self.stripped_orcids.iter().copied()),
            author_counts: sorted(self.author_counts.iter().map(|(&a, &c)| (a, c))),
            author_names: sorted(self.author_names.iter().map(|(&a, n)| (a, n.clone()))),
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
            reassigned: file.reassigned.into_iter().collect(),
            granted_ships: file.granted_ships,
            stripped_orcids: file.stripped_orcids.into_iter().collect(),
            author_counts: file.author_counts.into_iter().collect(),
            author_names: file.author_names.into_iter().collect(),
        })
    }
}

impl Outcomes {
    /// The authors whose authorship rows force an œuvre or settle an event.
    pub fn watched(&self, resolved: &ResolvedLedger) -> HashSet<BigId> {
        self.pins
            .iter()
            .copied()
            .chain(self.claims.iter().map(|c| c.claimant))
            .chain(self.takings.iter().map(|t| t.edge.0))
            .chain(resolved.reassigned.values().flatten().copied())
            .collect()
    }

    /// Every record of the claimed works.
    pub fn claimed_works(&self) -> HashSet<BigId> {
        self.claims
            .iter()
            .flat_map(|c| c.works.iter().copied())
            .collect()
    }

    /// The authorships that settle the forced claims `credited` leaves open, in key order: a
    /// claimant on no record of the work gets a row on its most cited one that they did not
    /// disown, after the rows it has (`rows`: the row count of every claimed record).
    pub fn grants(
        &self,
        credited: &HashSet<Edge>,
        removed: &HashSet<Edge>,
        rows: &HashMap<BigId, u16>,
    ) -> Vec<GrantedShip> {
        let mut open: Vec<&PendingClaim> = self
            .claims
            .iter()
            .filter(|c| c.forced && !c.works.iter().any(|w| credited.contains(&(c.claimant, *w))))
            .collect();
        open.sort_unstable_by(|a, b| a.key.cmp(&b.key));
        let mut next = rows.clone();
        let mut seen: HashSet<Edge> = HashSet::new();
        let mut granted = Vec::new();
        for claim in open {
            let kept = |w: &&BigId| !removed.contains(&(claim.claimant, **w));
            let Some(&work) = claim.works.iter().find(kept) else {
                continue;
            };
            if !seen.insert((claim.claimant, work)) {
                continue;
            }
            let position = next.entry(work).or_default();
            granted.push(GrantedShip {
                author: claim.claimant,
                work,
                position: *position,
            });
            *position = position.saturating_add(1);
        }
        granted
    }

    /// The record each forced claim credits its claimant on, the most cited: it rides through
    /// the screens like a pinned owner's œuvre. `credited` holds the granted rows.
    pub fn forced_claim_works<'a>(
        &'a self,
        credited: &'a HashSet<Edge>,
    ) -> impl Iterator<Item = BigId> + 'a {
        self.claims.iter().filter(|c| c.forced).filter_map(|c| {
            let credits = |w: &&BigId| credited.contains(&(c.claimant, **w));
            c.works.iter().find(credits).copied()
        })
    }

    /// `seen`: the watched authors' rows under the merges alone, which a disown or a
    /// reassignment needs one of; `credited`: their rows under the whole ledger, the granted
    /// ones among them, which a claim needs one of; `served`: the claimed records that pass the
    /// screens.
    pub fn manifest(
        &self,
        seen: &HashSet<Edge>,
        credited: &HashSet<Edge>,
        served: &HashSet<BigId>,
    ) -> AppliedManifest {
        let mut report = Report {
            applied: self.report.applied.clone(),
            skipped: self.report.skipped.clone(),
        };
        for taking in &self.takings {
            match seen.contains(&taking.edge) {
                true => report.applied.push(taking.key.clone()),
                false => report.skip(taking.key.clone(), SkipReason::AuthorNotOnWork),
            }
        }
        for claim in &self.claims {
            let mut on = claim
                .works
                .iter()
                .filter(|w| credited.contains(&(claim.claimant, **w)))
                .peekable();
            if on.peek().is_none() {
                report.skip(claim.key.clone(), SkipReason::ClaimantNotAttributed);
            } else if on.any(|w| served.contains(w)) {
                report.applied.push(claim.key.clone());
            } else {
                report.skip(claim.key.clone(), SkipReason::WorkScreened);
            }
        }
        let Report {
            mut applied,
            mut skipped,
        } = report;
        applied.sort_unstable();
        applied.dedup();
        skipped.sort_unstable_by(|a, b| a.key.cmp(&b.key));
        AppliedManifest {
            run_id: self.run_id.clone(),
            snapshot_at: self.run_id.clone(),
            applied_keys: applied,
            skipped,
        }
    }
}

impl AppliedManifest {
    pub fn write(&self, ul_dir: &Path) -> io::Result<()> {
        println!(
            "{APPLIED_MANIFEST}: {} applied, {} skipped",
            self.applied_keys.len(),
            self.skipped.len()
        );
        write_json(&ul_dir.join(APPLIED_MANIFEST), self)
    }
}

impl Report {
    fn skip(&mut self, key: String, reason: SkipReason) {
        self.skipped.push(SkippedEvent { key, reason });
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

/// Decides each record's fate from the entries in source order: the last entry whose keep
/// exists decides and supersedes the earlier ones, and a merge whose keep already merges into
/// its drop is refused, so the aliases hold no cycle. An entry without a key is machine-written
/// and fails the run where a keyed one is skipped.
fn settle(
    fates: Vec<(Key, BigId, Fate)>,
    exists: impl Fn(BigId) -> bool,
    report: &mut Report,
) -> io::Result<Settled> {
    let refused = |id: BigId, why: &str| invalid(format!("{DERIVED_JSONL}: record {id} {why}"));
    let mut deciding: HashMap<BigId, usize> = HashMap::new();
    let mut unclaimed = HashSet::new();
    for (i, (key, id, fate)) in fates.iter().enumerate() {
        if matches!(fate, Fate::Merge(keep) if !exists(*keep)) {
            match key {
                Some(key) => report.skip(key.clone(), SkipReason::OaIdNotInDataset),
                None => return Err(refused(*id, "merges into a record the CSVs lack")),
            }
            continue;
        }
        if let Some(earlier) = deciding.insert(*id, i) {
            let (earlier_key, _, earlier_fate) = &fates[earlier];
            if earlier_key.is_none() || *earlier_fate == Fate::Strip {
                unclaimed.insert(*id);
            }
            if let Some(key) = earlier_key {
                report.skip(key.clone(), SkipReason::Superseded);
            }
        }
    }
    let mut aliases = HashMap::new();
    let mut stripped = HashSet::new();
    for (i, (key, id, fate)) in fates.into_iter().enumerate() {
        if deciding.get(&id) != Some(&i) {
            continue;
        }
        let cycle = match fate {
            Fate::Strip => {
                stripped.insert(id);
                false
            }
            Fate::Merge(keep) if find_root(keep, &aliases) == id => true,
            Fate::Merge(keep) => {
                aliases.insert(id, keep);
                false
            }
        };
        match (key, cycle) {
            (Some(key), false) => report.applied.push(key),
            (Some(key), true) => report.skip(key, SkipReason::MergeCycle),
            (None, false) => {}
            (None, true) => return Err(refused(id, "merges into a record merged into it")),
        }
    }
    path_compress(&mut aliases);
    Ok(Settled {
        aliases,
        stripped,
        unclaimed,
    })
}

/// Terminates on an acyclic map only.
fn find_root(id: BigId, map: &HashMap<BigId, BigId>) -> BigId {
    let mut cur = id;
    while let Some(&next) = map.get(&cur) {
        cur = next;
    }
    cur
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
                keep: AuthorSubject {
                    oa_id: Some(10),
                    ..
                },
                drop: AuthorSubject {
                    oa_id: Some(20),
                    ..
                },
                ..
            }
        ));
    }

    #[test]
    fn claim_paper_collects_canonical_doi() {
        let mut ul = UserLedger::default();
        ul.apply_event(line(
            r#"{"key":"0-1|claim_paper|h","orcid":"0-1","payload":{"kind":"claim_paper","work":{"oa_id":null,"doi":"https://doi.org/10.1000/XYZ"}}}"#,
        ));
        // a paper without a DOI is claimed as its record, one without either is not a claim; a
        // curated claim is forced
        ul.apply_curated(line(
            r#"{"key":"0-1|claim_paper|h2","orcid":"0-1","payload":{"kind":"claim_paper","work":{"oa_id":5,"doi":null}}}"#,
        ));
        let claim = |key: &str, doi: Option<&str>, record, forced| {
            let doi = doi.map(str::to_string);
            let work = ClaimedWork { doi, record };
            (key.to_string(), "0-1".to_string(), work, forced)
        };
        assert_eq!(
            ul.claims,
            vec![
                claim("0-1|claim_paper|h", Some("10.1000/xyz"), None, false),
                claim("0-1|claim_paper|h2", None, Some(5), true)
            ]
        );
        ul.apply_event(line(
            r#"{"key":"0-1|claim_paper|h3","orcid":"0-1","payload":{"kind":"claim_paper","work":{"oa_id":null,"doi":null}}}"#,
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
            doi_works: [("10.1/x".to_string(), vec![(11, 3)])]
                .into_iter()
                .collect(),
        };
        let (resolved, outcomes) = ul.resolve(&ids).unwrap();
        assert_eq!(resolved.author_aliases, [(2, 1)].into_iter().collect());
        assert_eq!(resolved.work_aliases, [(11, 10)].into_iter().collect());
        // the keep row carries both records' counts, each within the work bound
        assert_eq!(resolved.author_counts, [(1, (7, 70))].into_iter().collect());
        assert_eq!(outcomes.bound_exempt, [1].into_iter().collect());
        // the owner's own id and the disowned work both read in keep space
        assert_eq!(resolved.removed_edges, [(1, 10)].into_iter().collect());
        assert_eq!(outcomes.pins, [1].into_iter().collect());
        assert_eq!(outcomes.claims.len(), 1);
        assert_eq!(outcomes.claims[0].claimant, 1);
        assert_eq!(outcomes.claims[0].works, vec![10]);
        // the two merges; the disown and the claim wait for the authorship rows
        assert_eq!(outcomes.report.applied.len(), 2);
        assert_eq!(outcomes.takings.len(), 1);
        assert_eq!(outcomes.report.skipped.len(), 1);
        assert_eq!(outcomes.report.skipped[0].key, "o|merge_authors|b");
    }

    fn merge(key: &str, keep: BigId, drop: BigId) -> LedgerEventLine {
        line(&format!(
            r#"{{"key":"{key}","orcid":"o","payload":{{"kind":"merge_authors","keep":{{"oa_id":{keep}}},"drop":{{"oa_id":{drop}}}}}}}"#
        ))
    }

    fn skips(outcomes: &Outcomes) -> Vec<(&str, SkipReason)> {
        let mut skipped: Vec<(&str, SkipReason)> = outcomes
            .report
            .skipped
            .iter()
            .map(|s| (s.key.as_str(), s.reason.clone()))
            .collect();
        skipped.sort_unstable_by_key(|(key, _)| *key);
        skipped
    }

    #[test]
    fn a_merge_into_its_own_drop_is_refused_and_an_earlier_event_on_a_record_is_superseded() {
        let mut ul = UserLedger::default();
        // the derived source keeps 1; a user's event from before it kept 2
        ul.apply_derived(merge("d", 1, 2)).unwrap();
        ul.derived_rows = Some(4);
        ul.apply_event(merge("cycle", 2, 1));
        ul.apply_event(merge("first", 1, 3));
        ul.apply_event(merge("last", 2, 3));
        let ids = SnapshotIds {
            orcid_carriers: carriers(&[("o", &[1, 2])]),
            authors: counts(&[1, 2, 3]),
            author_rows: 4,
            ..Default::default()
        };
        let (resolved, outcomes) = ul.resolve(&ids).unwrap();
        assert_eq!(
            resolved.author_aliases,
            [(2, 1), (3, 1)].into_iter().collect()
        );
        assert_eq!(outcomes.report.applied, vec!["last"]);
        assert_eq!(
            skips(&outcomes),
            vec![
                ("cycle", SkipReason::MergeCycle),
                ("first", SkipReason::Superseded)
            ]
        );
    }

    #[test]
    fn a_record_an_event_takes_from_its_derived_fate_holds_no_claim_on_the_orcid() {
        let mut ul = UserLedger::default();
        // of the ORCID's records the derived source merges 2 into 1 and strips 3; the curated
        // events say 2 and 3 are another person, 9
        ul.apply_derived(merge("d", 1, 2)).unwrap();
        ul.apply_derived(line(
            r#"{"key":"3|strip_orcid|","orcid":"o","payload":{"kind":"strip_orcid","author":{"oa_id":3}}}"#,
        ))
        .unwrap();
        ul.derived_rows = Some(5);
        ul.apply_event(merge("moved", 9, 2));
        ul.apply_event(merge("was-stripped", 9, 3));
        // a merge whose keep the snapshot lacks leaves the derived fate in place
        ul.apply_event(merge("ghost", 77, 2));
        ul.owner_pin_orcids.insert("o".into());
        let ids = SnapshotIds {
            orcid_carriers: carriers(&[("o", &[1, 2, 3])]),
            authors: counts(&[1, 2, 3, 9]),
            author_rows: 5,
            ..Default::default()
        };
        let (resolved, outcomes) = ul.resolve(&ids).unwrap();
        assert_eq!(
            resolved.author_aliases,
            [(2, 9), (3, 9)].into_iter().collect()
        );
        assert_eq!(outcomes.pins, [1].into_iter().collect());
        assert_eq!(
            skips(&outcomes),
            vec![("ghost", SkipReason::OaIdNotInDataset)]
        );
    }

    #[test]
    fn a_stripped_keep_does_not_own_the_orcid_through_its_merged_records() {
        let mut ul = UserLedger::default();
        ul.apply_derived(merge("d", 1, 2)).unwrap();
        ul.derived_rows = Some(2);
        ul.apply_event(line(
            r#"{"key":"s","orcid":"o","payload":{"kind":"strip_orcid","author":{"oa_id":1}}}"#,
        ));
        ul.owner_pin_orcids.insert("o".into());
        let ids = SnapshotIds {
            orcid_carriers: carriers(&[("o", &[1, 2])]),
            authors: counts(&[1, 2]),
            author_rows: 2,
            ..Default::default()
        };
        let (resolved, outcomes) = ul.resolve(&ids).unwrap();
        assert_eq!(resolved.stripped_orcids, [1].into_iter().collect());
        assert!(outcomes.pins.is_empty());
    }

    #[test]
    fn two_work_merges_on_one_drop_and_a_work_cycle() {
        let mut ul = UserLedger::default();
        for l in [
            r#"{"key":"a","orcid":"o","payload":{"kind":"merge_papers","keep":{"oa_id":10,"doi":null},"drop":{"oa_id":11,"doi":null}}}"#,
            r#"{"key":"b","orcid":"o","payload":{"kind":"merge_papers","keep":{"oa_id":12,"doi":null},"drop":{"oa_id":11,"doi":null}}}"#,
            r#"{"key":"c","orcid":"o","payload":{"kind":"merge_papers","keep":{"oa_id":11,"doi":null},"drop":{"oa_id":12,"doi":null}}}"#,
        ] {
            ul.apply_event(line(l));
        }
        let ids = SnapshotIds {
            works: [10, 11, 12].into_iter().collect(),
            ..Default::default()
        };
        let (resolved, outcomes) = ul.resolve(&ids).unwrap();
        assert_eq!(resolved.work_aliases, [(11, 12)].into_iter().collect());
        assert_eq!(outcomes.report.applied, vec!["b"]);
        assert_eq!(
            skips(&outcomes),
            vec![("a", SkipReason::Superseded), ("c", SkipReason::MergeCycle)]
        );
    }

    #[test]
    fn a_reassignment_and_a_name_resolve_in_keep_space() {
        let mut ul = UserLedger::default();
        ul.apply_event(merge("m", 1, 2));
        for l in [
            r#"{"key":"to","orcid":"","payload":{"kind":"reassign_paper","work":{"oa_id":10,"doi":null},"author":{"oa_id":2},"to":{"oa_id":5}}}"#,
            r#"{"key":"off","orcid":"","payload":{"kind":"reassign_paper","work":{"oa_id":11,"doi":null},"author":{"oa_id":1}}}"#,
            r#"{"key":"ghost","orcid":"","payload":{"kind":"reassign_paper","work":{"oa_id":10,"doi":null},"author":{"oa_id":1},"to":{"oa_id":77}}}"#,
            r#"{"key":"self","orcid":"","payload":{"kind":"reassign_paper","work":{"oa_id":10,"doi":null},"author":{"oa_id":1},"to":{"oa_id":1}}}"#,
            r#"{"key":"n","orcid":"","payload":{"kind":"name_author","author":{"oa_id":2},"name":"Kim Keep"}}"#,
            // a later reassignment of the same row and a later name of the same record decide
            r#"{"key":"later","orcid":"","payload":{"kind":"reassign_paper","work":{"oa_id":11,"doi":null},"author":{"oa_id":2}}}"#,
            r#"{"key":"n2","orcid":"","payload":{"kind":"name_author","author":{"oa_id":1},"name":"Kim A. Keep"}}"#,
        ] {
            ul.apply_event(line(l));
        }
        let refs = ul.referenced();
        assert_eq!(refs.authors, [1, 2, 5, 77].into_iter().collect());
        assert_eq!(refs.works, [10, 11].into_iter().collect());
        let ids = SnapshotIds {
            authors: counts(&[1, 2, 5]),
            works: [10, 11].into_iter().collect(),
            ..Default::default()
        };
        let (resolved, outcomes) = ul.resolve(&ids).unwrap();
        assert_eq!(
            resolved.reassigned,
            [((1, 10), Some(5)), ((1, 11), None)].into_iter().collect()
        );
        assert_eq!(
            resolved.author_names,
            [(1, "Kim A. Keep".to_string())].into_iter().collect()
        );
        assert_eq!(
            skips(&outcomes),
            vec![
                ("ghost", SkipReason::OaIdNotInDataset),
                ("n", SkipReason::Superseded),
                ("off", SkipReason::Superseded),
                ("self", SkipReason::MissingOaId)
            ]
        );
        // author 1 has work 10 and no row on 11; 5 gets the row taken on 10
        let seen: HashSet<Edge> = [(1, 10), (1, 12)].into_iter().collect();
        assert_eq!(outcomes.watched(&resolved), [1, 5].into_iter().collect());
        assert_eq!(
            resolved.credit(&seen),
            [(5, 10), (1, 12)].into_iter().collect()
        );
    }

    #[test]
    fn a_claim_needs_credit_on_a_served_record_and_a_taking_its_row() {
        let claim = |key: &str, claimant: BigId, works: &[BigId]| PendingClaim {
            key: key.to_string(),
            claimant,
            works: works.to_vec(),
            forced: false,
        };
        let taking = |key: &str, edge: Edge| PendingTaking {
            key: key.to_string(),
            edge,
        };
        let outcomes = Outcomes {
            run_id: String::new(),
            pins: HashSet::new(),
            claims: vec![
                claim("a", 1, &[10]),
                claim("d", 4, &[10]),
                claim("f", 6, &[12]),
                // a DOI on two records, the claimant on the lesser one
                claim("g", 7, &[13, 14]),
            ],
            bound_exempt: HashSet::new(),
            takings: vec![taking("x", (9, 10)), taking("y", (8, 10))],
            report: Report::default(),
        };
        let seen: HashSet<Edge> = [(8, 10)].into_iter().collect();
        let credited: HashSet<Edge> = [(1, 10), (6, 12), (7, 14)].into_iter().collect();
        let served: HashSet<BigId> = [10, 13, 14].into_iter().collect();
        let manifest = outcomes.manifest(&seen, &credited, &served);
        assert_eq!(manifest.applied_keys, ["a", "g", "y"]);
        let skipped: Vec<(&str, SkipReason)> = manifest
            .skipped
            .iter()
            .map(|s| (s.key.as_str(), s.reason.clone()))
            .collect();
        assert_eq!(
            skipped,
            [
                ("d", SkipReason::ClaimantNotAttributed),
                ("f", SkipReason::WorkScreened),
                ("x", SkipReason::AuthorNotOnWork)
            ]
        );
    }

    #[test]
    fn an_uncredited_forced_claim_is_granted_a_row_after_the_listed_ones() {
        let claim = |key: &str, claimant: BigId, works: &[BigId], forced| PendingClaim {
            key: key.to_string(),
            claimant,
            works: works.to_vec(),
            forced,
        };
        let outcomes = Outcomes {
            run_id: String::new(),
            pins: HashSet::new(),
            claims: vec![
                claim("d", 4, &[10], true),
                claim("b", 2, &[10], true),
                claim("a", 1, &[10], true),
                claim("c", 2, &[10], true),
                claim("e", 5, &[11], true),
                claim("f", 6, &[12], true),
                // a DOI on two records: 7 is on the lesser one, 8 disowned the main one
                claim("g", 7, &[13, 14], true),
                claim("h", 8, &[13, 14], true),
                // a site claim is never granted a row
                claim("s", 9, &[10], false),
            ],
            bound_exempt: HashSet::new(),
            takings: Vec::new(),
            report: Report::default(),
        };
        // 1 is on work 10 already, 4 disowned it; work 11 has no row at all
        let credited: HashSet<Edge> = [(1, 10), (7, 14)].into_iter().collect();
        let removed: HashSet<Edge> = [(4, 10), (8, 13)].into_iter().collect();
        let rows: HashMap<BigId, u16> = [(10, 3), (12, 7)].into_iter().collect();
        let ship = |author, work, position| GrantedShip {
            author,
            work,
            position,
        };
        let granted = outcomes.grants(&credited, &removed, &rows);
        assert_eq!(
            granted,
            vec![
                ship(2, 10, 3),
                ship(5, 11, 0),
                ship(6, 12, 7),
                ship(8, 14, 0)
            ]
        );
        let mut with_grants = credited.clone();
        with_grants.extend(granted.iter().map(|g| (g.author, g.work)));
        let forced: Vec<BigId> = outcomes.forced_claim_works(&with_grants).collect();
        assert_eq!(forced, [10, 10, 10, 11, 12, 14, 14]);
    }

    #[test]
    fn a_claim_whose_doi_the_snapshot_lacks_falls_back_to_its_record() {
        let mut ul = UserLedger::default();
        for l in [
            r#"{"key":"both","orcid":"o","payload":{"kind":"claim_paper","work":{"oa_id":11,"doi":"10.1/gone"}}}"#,
            r#"{"key":"doi","orcid":"o","payload":{"kind":"claim_paper","work":{"oa_id":12,"doi":"10.1/x"}}}"#,
            r#"{"key":"neither","orcid":"o","payload":{"kind":"claim_paper","work":{"oa_id":99,"doi":"10.1/gone"}}}"#,
        ] {
            ul.apply_event(line(l));
        }
        let refs = ul.referenced();
        assert_eq!(refs.works, [11, 12, 99].into_iter().collect());
        let ids = SnapshotIds {
            orcid_carriers: carriers(&[("o", &[1])]),
            authors: counts(&[1]),
            works: [11, 12].into_iter().collect(),
            doi_works: [("10.1/x".to_string(), vec![(13, 1), (10, 5)])]
                .into_iter()
                .collect(),
            ..Default::default()
        };
        let (_, outcomes) = ul.resolve(&ids).unwrap();
        let works: Vec<&[BigId]> = outcomes.claims.iter().map(|c| c.works.as_slice()).collect();
        // the DOI stands for its records, the most cited first, not the record the claimant saw
        assert_eq!(works, [&[11][..], &[10, 13][..]]);
        assert_eq!(
            skips(&outcomes),
            vec![("neither", SkipReason::DoiNotInSnapshot)]
        );
    }

    #[test]
    fn a_merge_keep_with_an_aggregate_record_is_not_exempt_from_the_work_bound() {
        let mut ul = UserLedger::default();
        ul.apply_event(merge("person", 1, 2));
        ul.apply_event(merge("into-aggregate", 3, 4));
        ul.apply_event(merge("of-aggregate", 5, 6));
        let over = WORK_SCREEN.max_author_papers + 1;
        let ids = SnapshotIds {
            authors: [(1, 4), (2, 4), (3, over), (4, 4), (5, 4), (6, over)]
                .into_iter()
                .map(|(a, works)| (a, (works, 4)))
                .collect(),
            ..Default::default()
        };
        let (_, outcomes) = ul.resolve(&ids).unwrap();
        assert_eq!(outcomes.bound_exempt, [1].into_iter().collect());
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
        assert_eq!(outcomes.report.applied.len(), 2);
        assert!(outcomes.report.skipped.is_empty());
    }

    #[test]
    fn a_derived_paper_merge_folds_the_work_and_names_no_orcid() {
        let mut ul = UserLedger::default();
        ul.apply_derived(line(
            r#"{"key":"|merge_papers|1","orcid":"","kind":"merge_papers","source":"derived","reason":"angewandte_edition","payload":{"kind":"merge_papers","keep":{"oa_id":2},"drop":{"oa_id":1}}}"#,
        ))
        .unwrap();
        let refs = ul.referenced();
        assert!(refs.orcids.is_empty());
        assert_eq!(refs.works, [1, 2].into_iter().collect());
        let ids = SnapshotIds {
            works: [1, 2].into_iter().collect(),
            ..Default::default()
        };
        let (resolved, outcomes) = ul.resolve(&ids).unwrap();
        assert_eq!(resolved.work_aliases, [(1, 2)].into_iter().collect());
        assert!(outcomes.report.skipped.is_empty());
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
        assert_eq!(outcomes.report.applied.len(), 3);
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
