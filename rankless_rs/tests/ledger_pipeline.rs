//! Ledger pipeline gate on the synthetic snapshot: `to-csv → filter → a1_entity_mapping`
//! in-process. The filter step resolves the ledger against the raw tables and writes
//! `resolved_ledger.json` + `applied_manifest.json`; from there every CSV read applies the
//! resolved tables, so the screens and a1 see merged ids as keep ids and disowned
//! authorships as absent. Later steps compile against `gen/` for one dataset shape, so their
//! link-level invariants ride `make mega_test`; here the filter sets, the dm space and the
//! resolved tables are asserted instead.

#[allow(dead_code)]
mod common;

use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File},
    io::Write,
    path::{Path, PathBuf},
};

use common::{
    synthetic_oa::{Scenario, INST_A, INST_B, SOURCE},
    TempRoot,
};
use dmove::LoadedIdMap;
use rankless_rs::{common::Stowage, run_step, user_ledger::ResolvedLedger};
use serde_json::{json, Value};

const RUN_ID: &str = "2026-09-02T00:00:00Z";

#[derive(Clone)]
struct Event {
    key: String,
    orcid: String,
    kind: &'static str,
    payload: Value,
}

struct Fixture {
    root: TempRoot,
    scenario: Scenario,
}

struct Run {
    root: PathBuf,
}

struct Manifest {
    run_id: String,
    applied: BTreeSet<String>,
    skipped: BTreeSet<(String, String)>,
}

impl Event {
    fn new(orcid: &str, kind: &'static str, tag: &str, payload: Value) -> Self {
        Self {
            key: format!("{orcid}|{kind}|{tag}"),
            orcid: orcid.to_string(),
            kind,
            payload,
        }
    }

    fn disown(orcid: &str, wid: u64, tag: &str) -> Self {
        Self::new(
            orcid,
            "disown_paper",
            tag,
            json!({"kind": "disown_paper", "work": {"oa_id": wid, "doi": null}}),
        )
    }

    fn merge_papers(orcid: &str, keep: u64, drop: u64, tag: &str) -> Self {
        Self::new(
            orcid,
            "merge_papers",
            tag,
            json!({"kind": "merge_papers", "keep": {"oa_id": keep, "doi": null}, "drop": {"oa_id": drop, "doi": null}}),
        )
    }

    fn merge_authors(orcid: &str, keep: u64, drop: u64, tag: &str) -> Self {
        Self::new(
            orcid,
            "merge_authors",
            tag,
            json!({"kind": "merge_authors", "keep": {"oa_id": keep, "orcid": orcid}, "drop": {"oa_id": drop, "orcid": null}}),
        )
    }

    fn claim(orcid: &str, doi: &str, tag: &str) -> Self {
        Self::new(
            orcid,
            "claim_paper",
            tag,
            json!({"kind": "claim_paper", "work": {"oa_id": null, "doi": doi}}),
        )
    }

    fn revoke(orcid: &str, target_key: &str, tag: &str) -> Self {
        Self::new(
            orcid,
            "revoke",
            tag,
            json!({"kind": "revoke", "target_key": target_key}),
        )
    }

    /// One `active.jsonl` line as `export_user_ledger.py` writes it.
    fn line(&self, event_id: usize) -> Value {
        json!({
            "event_id": event_id,
            "key": self.key,
            "orcid": self.orcid,
            "kind": self.kind,
            "source": "site",
            "payload": self.payload,
            "moderation": "auto_ok",
            "created_at": RUN_ID,
        })
    }
}

impl Fixture {
    fn new(tag: &str) -> Self {
        let root = TempRoot::new(tag);
        let scenario = Scenario::new();
        scenario.write_snapshot(&root.0.join("snapshot")).unwrap();
        let fixture = Self { root, scenario };
        let data = Scenario::data_dir(&fixture.root.0.join("snapshot"));
        run_step("to-csv", fixture.stowage(), data.to_str()).unwrap();
        fixture
    }

    fn data_root(&self) -> PathBuf {
        self.root.0.join("root")
    }

    fn ledger_dir(&self) -> PathBuf {
        self.data_root().join("user-ledger")
    }

    fn stowage(&self) -> Stowage {
        Stowage::new(self.data_root().to_str().unwrap()).with_code_dir(self.root.0.join("gen"))
    }

