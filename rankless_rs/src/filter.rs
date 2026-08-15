use std::{
    io,
    sync::{
        atomic::{AtomicUsize, Ordering},
        Arc,
    },
};

use hashbrown::{HashMap, HashSet};
use serde::{de::DeserializeOwned, Deserialize};

use crate::{
    common::{oa_id_parse_opt, ParsedId, Stowage, MAIN_NAME},
    csv_writers::{authors, institutions, sources, works},
    env_consts::{
        FINAL_YEAR, MIN_AUTHOR_CITE_COUNT, MIN_AUTHOR_WORK_COUNT, MIN_PAPERS_FOR_INST,
        MIN_PAPERS_FOR_SOURCE, START_YEAR,
    },
    oa_structs::{
        post::{Author, Institution, Location},
        ReferencedWork, Work,
    },
    user_ledger::{build_author_orcid_map, canonical_doi, SkipReason, SkippedEvent, UserLedger},
};

use dmove::BigId;

const MAX_AUTHORS: usize = 20;
const MIN_CITATIONS: usize = 1;
// Proceedings series carry both labels, depending on snapshot vintage (docs/architecture.md).
const WORK_KINDS: [&str; 5] = [
    "article",
    "book",
    "review",
    "book-chapter",
    "conference-paper",
];

const FORCE_DROP_INSTS: [BigId; 2] = [4210095297, 4210109586];

const FORCED_WORKS: &str = "forced_works.json";

type WorkSet = HashSet<BigId>;

#[derive(Deserialize)]
struct AuthorshipRow {
    author: String,
    institutions: Option<String>,
    parent_id: String,
}

/// Pinned-owner œuvres and claim-resolved works, which ride through the type and
/// citation screens.
struct ForcedWorks {
    set: WorkSet,
    /// what the step-10 type screen alone would have dropped
    outside_type: Vec<BigId>,
    /// what the step-11 citation screen alone would have dropped
    outside_citations: Vec<BigId>,
    doi_to_work: HashMap<String, BigId>,
}

struct AppliedClaim {
    key: String,
    wid: BigId,
    via_merge: bool,
}

struct ClaimOutcomes {
    applied: Vec<AppliedClaim>,
    skipped: Vec<SkippedEvent>,
}

#[derive(Default)]
struct Step10Acc {
    taken: Vec<BigId>,
    forced: Vec<BigId>,
    outside_type: Vec<BigId>,
    claim_works: Vec<(String, BigId)>,
}

trait FilterBase {
    const ENTITY_C: &'static str = works::C;
    const ENTITY_ATT: &'static str;
    const MIN: usize = 0;
    const MAX: usize = usize::MAX;
    const HAS_MAX: bool = false;
    const FILTER_TARGETS: bool = true;
    fn iter_edges(&self) -> Vec<[String; 2]>;
}

impl FilterBase for ReferencedWork {
    const ENTITY_ATT: &'static str = works::atts::referenced_works;
    const MIN: usize = MIN_CITATIONS;
    const FILTER_TARGETS: bool = false;

    fn iter_edges(&self) -> Vec<[String; 2]> {
        let pid = self.parent_id.clone().unwrap();
        vec![[self.referenced_work_id.to_string(), pid]]
    }
}

impl FilterBase for Location {
    const ENTITY_ATT: &'static str = works::atts::locations;
    const MIN: usize = MIN_PAPERS_FOR_SOURCE as usize;
    const FILTER_TARGETS: bool = false;

    fn iter_edges(&self) -> Vec<[String; 2]> {
        match &self.source_id {
            Some(source_id) => vec![[source_id.to_string(), self.parent_id.clone().unwrap()]],
            None => Vec::new(),
        }
    }
}

pub fn main(stowage: Stowage) -> io::Result<()> {
    // Before step 10: the œuvre pre-pass and the claim DOIs feed the work filter.
    let mut ledger = UserLedger::load(&stowage)?;
    let orcid_to_oa = build_author_orcid_map(&stowage);
    ledger.resolve_orcids(&orcid_to_oa);
    let ledger = Arc::new(ledger);

    let oeuvre = oeuvre_works(&stowage, &ledger);
    let mut forced = work_filter_with_forced(&stowage, 10, oeuvre, &ledger)?;
    forced.outside_citations =
        filter_step::<ReferencedWork>(&stowage, [works::C, works::C], 11, Some(&forced.set))?;
    filter_step::<Location>(&stowage, [sources::C, works::C], 12, None)?;

    let claims = authorship_filter(&stowage, 13, 14, &ledger, &orcid_to_oa, &forced)?;
    let author_rescues = author_filter_with_pins(&stowage, 20, &ledger)?;
    write_ledger_sidecars(&stowage, &ledger, &forced, &claims, author_rescues)?;
    inst_filter(&stowage, 21)
}

