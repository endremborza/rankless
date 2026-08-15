use std::{
    fs::{self, File},
    io::{self, BufRead, BufReader, BufWriter},
    path::Path,
};

use hashbrown::{HashMap, HashSet};
use serde::{Deserialize, Serialize};

use crate::{
    common::{ParsedId, Stowage, MAIN_NAME},
    csv_writers::authors,
    oa_structs::post::Author,
};
use dmove::BigId;

pub const ORCID_PREF: &str = "https://orcid.org/";

const A1_MANIFEST: &str = "a1_manifest.json";
const ACTIVE_JSONL: &str = "active.jsonl";
const APPLIED_MANIFEST: &str = "applied_manifest.json";
const FILTER_MANIFEST: &str = "filter_manifest.json";
const SNAPSHOT_MANIFEST: &str = "snapshot_manifest.json";
const OWNER_PINS: &str = "owner_pins.txt";
const DOI_PREFIXES: [&str; 4] = [
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
];

// ---------------------------------------------------------------------------
// Cross-language boundary: user-ledger/active.jsonl
// Source of truth (writer): src/lib/types/ledger.ts
// Mirror types below — keep in sync when TS types change.
// ---------------------------------------------------------------------------

#[derive(Default)]
pub struct UserLedger {
    pub run_id: String,
    /// drop_oa_id -> root_oa_id (path-compressed)
    pub author_aliases: HashMap<BigId, BigId>,
    /// drop_oa_id -> root_oa_id (path-compressed)
    pub work_aliases: HashMap<BigId, BigId>,
    /// (author_oa_id, work_oa_id) pairs to exclude from authorships; filled by resolve_orcids
    pub removed_edges: HashSet<(BigId, BigId)>,
    /// Normalised ORCIDs (no prefix) to force through the author filter
    pub owner_pin_orcids: HashSet<String>,
    /// Author oa_ids corresponding to owner_pin_orcids; filled by resolve_orcids
    pub owner_pin_oa_ids: HashSet<BigId>,
    /// (key, orcid, canonical_doi) claims awaiting DOI→work resolution in the filter step
    pub pending_claims: Vec<(String, String, String)>,
    /// (key, orcid, work_oa) pending ORCID→oa_id resolution
    pending_disowns: Vec<(String, String, BigId)>,
    /// (key, drop_oa, keep_oa) before path-compression; for manifest
    author_merge_events: Vec<(String, BigId, BigId)>,
    work_merge_events: Vec<(String, BigId, BigId)>,
    /// logical keys for disowns whose orcid resolved (filled by resolve_orcids)
    resolved_disown_keys: Vec<String>,
    pub skipped: Vec<SkippedEvent>,
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

#[derive(Serialize, Deserialize)]
struct StepManifest {
    run_id: String,
    applied_keys: Vec<String>,
    skipped: Vec<SkippedEvent>,
}

impl UserLedger {
    pub fn load(stowage: &Stowage) -> io::Result<Self> {
        let ul_dir = &stowage.paths.user_ledger;
        let mut ul = Self::default();
        ul.run_id = read_run_id(ul_dir);
        ul.owner_pin_orcids = load_owner_pins(ul_dir)?;

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

        path_compress(&mut ul.author_aliases);
        path_compress(&mut ul.work_aliases);
        Ok(ul)
    }

    fn apply_event(&mut self, event: LedgerEventLine) {
        let LedgerEventLine {
            key,
            orcid,
            payload,
        } = event;
        let orcid = normalize_orcid(&orcid);
        match payload {
            EventPayload::MergeAuthors { keep, drop } => match (keep.oa_id, drop.oa_id) {
                (Some(k), Some(d)) if k != d => {
                    self.author_aliases.insert(d, k);
                    self.author_merge_events.push((key, d, k));
                }
                _ => self.skipped.push(SkippedEvent {
                    key,
                    reason: SkipReason::MissingOaId,
                }),
            },
            EventPayload::MergePapers { keep, drop } => match (keep.oa_id, drop.oa_id) {
                (Some(k), Some(d)) if k != d => {
                    self.work_aliases.insert(d, k);
                    self.work_merge_events.push((key, d, k));
                }
                _ => self.skipped.push(SkippedEvent {
                    key,
                    reason: SkipReason::MissingOaId,
                }),
            },
            EventPayload::DisownPaper { work } => match work.oa_id {
                Some(w) if !orcid.is_empty() => self.pending_disowns.push((key, orcid, w)),
                _ => self.skipped.push(SkippedEvent {
                    key,
                    reason: SkipReason::MissingOaIdOrOrcid,
                }),
            },
            EventPayload::ClaimPaper { work } => match work.doi {
                Some(doi) if !orcid.is_empty() => {
                    self.pending_claims.push((key, orcid, canonical_doi(&doi)))
                }
                _ => self.skipped.push(SkippedEvent {
                    key,
                    reason: SkipReason::MissingOaIdOrOrcid,
                }),
            },
            // Resolved in export or never emitted; never present in active.jsonl.
            EventPayload::Revoke
            | EventPayload::ModerationDecision
            | EventPayload::AddPaperRequest => {}
        }
    }