    /// What `make filter` (export → clean-filters → filter) and the a1 step do to the ledger.
    fn run(&self, events: &[Event], pins: &[&str]) -> Run {
        let root = self.data_root();
        fs::create_dir_all(self.root.0.join("gen")).unwrap();
        write_ledger(&self.ledger_dir(), events, pins);
        let _ = fs::remove_dir_all(root.join("filter-steps"));
        run_step("filter", self.stowage(), None).unwrap();
        run_step("a1_entity_mapping", self.stowage(), None).unwrap();
        Run { root }
    }

    /// Every event kind once, from signed-in owners (every event author is pinned, as the
    /// login flow guarantees) plus the subjects that cannot resolve.
    fn full_ledger(&self) -> (Vec<Event>, Vec<&str>) {
        let s = &self.scenario;
        let owner = s.owner.orcid.unwrap();
        let keep = s.keep.orcid.unwrap();
        let outsider = s.outsider.orcid.unwrap();
        let events = vec![
            Event::disown(owner, s.solo, "solo"),
            Event::disown(owner, s.shared, "shared"),
            Event::merge_papers(keep, s.keep_work, s.drop_work, "twins"),
            Event::merge_authors(keep, s.keep.oa_id, s.drop.oa_id, "self"),
            Event::claim(keep, &doi(s, s.claim_auto), "auto"),
            Event::claim(keep, &doi(s, s.claim_merged), "merged"),
            Event::claim(outsider, &doi(s, s.not_mine), "not-mine"),
            Event::claim(keep, s.ghost_doi, "ghost-doi"),
            Event::disown(owner, s.ghost_work, "ghost-work"),
            Event::disown(s.unknown_orcid, s.solo, "unknown-orcid"),
        ];
        (events, vec![owner, keep, s.unknown_orcid])
    }

    /// The works `authors` are credited on in keep-id space.
    fn credited_works(&self, authors: &[u64]) -> BTreeSet<u64> {
        let s = &self.scenario;
        s.works
            .iter()
            .filter(|w| w.authors.iter().any(|(a, _)| authors.contains(a)))
            .map(|w| {
                if w.oa_id == s.drop_work {
                    s.keep_work
                } else {
                    w.oa_id
                }
            })
            .collect()
    }
}

impl Run {
    fn filter(&self, step: u8, entity: &str) -> BTreeSet<u64> {
        let bytes = fs::read(
            self.root
                .join("filter-steps")
                .join(step.to_string())
                .join(entity),
        )
        .unwrap_or_else(|e| panic!("filter {step}/{entity}: {e}"));
        bytes
            .chunks_exact(8)
            .map(|c| u64::from_be_bytes(c.try_into().unwrap()))
            .collect()
    }

    /// `a1_entity_mapping/<name>`: sorted (oa_id, dm_id) records, both big-endian u64.
    fn id_map(&self, name: &str) -> LoadedIdMap<u64> {
        let bytes = fs::read(self.root.join("a1_entity_mapping").join(name))
            .unwrap_or_else(|e| panic!("id map {name}: {e}"));
        LoadedIdMap(
            bytes
                .chunks_exact(16)
                .map(|c| {
                    (
                        u64::from_be_bytes(c[..8].try_into().unwrap()),
                        u64::from_be_bytes(c[8..].try_into().unwrap()),
                    )
                })
                .collect(),
        )
    }

    fn ledger_json(&self, name: &str) -> Value {
        let path = self.root.join("user-ledger").join(name);
        serde_json::from_slice(&fs::read(&path).unwrap_or_else(|e| panic!("{name}: {e}"))).unwrap()
    }

    fn resolved(&self) -> ResolvedLedger {
        ResolvedLedger::load(&self.root.join("user-ledger")).unwrap()
    }

    fn manifest(&self) -> Manifest {
        let v = self.ledger_json("applied_manifest.json");
        Manifest {
            run_id: v["run_id"].as_str().unwrap().to_string(),
            applied: v["applied_keys"]
                .as_array()
                .unwrap()
                .iter()
                .map(|k| k.as_str().unwrap().to_string())
                .collect(),
            skipped: v["skipped"]
                .as_array()
                .unwrap()
                .iter()
                .map(|s| {
                    (
                        s["key"].as_str().unwrap().to_string(),
                        s["reason"].as_str().unwrap().to_string(),
                    )
                })
                .collect(),
        }
    }

