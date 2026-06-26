use std::{io, sync::Arc};

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
    user_ledger::{build_author_orcid_map, UserLedger},
};

use dmove::BigId;

// for testing
pub const FIX_AUTHORS: [BigId; 7] = [
    5064297795, // César A. Hidalgo
    5005839111, // Balázs Lengyel
    5078032253, // Orsolya Vásárhelyi
    5045634725, // Attila Chikán
    5082456380, // Vera Messing
    5017880363, // Gábor Békés
    5042797356, // Endre Márk Borza
];

const MAX_AUTHORS: usize = 20;
const MIN_CITATIONS: usize = 1;
const WORK_KINDS: [&str; 3] = ["article", "book", "review"];

const FORCE_DROP_INSTS: [BigId; 2] = [4210095297, 4210109586];

#[derive(Deserialize)]
struct AuthorshipRow {
    author: String,
    institutions: Option<String>,
    parent_id: String,
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
    single_filter(&stowage, 10)?;
    filter_step::<ReferencedWork>(&stowage, [works::C, works::C], 11)?;
    filter_step::<Location>(&stowage, [sources::C, works::C], 12)?;
    // Load ledger before the authorship pass so alias resolution and removed edges
    // are applied when counting both institution papers and per-work author sets.
    let mut ledger = UserLedger::load(&stowage)?;
    let orcid_to_oa = build_author_orcid_map(&stowage);
    ledger.resolve_orcids(&orcid_to_oa);
    let ledger = Arc::new(ledger);

    authorship_filter(&stowage, 13, 14, &ledger)?;
    author_filter_with_pins(&stowage, 20, &ledger)?;
    inst_filter(&stowage, 21)
}

/// Single pass over works::atts::authorships that simultaneously builds:
/// - inst_map (institution → works): used to write the institution filter (inst_step_id)
/// - work_author_map (work → authors): used to write the work + author filters (person_step_id)
fn authorship_filter(
    stowage: &Stowage,
    inst_step_id: u8,
    person_step_id: u8,
    ledger: &Arc<UserLedger>,
) -> io::Result<()> {
    let work_filt = Arc::new(stowage.get_last_filter(works::C).unwrap());
    let ledger = Arc::clone(ledger);

    type BMap = HashMap<BigId, HashSet<BigId>>;

    let (inst_map, work_author_map) =
        crate::csv_iter::par_reduce::<AuthorshipRow, (BMap, BMap), _, _>(
            &stowage.paths.entity_csvs,
            works::C,
            works::atts::authorships,
            move |(inst_map, work_author_map), rec| {
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
                        let author_oa = ledger
                            .author_aliases
                            .get(&raw_author_oa)
                            .copied()
                            .unwrap_or(raw_author_oa);
                        if !ledger.removed_edges.contains(&(author_oa, work_oa)) {
                            work_author_map
                                .entry(work_oa)
                                .or_default()
                                .insert(author_oa);
                        }
                    }
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

    let mut taken_works = Vec::new();
    let mut taken_authors: HashSet<BigId> = HashSet::new();
    for (work, authors_set) in &work_author_map {
        if authors_set.len() <= MAX_AUTHORS {
            taken_works.push(*work);
            taken_authors.extend(authors_set.iter().copied());
        }
    }
    stowage.write_filter(person_step_id, authors::C, taken_authors.into_iter())?;
    stowage.write_filter(person_step_id, works::C, taken_works.into_iter())?;
    Ok(())
}

fn single_filter(stowage: &Stowage, step_id: u8) -> io::Result<()> {
    filter_write::<Work, _>(stowage, step_id, works::C, |o| {
        !o.is_retracted.unwrap_or(false)
            & WORK_KINDS.contains(&o.work_type.as_deref().unwrap_or(""))
            & (o.publication_year.unwrap_or(0) > START_YEAR) // > because 0 is "unknown"
            & (o.publication_year.unwrap_or(0) <= FINAL_YEAR)
    })
}

fn author_filter_with_pins(
    stowage: &Stowage,
    step_id: u8,
    ledger: &Arc<UserLedger>,
) -> io::Result<()> {
    let pre_filter = Arc::new(stowage.get_last_filter(authors::C).unwrap());
    let ledger = Arc::clone(ledger);
    filter_write::<Author, _>(stowage, step_id, authors::C, move |o| {
        if let Some(aid) = o.get_parsed_id() {
            FIX_AUTHORS.contains(&aid)
                | ledger.owner_pin_oa_ids.contains(&aid)
                | (pre_filter.contains(&aid)
                    & (o.cited_by_count.unwrap_or(0) >= MIN_AUTHOR_CITE_COUNT.into())
                    & (o.works_count.unwrap_or(0) >= MIN_AUTHOR_WORK_COUNT.into()))
        } else {
            false
        }
    })
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

fn filter_step<T>(stowage: &Stowage, types: [&'static str; 2], step_id: u8) -> io::Result<()>
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

    if T::FILTER_TARGETS {
        stowage.write_filter(step_id, target_type, &mut taken_targets.into_iter())?;
    }
    stowage.write_filter(step_id, source_type, &mut taken_sources.into_iter())?;
    Ok(())
}