/// Every work an alias-resolved pinned owner is credited on, minus disowned edges. Needs
/// its own pass: `authorship_filter` runs on the work filter this feeds.
fn oeuvre_works(stowage: &Stowage, ledger: &Arc<UserLedger>) -> WorkSet {
    if ledger.owner_pin_oa_ids.is_empty() {
        return WorkSet::new();
    }
    let ledger = Arc::clone(ledger);
    crate::csv_iter::par_reduce::<AuthorshipRow, WorkSet, _, _>(
        &stowage.paths.entity_csvs,
        works::C,
        works::atts::authorships,
        move |acc, rec| {
            if rec.author.is_empty() {
                return;
            }
            let (Some(work_oa), Some(raw_author_oa)) = (
                oa_id_parse_opt(&rec.parent_id),
                oa_id_parse_opt(&rec.author),
            ) else {
                return;
            };
            let author_oa = ledger
                .author_aliases
                .get(&raw_author_oa)
                .copied()
                .unwrap_or(raw_author_oa);
            if ledger.owner_pin_oa_ids.contains(&author_oa)
                && !ledger.removed_edges.contains(&(author_oa, work_oa))
            {
                acc.insert(work_oa);
            }
        },
        |a, b| a.extend(b),
        Some(4),
    )
}

/// Step 10: a work is taken if it passes the type screen or is forced, forced works
/// keeping the year + retraction predicates only. Resolves the claim DOIs on the way.
fn work_filter_with_forced(
    stowage: &Stowage,
    step_id: u8,
    oeuvre: WorkSet,
    ledger: &Arc<UserLedger>,
) -> io::Result<ForcedWorks> {
    let claim_dois: Arc<HashSet<String>> = Arc::new(
        ledger
            .pending_claims
            .iter()
            .map(|(_, _, doi)| doi.clone())
            .collect(),
    );
    let oeuvre = Arc::new(oeuvre);
    let acc = crate::csv_iter::par_reduce::<Work, Step10Acc, _, _>(
        &stowage.paths.entity_csvs,
        works::C,
        MAIN_NAME,
        move |acc, o| {
            let Some(id) = o.get_parsed_id() else { return };
            let claim_doi = o
                .doi
                .as_deref()
                .map(canonical_doi)
                .filter(|d| claim_dois.contains(d));
            if let Some(doi) = &claim_doi {
                acc.claim_works.push((doi.clone(), id));
            }
            let year = o.publication_year.unwrap_or(0);
            let screened = !o.is_retracted.unwrap_or(false)
                & (year > START_YEAR) // > because 0 is "unknown"
                & (year <= FINAL_YEAR);
            let standard = screened & WORK_KINDS.contains(&o.work_type.as_deref().unwrap_or(""));
            let forced = screened & (claim_doi.is_some() | oeuvre.contains(&id));
            if forced {
                acc.forced.push(id);
                if !standard {
                    acc.outside_type.push(id);
                }
            }
            if standard | forced {
                acc.taken.push(id);
            }
        },
        |a, b| {
            a.taken.extend(b.taken);
            a.forced.extend(b.forced);
            a.outside_type.extend(b.outside_type);
            a.claim_works.extend(b.claim_works);
        },
        Some(10),
    );
    stowage.write_filter(step_id, works::C, acc.taken.into_iter())?;
    Ok(ForcedWorks {
        set: acc.forced.into_iter().collect(),
        outside_type: acc.outside_type,
        outside_citations: Vec::new(),
        doi_to_work: acc.claim_works.into_iter().collect(),
    })
}