    /// Every byte the run writes deterministically: the a1 id maps and the ledger sidecars.
    fn stable_bytes(&self) -> BTreeMap<String, Vec<u8>> {
        let mut out = BTreeMap::new();
        for dir in ["a1_entity_mapping", "user-ledger"] {
            for entry in fs::read_dir(self.root.join(dir)).unwrap() {
                let path = entry.unwrap().path();
                let name = format!("{dir}/{}", path.file_name().unwrap().to_str().unwrap());
                out.insert(name, fs::read(&path).unwrap());
            }
        }
        out
    }

    /// Filter files are written in hash order, so they compare as sets.
    fn filter_sets(&self) -> BTreeMap<String, BTreeSet<u64>> {
        let mut out = BTreeMap::new();
        for step_dir in fs::read_dir(self.root.join("filter-steps")).unwrap() {
            let step_dir = step_dir.unwrap().path();
            for entry in fs::read_dir(&step_dir).unwrap() {
                let path = entry.unwrap().path();
                let name = format!(
                    "{}/{}",
                    step_dir.file_name().unwrap().to_str().unwrap(),
                    path.file_name().unwrap().to_str().unwrap()
                );
                let set = fs::read(&path)
                    .unwrap()
                    .chunks_exact(8)
                    .map(|c| u64::from_be_bytes(c.try_into().unwrap()))
                    .collect();
                out.insert(name, set);
            }
        }
        out
    }
}

fn doi(s: &Scenario, wid: u64) -> String {
    s.work(wid).doi.clone().unwrap()
}

fn write_ledger(dir: &Path, events: &[Event], pins: &[&str]) {
    fs::create_dir_all(dir).unwrap();
    let mut active = File::create(dir.join("active.jsonl")).unwrap();
    for (i, e) in events.iter().enumerate() {
        serde_json::to_writer(&mut active, &e.line(i + 1)).unwrap();
        active.write_all(b"\n").unwrap();
    }
    let manifest = json!({"run_id": RUN_ID, "event_ids": (1..=events.len()).collect::<Vec<_>>(), "sources": {"site": events.len()}});
    fs::write(dir.join("snapshot_manifest.json"), manifest.to_string()).unwrap();
    let mut pin_file = String::new();
    for p in pins {
        pin_file.push_str(p);
        pin_file.push('\n');
    }
    fs::write(dir.join("owner_pins.txt"), pin_file).unwrap();
}

fn keys(events: &[Event], tags: &[&str]) -> BTreeSet<String> {
    tags.iter()
        .map(|t| {
            events
                .iter()
                .find(|e| e.key.ends_with(&format!("|{t}")))
                .unwrap_or_else(|| panic!("no event tagged {t}"))
                .key
                .clone()
        })
        .collect()
}

fn skips(events: &[Event], pairs: &[(&str, &str)]) -> BTreeSet<(String, String)> {
    pairs
        .iter()
        .map(|(t, reason)| {
            (
                keys(events, &[t]).into_iter().next().unwrap(),
                reason.to_string(),
            )
        })
        .collect()
}

fn dm_of(map: &LoadedIdMap<u64>, oa: u64) -> Option<u64> {
    map.0.get(&oa).copied()
}

