use std::{
    fs::{self, File},
    io::{self, BufRead, BufReader, BufWriter},
    path::Path,
};

use hashbrown::{HashMap, HashSet};
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{
    common::{ParsedId, Stowage, MAIN_NAME},
    csv_writers::authors,
    oa_structs::post::Author,
};
use dmove::BigId;

pub const ORCID_PREF: &str = "https://orcid.org/";

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SkipReason {
    MissingOaId,
    MissingOaIdOrOrcid,
    ClaimPipelineNotImplemented,
    OrcidNotInDataset,
    OaIdNotInDataset,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkippedEvent {
    pub event_id: u64,
    pub reason: SkipReason,
}

#[derive(Serialize, Deserialize)]
struct StepManifest {
    run_id: String,
    applied_event_ids: Vec<u64>,
    skipped: Vec<SkippedEvent>,
}

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
    /// (event_id, orcid, work_oa) pending ORCID→oa_id resolution
    pending_disowns: Vec<(u64, String, BigId)>,
    /// (event_id, drop_oa, keep_oa) before path-compression; for manifest
    author_merge_events: Vec<(u64, BigId, BigId)>,
    work_merge_events: Vec<(u64, BigId, BigId)>,
    /// event_ids for disowns whose orcid resolved (filled by resolve_orcids)
    resolved_disown_event_ids: Vec<u64>,
    pub skipped: Vec<SkippedEvent>,
}

impl UserLedger {
    pub fn load(stowage: &Stowage) -> io::Result<Self> {
        let ul_dir = &stowage.paths.user_ledger;
        let run_id = read_run_id(ul_dir);
        let owner_pin_orcids = load_owner_pins(ul_dir)?;

        let mut author_aliases: HashMap<BigId, BigId> = HashMap::new();
        let mut work_aliases: HashMap<BigId, BigId> = HashMap::new();
        let mut pending_disowns: Vec<(u64, String, BigId)> = Vec::new();
        let mut author_merge_events: Vec<(u64, BigId, BigId)> = Vec::new();
        let mut work_merge_events: Vec<(u64, BigId, BigId)> = Vec::new();
        let mut skipped: Vec<SkippedEvent> = Vec::new();

        let active_path = ul_dir.join("active.jsonl");
        if active_path.exists() {
            for line in BufReader::new(File::open(&active_path)?).lines() {
                let line = line?;
                let line = line.trim();
                if line.is_empty() {
                    continue;
                }
                let event: Value = match serde_json::from_str(line) {
                    Ok(v) => v,
                    Err(e) => {
                        eprintln!("user_ledger: skipping malformed event: {e}");
                        continue;
                    }
                };
                let event_id = event["event_id"].as_u64().unwrap_or(0);
                let kind = event["kind"].as_str().unwrap_or("");
                let orcid = normalize_orcid(event["orcid"].as_str().unwrap_or(""));

                match kind {
                    "merge_authors" => {
                        let keep_raw = event["payload"]["keep"]["oa_id"].as_u64();
                        let drop_raw = event["payload"]["drop"]["oa_id"].as_u64();
                        match (keep_raw, drop_raw) {
                            (Some(k), Some(d)) if k != d => {
                                author_aliases.insert(d, k);
                                author_merge_events.push((event_id, d, k));
                            }
                            _ => skipped.push(SkippedEvent {
                                event_id,
                                reason: SkipReason::MissingOaId,
                            }),
                        }
                    }
                    "merge_papers" => {
                        let keep_raw = event["payload"]["keep"]["oa_id"].as_u64();
                        let drop_raw = event["payload"]["drop"]["oa_id"].as_u64();
                        match (keep_raw, drop_raw) {
                            (Some(k), Some(d)) if k != d => {
                                work_aliases.insert(d, k);
                                work_merge_events.push((event_id, d, k));
                            }
                            _ => skipped.push(SkippedEvent {
                                event_id,
                                reason: SkipReason::MissingOaId,
                            }),
                        }
                    }
                    "disown_paper" => {
                        let work_oa_raw = event["payload"]["work"]["oa_id"].as_u64();
                        match work_oa_raw {
                            Some(w) if !orcid.is_empty() => {
                                pending_disowns.push((event_id, orcid, w));
                            }
                            _ => skipped.push(SkippedEvent {
                                event_id,
                                reason: SkipReason::MissingOaIdOrOrcid,
                            }),
                        }
                    }
                    "claim_paper" => {
                        skipped.push(SkippedEvent {
                            event_id,
                            reason: SkipReason::ClaimPipelineNotImplemented,
                        });
                    }
                    "revoke" => {
                        // Revoke of an already-applied event (export inlines the target).
                        if let Some(target) = event.get("target_inlined") {
                            match target["kind"].as_str().unwrap_or("") {
                                "merge_authors" => {
                                    if let Some(d_raw) = target["payload"]["drop"]["oa_id"].as_u64()
                                    {
                                        author_aliases.remove(&d_raw);
                                        author_merge_events.retain(|(_, drop, _)| *drop != d_raw);
                                    }
                                }
                                "merge_papers" => {
                                    if let Some(d_raw) = target["payload"]["drop"]["oa_id"].as_u64()
                                    {
                                        work_aliases.remove(&d_raw);
                                        work_merge_events.retain(|(_, drop, _)| *drop != d_raw);
                                    }
                                }
                                "disown_paper" => {
                                    let w_raw = target["payload"]["work"]["oa_id"].as_u64();
                                    let torcid =
                                        normalize_orcid(target["orcid"].as_str().unwrap_or(""));
                                    if let Some(work_oa) = w_raw {
                                        pending_disowns.retain(|(_, o, wid)| {
                                            !(o == &torcid && *wid == work_oa)
                                        });
                                    }
                                }
                                _ => {}
                            }
                        }
                    }
                    _ => {}
                }
            }
        }

        path_compress(&mut author_aliases);
        path_compress(&mut work_aliases);

        Ok(Self {
            run_id,
            author_aliases,
            work_aliases,
            removed_edges: HashSet::new(),
            owner_pin_orcids,
            owner_pin_oa_ids: HashSet::new(),
            pending_disowns,
            author_merge_events,
            work_merge_events,
            resolved_disown_event_ids: Vec::new(),
            skipped,
        })
    }