    /// Resolve ORCID strings to author oa_ids and populate `removed_edges` and
    /// `owner_pin_oa_ids`. Call this after `load` once an orcid→oa_id map is available.
    pub fn resolve_orcids(&mut self, orcid_to_oa: &HashMap<String, BigId>) {
        for orcid in &self.owner_pin_orcids {
            if let Some(&oa_id) = orcid_to_oa.get(orcid) {
                self.owner_pin_oa_ids.insert(oa_id);
            }
        }
        for (key, orcid, work_oa) in &self.pending_disowns {
            if let Some(&author_oa) = orcid_to_oa.get(orcid) {
                self.removed_edges.insert((author_oa, *work_oa));
                self.resolved_disown_keys.push(key.clone());
            } else {
                self.skipped.push(SkippedEvent {
                    key: key.clone(),
                    reason: SkipReason::OrcidNotInDataset,
                });
            }
        }
    }

    /// Write `user_ledger/a1_manifest.json` recording which merge events were
    /// applied vs skipped, validated against the current filter sets.
    pub fn write_a1_manifest(
        &self,
        stowage: &Stowage,
        author_filter: &HashSet<BigId>,
        work_filter: &HashSet<BigId>,
    ) -> io::Result<()> {
        let mut applied = Vec::new();
        let mut skipped = self.skipped.clone();

        for (key, drop_oa, _) in &self.author_merge_events {
            let root = *self.author_aliases.get(drop_oa).unwrap_or(drop_oa);
            if author_filter.contains(&root) {
                applied.push(key.clone());
            } else {
                eprintln!(
                    "user_ledger: event {key} skipped — author oa_id {root} not in dataset. \
                     If this ID was recently deprecated by OpenAlex, re-implement merged_ids \
                     redirect support (see docs/todo-backend.md, ledger deferred follow-ups)."
                );
                skipped.push(SkippedEvent {
                    key: key.clone(),
                    reason: SkipReason::OaIdNotInDataset,
                });
            }
        }
        for (key, drop_oa, _) in &self.work_merge_events {
            let root = *self.work_aliases.get(drop_oa).unwrap_or(drop_oa);
            if work_filter.contains(&root) {
                applied.push(key.clone());
            } else {
                eprintln!(
                    "user_ledger: event {key} skipped — work oa_id {root} not in dataset. \
                     If this ID was recently deprecated by OpenAlex, re-implement merged_ids \
                     redirect support (see docs/todo-backend.md, ledger deferred follow-ups)."
                );
                skipped.push(SkippedEvent {
                    key: key.clone(),
                    reason: SkipReason::OaIdNotInDataset,
                });
            }
        }

        applied.sort_unstable();
        let manifest = StepManifest {
            run_id: self.run_id.clone(),
            applied_keys: applied,
            skipped,
        };
        write_json(&stowage.paths.user_ledger.join(A1_MANIFEST), &manifest)?;
        println!(
            "{A1_MANIFEST}: {} applied, {} skipped",
            manifest.applied_keys.len(),
            manifest.skipped.len()
        );
        Ok(())
    }

    /// Write `user_ledger/filter_manifest.json` recording claim application:
    /// applied claim keys + claim skips, resolved by the filter step.
    pub fn write_filter_manifest(
        &self,
        stowage: &Stowage,
        applied_keys: Vec<String>,
        skipped: Vec<SkippedEvent>,
    ) -> io::Result<()> {
        let mut applied = applied_keys;
        applied.sort_unstable();
        let manifest = StepManifest {
            run_id: self.run_id.clone(),
            applied_keys: applied,
            skipped,
        };
        write_json(&stowage.paths.user_ledger.join(FILTER_MANIFEST), &manifest)?;
        println!(
            "{FILTER_MANIFEST}: {} applied, {} skipped",
            manifest.applied_keys.len(),
            manifest.skipped.len()
        );
        Ok(())
    }