#[test]
fn ledger_applies_through_filter_and_a1() {
    let fx = Fixture::new("ledger-full");
    let s = &fx.scenario;
    let (events, pins) = fx.full_ledger();
    let run = fx.run(&events, &pins);

    // The resolved tables: merges in keep-id space, disowns anchored to the owner's id.
    let resolved = run.resolved();
    assert_eq!(resolved.run_id, RUN_ID);
    assert_eq!(
        resolved.work_aliases,
        [(s.drop_work, s.keep_work)].into_iter().collect()
    );
    assert_eq!(
        resolved.author_aliases,
        [(s.drop.oa_id, s.keep.oa_id)].into_iter().collect()
    );
    assert_eq!(
        resolved.removed_edges,
        [(s.owner.oa_id, s.solo), (s.owner.oa_id, s.shared)]
            .into_iter()
            .collect()
    );

    // Step 10 (type screen): the owners' datasets and preprints ride through; the merged
    // twin has no row of its own.
    let typed = run.filter(10, "works");
    for wid in [
        s.dataset,
        s.claim_auto,
        s.claim_merged,
        s.solo,
        s.shared,
        s.uncited,
        s.hyper,
        s.keep_work,
    ] {
        assert!(typed.contains(&wid), "step 10 lacks {wid}");
    }
    assert!(!typed.contains(&s.drop_work));
    assert!(!typed.contains(&s.ghost_work));
    // Step 11 (citation screen): the owner's uncited article rides through.
    assert!(run.filter(11, "works").contains(&s.uncited));
    // Step 14 (authorship): the disowned solo work is authorless and drops; the shared one
    // stays; the hyperauthored one survives only because the owner's œuvre is forced.
    let works14 = run.filter(14, "works");
    assert!(!works14.contains(&s.solo));
    assert!(!works14.contains(&s.drop_work));
    for wid in [s.shared, s.hyper, s.dataset, s.uncited, s.keep_work] {
        assert!(works14.contains(&wid), "step 14 lacks {wid}");
    }
    let authors14 = run.filter(14, "authors");
    assert!(authors14.contains(&s.keep.oa_id));
    assert!(
        !authors14.contains(&s.drop.oa_id),
        "drop side credited to keep"
    );
    // Step 20 (author thresholds): the owner survives only through the pin.
    let authors20 = run.filter(20, "authors");
    assert!(authors20.contains(&s.owner.oa_id));
    assert!(authors20.contains(&s.keep.oa_id));
    assert!(!authors20.contains(&s.outsider.oa_id));
    assert!(run
        .filter(21, "institutions")
        .is_superset(&[INST_A, INST_B].into()));
    assert!(run.filter(12, "sources").contains(&SOURCE));

    // a1 dm space: drop sides get no id anywhere.
    let works = run.id_map("works");
    assert!(dm_of(&works, s.drop_work).is_none());
    assert!(dm_of(&works, s.keep_work).is_some());
    assert!(dm_of(&works, s.solo).is_none());
    let authors = run.id_map("authors");
    let discarded = run.id_map("discarded-authors");
    assert!(dm_of(&authors, s.owner.oa_id).is_some());
    assert!(dm_of(&authors, s.keep.oa_id).is_some());
    assert!(dm_of(&authors, s.drop.oa_id).is_none());
    assert!(dm_of(&discarded, s.drop.oa_id).is_none());
    assert!(dm_of(&discarded, s.outsider.oa_id).is_some());

    // The manifest: exact applied and skipped sets; the merged claim is credited only
    // because the authorship rows read under the keep author's id.
    let applied = run.manifest();
    assert_eq!(applied.run_id, RUN_ID);
    assert_eq!(
        applied.applied,
        keys(
            &events,
            &["solo", "shared", "twins", "self", "auto", "merged"]
        )
    );
    assert_eq!(
        applied.skipped,
        skips(
            &events,
            &[
                ("not-mine", "claimant_not_attributed"),
                ("ghost-doi", "doi_not_in_snapshot"),
                ("ghost-work", "oa_id_not_in_dataset"),
                ("unknown-orcid", "orcid_not_in_dataset"),
            ],
        )
    );

    // The forced-set sidecar: the pinned owners' œuvres minus the disowns.
    let mut expected_forced = fx.credited_works(&[s.owner.oa_id]);
    expected_forced.remove(&s.solo);
    expected_forced.remove(&s.shared);
    expected_forced.extend(fx.credited_works(&[s.keep.oa_id, s.drop.oa_id]));
    let forced = run.ledger_json("forced_works.json");
    assert_eq!(forced["cohort"], 2);
    assert_eq!(forced["forced_total"], expected_forced.len());
    assert_eq!(forced["outside_type"], 3);
    assert_eq!(forced["outside_citations"], 1);
    assert_eq!(forced["outside_standard"], 4);
    assert_eq!(forced["claimed"], 2);
    assert_eq!(forced["author_rescues"], 1);
    let mut outside = vec![s.dataset, s.uncited, s.claim_auto, s.claim_merged];
    outside.sort_unstable();
    assert_eq!(forced["outside_wids"], json!(outside));
}