/// Single pass over works::atts::authorships building both:
/// - inst_map (institution → works), written as the institution filter (inst_step_id)
/// - work_author_map (work → authors), written as the work + author filters (person_step_id)
///
/// work_author_map also settles the claims: one lands iff its work survived every screen
/// and credits the claimant.
fn authorship_filter(
    stowage: &Stowage,
    inst_step_id: u8,
    person_step_id: u8,
    ledger: &Arc<UserLedger>,
    orcid_to_oa: &HashMap<String, BigId>,
    forced: &ForcedWorks,
) -> io::Result<ClaimOutcomes> {
    let work_filt = Arc::new(stowage.get_last_filter(works::C).unwrap());
    let resolve_author = |oa: BigId| ledger.author_aliases.get(&oa).copied().unwrap_or(oa);
    // Alias-credit tracking is scoped to claimants so the side collection stays tiny.
    let claimant_oas: Arc<HashSet<BigId>> = Arc::new(
        ledger
            .pending_claims
            .iter()
            .filter_map(|(_, orcid, _)| orcid_to_oa.get(orcid).copied())
            .map(resolve_author)
            .collect(),
    );
    let claimants = Arc::clone(&claimant_oas);
    let ledger_map = Arc::clone(ledger);

    type BMap = HashMap<BigId, HashSet<BigId>>;

    let (inst_map, work_author_map, alias_credits) =
        crate::csv_iter::par_reduce::<AuthorshipRow, (BMap, BMap, Vec<(BigId, BigId)>), _, _>(
            &stowage.paths.entity_csvs,
            works::C,
            works::atts::authorships,
            move |(inst_map, work_author_map, alias_credits), rec| {
                let work_oa = match oa_id_parse_opt(&rec.parent_id) {
                    Some(w) => w,
                    None => return,
                };
                if !work_filt.contains(&work_oa) {
                    return;
                }

                if let Some(insts) = &rec.institutions {
                    for inst_str in insts.split(';') {
                        if let Some(inst_oa) = oa_id_parse_opt(inst_str) {
                            let entry = inst_map.entry(inst_oa).or_default();
                            if entry.len() < MIN_PAPERS_FOR_INST as usize {
                                entry.insert(work_oa);
                            }
                        }
                    }
                }

                if !rec.author.is_empty() {
                    if let Some(raw_author_oa) = oa_id_parse_opt(&rec.author) {
                        let author_oa = ledger_map
                            .author_aliases
                            .get(&raw_author_oa)
                            .copied()
                            .unwrap_or(raw_author_oa);
                        if !ledger_map.removed_edges.contains(&(author_oa, work_oa)) {
                            if author_oa != raw_author_oa && claimants.contains(&author_oa) {
                                alias_credits.push((work_oa, author_oa));
                            }
                            work_author_map
                                .entry(work_oa)
                                .or_default()
                                .insert(author_oa);
                        }
                    }
                }
            },
            |(ia, wa, ca), (ib, wb, cb)| {
                for (k, v) in ib {
                    ia.entry(k).or_default().extend(v);
                }
                for (k, v) in wb {
                    wa.entry(k).or_default().extend(v);
                }
                ca.extend(cb);
            },
            Some(4),
        );

    let inst_ids = inst_map
        .into_iter()
        .filter(|(_, works)| works.len() >= MIN_PAPERS_FOR_INST as usize)
        .map(|(inst, _)| inst);
    stowage.write_filter(inst_step_id, institutions::C, inst_ids)?;

    // Forced works keep hyperauthored entries; their co-authors still face the step-20 minimums.
    let work_taken = |w: &BigId, authors_set: &HashSet<BigId>| {
        authors_set.len() <= MAX_AUTHORS || forced.set.contains(w)
    };

    let mut taken_works = Vec::new();
    let mut taken_authors: HashSet<BigId> = HashSet::new();
    for (work, authors_set) in &work_author_map {
        if work_taken(work, authors_set) {
            taken_works.push(*work);
            taken_authors.extend(authors_set.iter().copied());
        }
    }

    let alias_credit_set: HashSet<(BigId, BigId)> = alias_credits.into_iter().collect();
    let mut outcomes = ClaimOutcomes {
        applied: Vec::new(),
        skipped: Vec::new(),
    };
    let mut skip = |key: &String, reason: SkipReason| {
        outcomes.skipped.push(SkippedEvent {
            key: key.clone(),
            reason,
        })
    };
    for (key, orcid, doi) in &ledger.pending_claims {
        let Some(&wid) = forced.doi_to_work.get(doi) else {
            skip(key, SkipReason::DoiNotInSnapshot);
            continue;
        };
        let Some(&raw_claimant) = orcid_to_oa.get(orcid) else {
            skip(key, SkipReason::OrcidNotInDataset);
            continue;
        };
        let claimant = resolve_author(raw_claimant);
        let root = *ledger.work_aliases.get(&wid).unwrap_or(&wid);
        match work_author_map.get(&root) {
            Some(authors_set) if work_taken(&root, authors_set) => {
                if authors_set.contains(&claimant) {
                    outcomes.applied.push(AppliedClaim {
                        key: key.clone(),
                        wid: root,
                        via_merge: alias_credit_set.contains(&(root, claimant)),
                    });
                } else {
                    skip(key, SkipReason::ClaimantNotAttributed);
                }
            }
            _ => skip(key, SkipReason::OaIdNotInDataset),
        }
    }

    stowage.write_filter(person_step_id, authors::C, taken_authors.into_iter())?;
    stowage.write_filter(person_step_id, works::C, taken_works.into_iter())?;
    Ok(outcomes)
}