    /// Cross-language boundary: applied_manifest.json (Rust → TS)
    /// Mirror: src/lib/types/ledger.ts — AppliedManifest
    pub fn write_final_manifest(&self, stowage: &Stowage) -> io::Result<()> {
        let ul_dir = &stowage.paths.user_ledger;
        let a1 = read_step_manifest(ul_dir, A1_MANIFEST, "a1_entity_mapping")?;
        let filt = read_step_manifest(ul_dir, FILTER_MANIFEST, "the filter step")?;
        for (label, manifest) in [("a1", &a1), ("filter", &filt)] {
            if !self.run_id.is_empty()
                && !manifest.run_id.is_empty()
                && manifest.run_id != self.run_id
            {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    format!(
                        "manifest run_id mismatch: {label}={} a2={}",
                        manifest.run_id, self.run_id
                    ),
                ));
            }
        }

        let mut all_applied = a1.applied_keys;
        all_applied.extend(filt.applied_keys);
        for key in &self.resolved_disown_keys {
            all_applied.push(key.clone());
        }
        all_applied.sort_unstable();
        all_applied.dedup();

        let mut all_skipped = a1.skipped;
        all_skipped.extend(filt.skipped);
        all_skipped.extend(self.skipped.iter().cloned());
        let mut seen = HashSet::new();
        all_skipped.retain(|s| seen.insert((s.key.clone(), s.reason.clone())));

        let manifest = serde_json::json!({
            "run_id": self.run_id,
            "snapshot_at": self.run_id,
            "applied_keys": all_applied,
            "skipped": all_skipped,
        });
        write_json(&ul_dir.join(APPLIED_MANIFEST), &manifest)?;
        println!(
            "applied_manifest: {} applied, {} skipped",
            all_applied.len(),
            all_skipped.len()
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

/// Scan the authors CSV and return a map of normalised ORCID → author oa_id.
pub fn build_author_orcid_map(stowage: &Stowage) -> HashMap<String, BigId> {
    stowage
        .read_csv_objs::<Author>(authors::C, MAIN_NAME)
        .filter_map(|a| {
            let oa_id = a.get_parsed_id()?;
            let orcid = a.orcid?;
            let normalized = normalize_orcid(&orcid);
            if normalized.is_empty() {
                return None;
            }
            Some((normalized, oa_id))
        })
        .collect()
}

/// Augment `map` so that every drop-side alias resolves to the keep author's dm_id.
/// Entries are only added when the keep oa_id is already in `map`; invalid aliases
/// (keep not in dataset) are silently skipped.
pub fn augment_with_aliases<T>(map: &mut dmove::LoadedIdMap<T>, aliases: &HashMap<BigId, BigId>)
where
    T: dmove::UnsignedNumber + Copy,
{
    let extra: Vec<(BigId, T)> = aliases
        .iter()
        .filter_map(|(&drop, &keep)| map.0.get(&keep).copied().map(|dm| (drop, dm)))
        .collect();
    for (drop, dm) in extra {
        map.0.insert(drop, dm);
    }
}

fn read_step_manifest(ul_dir: &Path, name: &str, producer: &str) -> io::Result<StepManifest> {
    let raw = fs::read_to_string(ul_dir.join(name)).map_err(|_| {
        io::Error::new(
            io::ErrorKind::NotFound,
            format!("{name} missing — {producer} must run before a2_init_atts"),
        )
    })?;
    serde_json::from_str(&raw).map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))
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
    let mut pins = HashSet::new();
    for line in BufReader::new(File::open(&path)?).lines() {
        let trimmed = line?.trim().to_string();
        if !trimmed.is_empty() {
            pins.insert(normalize_orcid(&trimmed));
        }
    }
    Ok(pins)
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
        let mut ul = UserLedger {
            run_id: String::new(),
            author_aliases: HashMap::new(),
            work_aliases: HashMap::new(),
            removed_edges: HashSet::new(),
            owner_pin_orcids: HashSet::new(),
            owner_pin_oa_ids: HashSet::new(),
            pending_claims: Vec::new(),
            pending_disowns: Vec::new(),
            author_merge_events: Vec::new(),
            work_merge_events: Vec::new(),
            resolved_disown_keys: Vec::new(),
            skipped: Vec::new(),
        };
        let event: LedgerEventLine = serde_json::from_str(
            r#"{"key":"0-1|claim_paper|h","orcid":"0-1","payload":{"kind":"claim_paper","work":{"oa_id":null,"doi":"https://doi.org/10.1000/XYZ"}}}"#,
        )
        .unwrap();
        ul.apply_event(event);
        assert_eq!(
            ul.pending_claims,
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