    /// Resolve ORCID strings to author oa_ids and populate `removed_edges` and
    /// `owner_pin_oa_ids`. Call this after `load` once an orcid→oa_id map is available.
    pub fn resolve_orcids(&mut self, orcid_to_oa: &HashMap<String, BigId>) {
        for orcid in &self.owner_pin_orcids {
            if let Some(&oa_id) = orcid_to_oa.get(orcid) {
                self.owner_pin_oa_ids.insert(oa_id);
            }
        }
        for (event_id, orcid, work_oa) in &self.pending_disowns {
            if let Some(&author_oa) = orcid_to_oa.get(orcid) {
                self.removed_edges.insert((author_oa, *work_oa));
                self.resolved_disown_event_ids.push(*event_id);
            } else {
                self.skipped.push(SkippedEvent {
                    event_id: *event_id,
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

        for (event_id, drop_oa, _) in &self.author_merge_events {
            // After path-compression, alias[drop] is already the root.
            let root = *self.author_aliases.get(drop_oa).unwrap_or(drop_oa);
            if author_filter.contains(&root) {
                applied.push(*event_id);
            } else {
                eprintln!(
                    "user_ledger: event {event_id} skipped — author oa_id {root} not in dataset. \
                     If this ID was recently deprecated by OpenAlex, re-implement merged_ids \
                     redirect support (see docs/plans/author-profile-ledger.md §6.5)."
                );
                skipped.push(SkippedEvent {
                    event_id: *event_id,
                    reason: SkipReason::OaIdNotInDataset,
                });
            }
        }
        for (event_id, drop_oa, _) in &self.work_merge_events {
            let root = *self.work_aliases.get(drop_oa).unwrap_or(drop_oa);
            if work_filter.contains(&root) {
                applied.push(*event_id);
            } else {
                eprintln!(
                    "user_ledger: event {event_id} skipped — work oa_id {root} not in dataset. \
                     If this ID was recently deprecated by OpenAlex, re-implement merged_ids \
                     redirect support (see docs/plans/author-profile-ledger.md §6.5)."
                );
                skipped.push(SkippedEvent {
                    event_id: *event_id,
                    reason: SkipReason::OaIdNotInDataset,
                });
            }
        }

        applied.sort_unstable();
        let manifest = StepManifest {
            run_id: self.run_id.clone(),
            applied_event_ids: applied,
            skipped,
        };
        write_json(
            &stowage.paths.user_ledger.join("a1_manifest.json"),
            &manifest,
        )?;
        println!(
            "a1_manifest: {} applied, {} skipped",
            manifest.applied_event_ids.len(),
            manifest.skipped.len()
        );
        Ok(())
    }

    /// Read `a1_manifest.json`, validate run_id, combine with a2's disown results,
    /// and write the final `applied_manifest.json`.
    pub fn write_final_manifest(&self, stowage: &Stowage) -> io::Result<()> {
        let ul_dir = &stowage.paths.user_ledger;
        let raw = fs::read_to_string(ul_dir.join("a1_manifest.json")).map_err(|_| {
            io::Error::new(
                io::ErrorKind::NotFound,
                "a1_manifest.json missing — a1_entity_mapping must run before a2_init_atts",
            )
        })?;
        let a1: StepManifest = serde_json::from_str(&raw)
            .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;

        if !self.run_id.is_empty() && !a1.run_id.is_empty() && a1.run_id != self.run_id {
            return Err(io::Error::new(
                io::ErrorKind::InvalidData,
                format!(
                    "manifest run_id mismatch: a1={} a2={}",
                    a1.run_id, self.run_id
                ),
            ));
        }

        let mut all_applied = a1.applied_event_ids;
        for &eid in &self.resolved_disown_event_ids {
            all_applied.push(eid);
        }
        all_applied.sort_unstable();
        all_applied.dedup();

        let mut all_skipped = a1.skipped;
        all_skipped.extend(self.skipped.iter().cloned());

        let manifest = serde_json::json!({
            "run_id": self.run_id,
            "snapshot_at": self.run_id,
            "applied_event_ids": all_applied,
            "skipped": all_skipped,
        });
        write_json(&ul_dir.join("applied_manifest.json"), &manifest)?;
        println!(
            "applied_manifest: {} applied, {} skipped",
            all_applied.len(),
            all_skipped.len()
        );
        Ok(())
    }
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

fn read_run_id(ul_dir: &Path) -> String {
    let path = ul_dir.join("snapshot_manifest.json");
    if !path.exists() {
        return String::new();
    }
    fs::read_to_string(&path)
        .ok()
        .and_then(|s| serde_json::from_str::<Value>(&s).ok())
        .and_then(|v| v["run_id"].as_str().map(String::from))
        .unwrap_or_default()
}

fn load_owner_pins(ul_dir: &Path) -> io::Result<HashSet<String>> {
    let path = ul_dir.join("owner_pins.txt");
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

pub fn normalize_orcid(orcid: &str) -> String {
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
}