fn author_filter_with_pins(
    stowage: &Stowage,
    step_id: u8,
    ledger: &Arc<UserLedger>,
) -> io::Result<usize> {
    let pre_filter = Arc::new(stowage.get_last_filter(authors::C).unwrap());
    let ledger = Arc::clone(ledger);
    let rescued = Arc::new(AtomicUsize::new(0));
    let rescue_count = Arc::clone(&rescued);
    filter_write::<Author, _>(stowage, step_id, authors::C, move |o| {
        if let Some(aid) = o.get_parsed_id() {
            let standard = pre_filter.contains(&aid)
                & (o.cited_by_count.unwrap_or(0) >= MIN_AUTHOR_CITE_COUNT.into())
                & (o.works_count.unwrap_or(0) >= MIN_AUTHOR_WORK_COUNT.into());
            let pinned = ledger.owner_pin_oa_ids.contains(&aid);
            if pinned & !standard {
                rescue_count.fetch_add(1, Ordering::Relaxed);
            }
            pinned | standard
        } else {
            false
        }
    })?;
    Ok(rescued.load(Ordering::Relaxed))
}

/// `filter_manifest.json` (claim keys applied/skipped, merged into the final manifest by
/// a2) and the private `forced_works.json` (aggregates + the forced-only wids).
fn write_ledger_sidecars(
    stowage: &Stowage,
    ledger: &Arc<UserLedger>,
    forced: &ForcedWorks,
    claims: &ClaimOutcomes,
    author_rescues: usize,
) -> io::Result<()> {
    let outside: WorkSet = forced
        .outside_type
        .iter()
        .chain(forced.outside_citations.iter())
        .copied()
        .collect();
    let (mut claim_auto, mut claim_merged) = (0usize, 0usize);
    for claim in &claims.applied {
        if outside.contains(&claim.wid) {
            match claim.via_merge {
                true => claim_merged += 1,
                false => claim_auto += 1,
            }
        }
    }
    let mut outside_wids: Vec<BigId> = outside.into_iter().collect();
    outside_wids.sort_unstable();

    let sidecar = serde_json::json!({
        "run_id": ledger.run_id,
        "cohort": ledger.owner_pin_oa_ids.len(),
        "forced_total": forced.set.len(),
        "outside_standard": outside_wids.len(),
        "outside_type": forced.outside_type.len(),
        "outside_citations": forced.outside_citations.len(),
        "claim_auto": claim_auto,
        "claim_merged": claim_merged,
        "author_rescues": author_rescues,
        "outside_wids": outside_wids,
    });
    let path = stowage.paths.user_ledger.join(FORCED_WORKS);
    serde_json::to_writer_pretty(
        std::io::BufWriter::new(std::fs::File::create(&path)?),
        &sidecar,
    )
    .map_err(|e| io::Error::new(io::ErrorKind::Other, e))?;
    println!(
        "{FORCED_WORKS}: {} forced, {} outside standard filters",
        forced.set.len(),
        sidecar["outside_standard"]
    );

    let applied_keys = claims.applied.iter().map(|c| c.key.clone()).collect();
    ledger.write_filter_manifest(stowage, applied_keys, claims.skipped.clone())
}