#[test]
fn empty_ledger_is_the_counterfactual() {
    let fx = Fixture::new("ledger-empty");
    let s = &fx.scenario;
    let run = fx.run(&[], &[]);

    assert!(run.resolved().is_empty());
    let typed = run.filter(10, "works");
    assert!(!typed.contains(&s.dataset));
    assert!(!typed.contains(&s.claim_auto));
    assert!(typed.contains(&s.drop_work));
    assert!(!run.filter(11, "works").contains(&s.uncited));
    let works14 = run.filter(14, "works");
    assert!(works14.contains(&s.solo));
    assert!(!works14.contains(&s.hyper));
    assert!(run.filter(14, "authors").contains(&s.drop.oa_id));
    assert!(!run.filter(20, "authors").contains(&s.owner.oa_id));

    let works = run.id_map("works");
    assert!(dm_of(&works, s.drop_work).is_some());
    assert!(dm_of(&works, s.solo).is_some());
    assert!(dm_of(&run.id_map("authors"), s.drop.oa_id).is_some());
    assert!(dm_of(&run.id_map("discarded-authors"), s.owner.oa_id).is_some());

    let m = run.manifest();
    assert!(m.applied.is_empty() && m.skipped.is_empty());
    let forced = run.ledger_json("forced_works.json");
    for field in [
        "cohort",
        "forced_total",
        "outside_standard",
        "claimed",
        "author_rescues",
    ] {
        assert_eq!(forced[field], 0, "{field}");
    }
    assert_eq!(forced["outside_wids"], json!([]));
}

#[test]
fn revoked_events_revert_and_reapply_byte_equal() {
    let fx = Fixture::new("ledger-revoke");
    let s = &fx.scenario;
    let (events, pins) = fx.full_ledger();
    let first = fx.run(&events, &pins);
    let bytes = first.stable_bytes();
    let filters = first.filter_sets();

    // A revoke collapses with its target in the export, so the pipeline sees neither.
    let revoked = keys(&events, &["solo", "twins", "self"]);
    let remaining: Vec<Event> = events
        .iter()
        .filter(|e| !revoked.contains(&e.key))
        .cloned()
        .collect();
    let second = fx.run(&remaining, &pins);
    assert!(second.filter(14, "works").contains(&s.solo));
    assert!(dm_of(&second.id_map("works"), s.drop_work).is_some());
    assert!(dm_of(&second.id_map("authors"), s.drop.oa_id).is_some());
    // Without the author merge the claim under the dropped name has no claimant credit.
    let manifest = second.manifest();
    assert!(manifest.applied.is_disjoint(&revoked));
    assert_eq!(manifest.applied, keys(&events, &["shared", "auto"]));
    assert!(manifest
        .skipped
        .is_superset(&skips(&events, &[("merged", "claimant_not_attributed")])));

    let third = fx.run(&events, &pins);
    assert_eq!(third.stable_bytes(), bytes);
    assert_eq!(third.filter_sets(), filters);
}

#[test]
fn unresolvable_subjects_are_skipped_never_applied() {
    let fx = Fixture::new("ledger-bad");
    let s = &fx.scenario;
    let owner = s.owner.orcid.unwrap();
    let keep = s.keep.orcid.unwrap();
    let disown = Event::disown(owner, s.solo, "solo");
    let revoke_key = disown.key.clone();
    let events = vec![
        disown,
        Event::merge_papers(keep, s.ghost_work, s.not_mine, "ghost-keep-work"),
        Event::merge_papers(keep, s.not_mine, s.ghost_work, "ghost-drop-work"),
        Event::merge_authors(keep, s.ghost_author, s.outsider.oa_id, "ghost-keep-author"),
        Event::revoke(owner, &revoke_key, "stray-revoke"),
    ];
    let run = fx.run(&events, &[owner]);

    // A merge needs its keep in the snapshot; an absent drop side is a no-op rewrite.
    let applied = run.manifest();
    assert_eq!(applied.applied, keys(&events, &["solo", "ghost-drop-work"]));
    assert_eq!(
        applied.skipped,
        skips(
            &events,
            &[
                ("ghost-keep-work", "oa_id_not_in_dataset"),
                ("ghost-keep-author", "oa_id_not_in_dataset"),
            ],
        )
    );
    let stray = keys(&events, &["stray-revoke"]);
    assert!(applied.applied.is_disjoint(&stray));
    assert!(!applied.skipped.iter().any(|(k, _)| stray.contains(k)));

    // A skipped merge leaves no trace: an alias into a ghost keep never exists, so the
    // drop side keeps its own dm id instead of vanishing into an absent entity.
    let resolved = run.resolved();
    assert_eq!(
        resolved.work_aliases,
        [(s.ghost_work, s.not_mine)].into_iter().collect()
    );
    assert!(resolved.author_aliases.is_empty());
    assert!(dm_of(&run.id_map("works"), s.not_mine).is_some());
    assert!(dm_of(&run.id_map("discarded-authors"), s.outsider.oa_id).is_some());
}
