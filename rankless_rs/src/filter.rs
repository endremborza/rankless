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
    csv_iter::par_reduce,
    csv_writers::{authors, institutions, sources, works},
    env_consts::{
        FINAL_YEAR, MIN_AUTHOR_CITE_COUNT, MIN_AUTHOR_WORK_COUNT, MIN_PAPERS_FOR_INST,
        MIN_PAPERS_FOR_SOURCE, START_YEAR,
    },
    oa_structs::{
        post::{Author, Institution, Location},
        ReferencedWork, Work,
    },
    user_ledger::{Outcomes, SnapshotIds, UserLedger},
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
type Edge = (BigId, BigId);

#[derive(Deserialize)]
struct AuthorshipRow {
    author: String,
    institutions: Option<String>,
    parent_id: String,
}

/// The pinned owners' œuvres, which ride through the type and citation screens.
struct ForcedWorks {
    set: WorkSet,
    /// what the step-10 type screen alone would have dropped
    outside_type: Vec<BigId>,
    /// what the step-11 citation screen alone would have dropped
    outside_citations: Vec<BigId>,
}

#[derive(Default)]
struct Step10Acc {
    taken: Vec<BigId>,
    forced: Vec<BigId>,
    outside_type: Vec<BigId>,
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

pub fn main(mut stowage: Stowage) -> io::Result<()> {
    // The ledger is decided here, once, against the raw tables; every read below sees it
    // applied, and the screens know only the pinned owners and their forced œuvre.
    let ul_dir = stowage.paths.user_ledger.clone();
    let ledger = UserLedger::load(&ul_dir)?;
    let ids = SnapshotIds::scan(&stowage, ledger.referenced());
    let (resolved, outcomes) = ledger.resolve(&ids);
    resolved.save(&ul_dir)?;
    stowage.set_ledger(resolved);

    let credited = credited_edges(&stowage, &outcomes);
    outcomes.write_manifest(&ul_dir, &credited)?;
    let oeuvre: WorkSet = credited
        .iter()
        .filter(|(author, _)| outcomes.pins.contains(author))
        .map(|(_, work)| *work)
        .collect();

    let mut forced = work_filter_with_forced(&stowage, 10, oeuvre)?;
    forced.outside_citations =
        filter_step::<ReferencedWork>(&stowage, [works::C, works::C], 11, Some(&forced.set))?;
    filter_step::<Location>(&stowage, [sources::C, works::C], 12, None)?;

    authorship_filter(&stowage, 13, 14, &forced)?;
    let author_rescues = author_filter_with_pins(&stowage, 20, &outcomes.pins)?;
    write_forced_sidecar(&stowage, &outcomes, &credited, &forced, author_rescues)?;
    inst_filter(&stowage, 21)
}

/// (author, work) pairs of the pinned owners and the claimants as the applied ledger
/// credits them: the owners' œuvre is forced through the screens, the claimants' credit
/// settles their claims. Needs its own pass: `authorship_filter` runs on the work filter
/// this feeds.
fn credited_edges(stowage: &Stowage, outcomes: &Outcomes) -> HashSet<Edge> {
    let authors: Arc<HashSet<BigId>> = Arc::new(
        outcomes
            .pins
            .iter()
            .copied()
            .chain(outcomes.claims.iter().map(|c| c.claimant))
            .collect(),
    );
    if authors.is_empty() {
        return HashSet::new();
    }
    par_reduce::<AuthorshipRow, HashSet<Edge>, _, _>(
        stowage,
        works::C,
        works::atts::authorships,
        move |acc, rec| {
            let (Some(work), Some(author)) = (
                oa_id_parse_opt(&rec.parent_id),
                oa_id_parse_opt(&rec.author),
            ) else {
                return;
            };
            if authors.contains(&author) {
                acc.insert((author, work));
            }
        },
        |a, b| a.extend(b),
        Some(4),
    )
}

/// Step 10: a work is taken if it passes the type screen or is forced, forced works
/// keeping the year + retraction predicates only.
fn work_filter_with_forced(
    stowage: &Stowage,
    step_id: u8,
    oeuvre: WorkSet,
) -> io::Result<ForcedWorks> {
    let oeuvre = Arc::new(oeuvre);
    let acc = par_reduce::<Work, Step10Acc, _, _>(
        stowage,
        works::C,
        MAIN_NAME,
        move |acc, o| {
            let Some(id) = o.get_parsed_id() else { return };
            let year = o.publication_year.unwrap_or(0);
            let screened = !o.is_retracted.unwrap_or(false)
                & (year > START_YEAR) // > because 0 is "unknown"
                & (year <= FINAL_YEAR);
            let standard = screened & WORK_KINDS.contains(&o.work_type.as_deref().unwrap_or(""));
            let forced = screened & oeuvre.contains(&id);
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
        },
        Some(10),
    );
    stowage.write_filter(step_id, works::C, acc.taken.into_iter())?;
    Ok(ForcedWorks {
        set: acc.forced.into_iter().collect(),
        outside_type: acc.outside_type,
        outside_citations: Vec::new(),
    })
}

/// Single pass over works::atts::authorships building both:
/// - inst_map (institution → works), written as the institution filter (inst_step_id)
/// - work_author_map (work → authors), written as the work + author filters (person_step_id)
fn authorship_filter(
    stowage: &Stowage,
    inst_step_id: u8,
    person_step_id: u8,
    forced: &ForcedWorks,
) -> io::Result<()> {
    let work_filt = Arc::new(stowage.get_last_filter(works::C).unwrap());

    type BMap = HashMap<BigId, HashSet<BigId>>;

    let (inst_map, work_author_map) = par_reduce::<AuthorshipRow, (BMap, BMap), _, _>(
        stowage,
        works::C,
        works::atts::authorships,
        move |(inst_map, work_author_map), rec| {
            let Some(work_oa) = oa_id_parse_opt(&rec.parent_id) else {
                return;
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

            if let Some(author_oa) = oa_id_parse_opt(&rec.author) {
                work_author_map
                    .entry(work_oa)
                    .or_default()
                    .insert(author_oa);
            }
        },
        |(ia, wa), (ib, wb)| {
            for (k, v) in ib {
                ia.entry(k).or_default().extend(v);
            }
            for (k, v) in wb {
                wa.entry(k).or_default().extend(v);
            }
        },
        Some(4),
    );

    let inst_ids = inst_map
        .into_iter()
        .filter(|(_, works)| works.len() >= MIN_PAPERS_FOR_INST as usize)
        .map(|(inst, _)| inst);
    stowage.write_filter(inst_step_id, institutions::C, inst_ids)?;

    // Forced works keep hyperauthored entries; their co-authors still face the step-20 minimums.
    let mut taken_works = Vec::new();
    let mut taken_authors: HashSet<BigId> = HashSet::new();
    for (work, authors_set) in &work_author_map {
        if authors_set.len() <= MAX_AUTHORS || forced.set.contains(work) {
            taken_works.push(*work);
            taken_authors.extend(authors_set.iter().copied());
        }
    }
    stowage.write_filter(person_step_id, authors::C, taken_authors.into_iter())?;
    stowage.write_filter(person_step_id, works::C, taken_works.into_iter())
}

fn author_filter_with_pins(
    stowage: &Stowage,
    step_id: u8,
    pins: &HashSet<BigId>,
) -> io::Result<usize> {
    let pre_filter = Arc::new(stowage.get_last_filter(authors::C).unwrap());
    let pins = Arc::new(pins.clone());
    let rescued = Arc::new(AtomicUsize::new(0));
    let rescue_count = Arc::clone(&rescued);
    filter_write::<Author, _>(stowage, step_id, authors::C, move |o| {
        if let Some(aid) = o.get_parsed_id() {
            let standard = pre_filter.contains(&aid)
                & (o.cited_by_count.unwrap_or(0) >= MIN_AUTHOR_CITE_COUNT.into())
                & (o.works_count.unwrap_or(0) >= MIN_AUTHOR_WORK_COUNT.into());
            let pinned = pins.contains(&aid);
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

/// The private `forced_works.json` sidecar (aggregates + the forced-only wids); `claimed`
/// counts the applied claims among the works served beyond the standard screens.
fn write_forced_sidecar(
    stowage: &Stowage,
    outcomes: &Outcomes,
    credited: &HashSet<Edge>,
    forced: &ForcedWorks,
    author_rescues: usize,
) -> io::Result<()> {
    let outside: WorkSet = forced
        .outside_type
        .iter()
        .chain(forced.outside_citations.iter())
        .copied()
        .collect();
    let claimed = outcomes
        .claims
        .iter()
        .filter(|c| outside.contains(&c.work) && credited.contains(&(c.claimant, c.work)))
        .count();
    let mut outside_wids: Vec<BigId> = outside.into_iter().collect();
    outside_wids.sort_unstable();

    let sidecar = serde_json::json!({
        "run_id": outcomes.run_id,
        "cohort": outcomes.pins.len(),
        "forced_total": forced.set.len(),
        "outside_standard": outside_wids.len(),
        "outside_type": forced.outside_type.len(),
        "outside_citations": forced.outside_citations.len(),
        "claimed": claimed,
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
    Ok(())
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
    let ids = par_reduce::<T, Vec<BigId>, _, _>(
        stowage,
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

    let source_map = par_reduce::<T, HashMap<u64, HashSet<u64>>, _, _>(
        stowage,
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