fn inst_filter(stowage: &Stowage, step_id: u8) -> io::Result<()> {
    let pre_filter = Arc::new(stowage.get_last_filter(institutions::C).unwrap());
    filter_write::<Institution, _>(stowage, step_id, institutions::C, move |o| {
        let iid = o.get_parsed_id().expect(&o.display_name);
        !FORCE_DROP_INSTS.contains(&iid) && pre_filter.contains(&iid)
    })
}

fn filter_write<T, F>(
    stowage: &Stowage,
    step_id: u8,
    entity_type: &str,
    closure: F,
) -> io::Result<()>
where
    T: for<'de> Deserialize<'de> + ParsedId + Send + 'static,
    F: Fn(&T) -> bool + Send + Sync + 'static,
{
    let ids = crate::csv_iter::par_reduce::<T, Vec<BigId>, _, _>(
        &stowage.paths.entity_csvs,
        entity_type,
        MAIN_NAME,
        move |acc, rec| {
            if closure(&rec) {
                if let Some(id) = rec.get_parsed_id() {
                    acc.push(id);
                }
            }
        },
        |a, b| {
            a.extend(b);
        },
        Some(10),
    );
    stowage.write_filter(step_id, entity_type, ids.into_iter())
}

fn olen<T>(o: &Option<HashSet<T>>) -> String {
    match o {
        Some(ref l) => l.len().to_string(),
        None => "nothing".to_string(),
    }
}

/// `forced`: works unioned into the written source filter; returns those of them the
/// screen alone would have dropped.
fn filter_step<T>(
    stowage: &Stowage,
    types: [&'static str; 2],
    step_id: u8,
    forced: Option<&WorkSet>,
) -> io::Result<Vec<BigId>>
where
    T: FilterBase + DeserializeOwned + Send + 'static,
{
    let [source_type, target_type] = types;
    let [source_set_o, target_set_o] = types.map(|t| stowage.get_last_filter(t));

    println!(
        "filtering {:?} - {:?} --> {:?}. pre-filtered to {} pre-filtered to {}",
        step_id,
        source_type,
        target_type,
        olen(&source_set_o),
        olen(&target_set_o),
    );

    let source_filt = Arc::new(source_set_o);
    let target_filt = Arc::new(target_set_o);

    let source_map = crate::csv_iter::par_reduce::<T, HashMap<u64, HashSet<u64>>, _, _>(
        &stowage.paths.entity_csvs,
        T::ENTITY_C,
        T::ENTITY_ATT,
        move |local_map, rec| {
            for ends in rec.iter_edges() {
                if let (Some(sk), Some(tk)) = (oa_id_parse_opt(&ends[0]), oa_id_parse_opt(&ends[1]))
                {
                    let pass = source_filt
                        .as_ref()
                        .as_ref()
                        .map_or(true, |s| s.contains(&sk))
                        && target_filt
                            .as_ref()
                            .as_ref()
                            .map_or(true, |s| s.contains(&tk));
                    if pass {
                        let entry: &mut HashSet<u64> = local_map.entry(sk).or_default();
                        if T::FILTER_TARGETS | (entry.len() < T::MIN) | T::HAS_MAX {
                            entry.insert(tk);
                        }
                    }
                }
            }
        },
        |a, b| {
            for (k, v) in b {
                a.entry(k).or_default().extend(v);
            }
        },
        Some(5),
    );

    let mut taken_sources = Vec::new();
    let mut taken_targets: HashSet<u64> = HashSet::new();
    for (k, v) in source_map.iter() {
        if (v.len() >= T::MIN) && (v.len() <= T::MAX) {
            taken_sources.push(*k);
            if T::FILTER_TARGETS {
                taken_targets.extend(v);
            }
        }
    }

    let mut screened_out = Vec::new();
    if let Some(forced_set) = forced {
        for w in forced_set {
            let in_range = source_map
                .get(w)
                .map_or(false, |v| (v.len() >= T::MIN) && (v.len() <= T::MAX));
            if !in_range {
                screened_out.push(*w);
                taken_sources.push(*w);
            }
        }
    }

    if T::FILTER_TARGETS {
        stowage.write_filter(step_id, target_type, &mut taken_targets.into_iter())?;
    }
    stowage.write_filter(step_id, source_type, &mut taken_sources.into_iter())?;
    Ok(screened_out)
}
