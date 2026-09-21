use std::sync::Arc;

use axum::extract::State;
use hashbrown::{HashMap, HashSet};
use muwo_search::SearchEngine;

use dmove::{Entity, UnsignedNumber, ET};
use rankless_rs::{
    common::EXT_SEP,
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields, Topics},
        derive_links3::HitPapers,
    },
    steps::{
        a1_entity_mapping::{RawYear, YearInterface, Years},
        derive_links2::EraRec,
    },
};
use rankless_trees::{
    extensions::DistinctionText,
    interfacing::{Getters, RootColumns, RootInterfaceable, RootInterfaces},
    io::TreeRunManager,
    metrics::{self, Arg, Kind, MetricDecl, Value, METRICS},
    AttributeLabelUnion,
};

use crate::cohort::BoundCall;
use crate::consts::{MAX_HITS, SEARCH_SIZE};
use crate::responses::{
    PostAttRelatedEntity, RelationGroups, SearchResult, SerializableExt, YearWindow,
};
use crate::search_cache::{fnv64, save_engine, try_load_engine};

pub(crate) type InstTrm = TreeRunManager<(
    Institutions,
    Authors,
    Subfields,
    Countries,
    Sources,
    HitPapers,
)>;
pub(crate) type NameStateMap = HashMap<&'static str, NameState>;
pub(crate) type StatesT = State<(Arc<NameStateMap>, Arc<AttributeLabelUnion>, Arc<InstTrm>)>;

// The search side of a root type: the engine, the responses it answers with, the id maps between
// semantic, OpenAlex, dm and response ids, and the cohort orderings. Every per-entity number is a
// column of the root's `RootColumns`.
pub(crate) struct NameState {
    pub engine: SearchEngine<SEARCH_SIZE>,
    // Ordered by citations descending: response id == citation rank - 1.
    pub responses: Box<[SearchResult]>,
    pub sem_to_dm: HashMap<Arc<str>, u32>,
    pub oa_to_rid: HashMap<u64, u32>,
    dm_to_rid: Box<[u32]>,
    pub orderings: Orderings,
}

// Response ids in descending order of every parameter-free global number but citations (the
// response array itself), keyed by metric id; ties keep citation order.
pub(crate) struct Orderings(HashMap<&'static str, Box<[u32]>>);

pub(crate) trait IsTop: RootInterfaceable + Sized {
    fn is_top(_sr: &SearchResult) -> bool {
        true
    }
}

impl IsTop for Countries {}
impl IsTop for Subfields {}

impl IsTop for HitPapers {
    fn is_top(_sr: &SearchResult) -> bool {
        false
    }
}

impl IsTop for Authors {
    fn is_top(sr: &SearchResult) -> bool {
        crate::consts::FIN_AUTHORS.contains(&sr.semantic_id.as_ref())
    }
}

impl IsTop for Institutions {
    fn is_top(sr: &SearchResult) -> bool {
        let min_citations: u32 = 8_000_000;
        crate::consts::FIN_UNIS.contains(&sr.semantic_id.as_ref()) || sr.citations > min_citations
    }
}

impl IsTop for Sources {
    fn is_top(sr: &SearchResult) -> bool {
        crate::consts::FIN_SOURCES.contains(&sr.semantic_id.as_ref())
    }
}

// The entity's hit papers, capped for the profile.
pub(crate) fn hit_papers(cols: &RootColumns, dm_id: usize) -> &[ET<HitPapers>] {
    let hits = cols.hit_works.0.get(dm_id).map_or(&[][..], |h| &h[..]);
    &hits[..hits.len().min(MAX_HITS)]
}

pub(crate) fn yearly_papers(cols: &RootColumns, dm_id: usize) -> EraRec {
    cols.yearly_papers.get(dm_id).copied().unwrap_or_default()
}

// The first year with a paper; a hit paper's is its own publication year.
pub(crate) fn start_year(etype: &str, dm_id: usize, cols: &RootColumns, gets: &Getters) -> RawYear {
    let idx = if etype == HitPapers::NAME {
        gets.year(&gets.hit_papers[dm_id].to_usize()).to_usize()
    } else {
        yearly_papers(cols, dm_id)
            .iter()
            .position(|&c| c > 0)
            .unwrap_or(0)
    };
    YearInterface::reverse(idx as ET<Years>)
}

pub(crate) fn year_window(
    cols: &RootColumns,
    dm_id: usize,
    year_from: Option<RawYear>,
    year_to: Option<RawYear>,
) -> YearWindow {
    let (from, to, papers, cites) = cols.era_slices(dm_id, year_from, year_to);
    YearWindow {
        from,
        to,
        papers: papers.iter().sum(),
        citations: cites.iter().sum(),
        yearly_papers: papers.to_vec(),
        yearly_cites: cites.to_vec(),
    }
}

// Relations + co-author network are rebuilt on demand from the mmapped top-N tables rather than
// held resident: each entity view reads only its own rows.
pub(crate) fn serializable_ext(
    etype: &str,
    dm_id: usize,
    cols: &RootColumns,
    satts: &AttributeLabelUnion,
    nstates: &NameStateMap,
    gets: &Getters,
) -> SerializableExt {
    let (relations, author_network) = build_relations(etype, dm_id, satts, nstates, gets);
    SerializableExt {
        start_year: start_year(etype, dm_id, cols, gets),
        yearly_papers: yearly_papers(cols, dm_id),
        yearly_cites: cols.yearly_cites[dm_id],
        relations,
        author_network,
    }
}

fn build_relations(
    etype: &str,
    dm_id: usize,
    satts: &AttributeLabelUnion,
    nstates: &NameStateMap,
    gets: &Getters,
) -> (RelationGroups, Box<[u8]>) {
    // TODO: these parameters reappear a bunch and also there are a lot of WET
    // relation defs here, a refactor will soon be in order
    let Some(tr) = gets.columns_for(etype) else {
        return (RelationGroups::default(), Box::new([]));
    };
    // For an author hero, attach the shared-paper count to each co-author from the resident per-author
    // co-authorship map (complete, u8-capped). Other entity types list "top scholars" here, where a
    // pairwise shared count is meaningless, so the map stays empty and the count is omitted.
    let coauthor_counts: HashMap<usize, u32> = if etype == Authors::NAME {
        gets.coathors(dm_id)
            .iter()
            .map(|(a, n)| (a.to_usize(), *n as u32))
            .collect()
    } else {
        HashMap::new()
    };
    // Hit papers don't surface affiliation-country or topic relations (empty placeholders, no mmap).
    let collab_nation = tr
        .aff_countries
        .as_ref()
        .map(|m| resolve_group(m.row(dm_id), Countries::NAME, satts, nstates, gets, None))
        .unwrap_or_default();
    let paper_topics = tr
        .paper_topic
        .as_ref()
        .map(|m| resolve_group(m.row(dm_id), Topics::NAME, satts, nstates, gets, None))
        .unwrap_or_default();
    let citing_topics = tr
        .citing_topic
        .as_ref()
        .map(|m| resolve_group(m.row(dm_id), Topics::NAME, satts, nstates, gets, None))
        .unwrap_or_default();
    let relations = RelationGroups {
        paper_fields: resolve_group(
            tr.paper_sfc.row(dm_id),
            Subfields::NAME,
            satts,
            nstates,
            gets,
            None,
        ),
        citing_fields: resolve_group(
            tr.citing_sfc.row(dm_id),
            Subfields::NAME,
            satts,
            nstates,
            gets,
            None,
        ),
        paper_journals: resolve_group(
            tr.journals.row(dm_id),
            Sources::NAME,
            satts,
            nstates,
            gets,
            None,
        ),
        paper_authors: resolve_group(
            tr.authors.row(dm_id),
            Authors::NAME,
            satts,
            nstates,
            gets,
            Some(&coauthor_counts),
        ),
        collab_nation,
        paper_topics,
        citing_topics,
    };
    let author_network = build_author_network(tr.authors.row(dm_id), gets);
    (relations, author_network)
}

// One top-N row → resolved related entities. dm id 0 is the empty/padding sentinel. Topics carry
// their parent field, resolved via `gets.tsuf`, so the hero can nest them.
fn resolve_group<ID, const N: usize>(
    row: [(u32, ID); N],
    target_etype: &'static str,
    satts: &AttributeLabelUnion,
    nstates: &NameStateMap,
    gets: &Getters,
    counts: Option<&HashMap<usize, u32>>,
) -> Vec<PostAttRelatedEntity>
where
    ID: UnsignedNumber,
{
    let is_topic = target_etype == Topics::NAME;
    row.into_iter()
        .filter_map(|(score, id)| {
            let dm = id.to_usize();
            if dm == 0 {
                return None;
            }
            let att = &satts[target_etype][dm];
            let semantic_id = nstates
                .get(target_etype)
                .and_then(|rs| rs.sem_to_dm.get(att.semantic_id.as_ref()))
                .map(|_| att.semantic_id.to_string())
                .unwrap_or_default();
            let (parent_name, parent_semantic_id) = if is_topic {
                let sf_dm = gets.tsuf(&dm).to_usize();
                if sf_dm != 0 {
                    let p = &satts[Subfields::NAME][sf_dm];
                    let sid = nstates
                        .get(Subfields::NAME)
                        .and_then(|rs| rs.sem_to_dm.get(p.semantic_id.as_ref()))
                        .map(|_| p.semantic_id.to_string());
                    (Some(p.name.to_string()), sid)
                } else {
                    (None, None)
                }
            } else {
                (None, None)
            };
            Some(PostAttRelatedEntity {
                name: att.name.to_string(),
                semantic_id,
                etype: target_etype.to_string(),
                score,
                count: counts.map(|c| c.get(&dm).copied().unwrap_or(0)),
                parent_name,
                parent_semantic_id,
            })
        })
        .collect()
}

// Upper-triangular co-authorship counts among the entity's top paper-authors (same order as the
// `paper-authors` group), each looked up against the resident per-author `coathors` lists.
fn build_author_network<ID, const N: usize>(row: [(u32, ID); N], gets: &Getters) -> Box<[u8]>
where
    ID: UnsignedNumber,
{
    let ids: Vec<usize> = row
        .into_iter()
        .map(|(_, a)| a.to_usize())
        .filter(|&a| a != 0)
        .collect();
    let mut out: Vec<u8> = Vec::new();
    for si in 0..ids.len().saturating_sub(1) {
        let coll_nums = gets.coathors(ids[si]);
        for &taid in ids.iter().skip(si + 1) {
            let mut coll_num: u8 = 0;
            for (ctaid, n) in coll_nums {
                if ctaid.to_usize() == taid {
                    coll_num = *n;
                    break;
                }
            }
            out.push(coll_num);
        }
    }
    out.into()
}

impl Orderings {
    fn new(responses: &[SearchResult], cols: &RootColumns, gets: &Getters) -> Self {
        let n = responses.len() as u32;
        let dm = |rid: u32| responses[rid as usize].dm_id;
        Self(
            METRICS
                .iter()
                .filter(|m| Self::precomputed(m, cols))
                .map(|m| {
                    let read = |rid: u32| match m.read(cols, gets, dm(rid), Arg::None) {
                        Some(Value::Num(v)) => v,
                        _ => 0.0,
                    };
                    (m.id, order_by(0..n, read))
                })
                .collect(),
        )
    }

    fn precomputed(m: &MetricDecl, cols: &RootColumns) -> bool {
        m.id != metrics::CITATIONS
            && m.param.is_none()
            && !m.is_entity_valued()
            && m.kind(cols, |_| false) == Some(Kind::Global)
    }

    pub fn get(&self, call: &BoundCall) -> Option<&[u32]> {
        match call.arg {
            Arg::None => self.0.get(call.decl.id).map(Box::as_ref),
            _ => None,
        }
    }
}

impl NameState {
    pub fn new<E>(
        entif: &RootInterfaces<E>,
        cols: &RootColumns,
        gets: &Getters,
        names_arc: &[Arc<str>],
        sem_ids_arc: &[Arc<str>],
    ) -> Self
    where
        E: RootInterfaceable + IsTop + DistinctionText,
    {
        let (responses, engine_strs) = Self::get_resps(entif, cols, gets, names_arc, sem_ids_arc);
        let cache_dir = gets.stowage.path_from_ns("search-cache");
        let stem = format!("{}-s{SEARCH_SIZE}", E::NAME);
        let bin_path = cache_dir.join(format!("{stem}.bin"));
        let stamp_path = cache_dir.join(format!("{stem}.stamp"));
        let key = fnv64(engine_strs.iter().map(|s| s.as_bytes()));
        let now = std::time::Instant::now();
        let (engine, from_cache) = match try_load_engine(&bin_path, &stamp_path, key) {
            Some(e) => (e, true),
            None => {
                let e = SearchEngine::new(engine_strs.into_iter());
                save_engine(&e, &bin_path, &stamp_path, &cache_dir, key);
                (e, false)
            }
        };
        println!(
            "search engine for {} (n={}) in {}s ({})",
            E::NAME,
            responses.len(),
            now.elapsed().as_secs(),
            if from_cache { "cached" } else { "built" }
        );
        let n = responses.len();
        let mut sem_to_dm = HashMap::with_capacity(n);
        let mut oa_to_rid = HashMap::with_capacity(n);
        let mut dm_to_rid: Box<[u32]> = vec![u32::MAX; names_arc.len()].into_boxed_slice();
        for (i, res) in responses.iter().enumerate() {
            let dm_id = res.dm_id;
            oa_to_rid.insert(res.oa_id, i as u32);
            sem_to_dm.insert(res.semantic_id.clone(), dm_id as u32);
            if dm_id < dm_to_rid.len() {
                dm_to_rid[dm_id] = i as u32;
            }
        }

        let now = std::time::Instant::now();
        let orderings = Orderings::new(&responses, cols, gets);
        println!(
            "orderings for {} (n={}) in {:.2?}",
            E::NAME,
            responses.len(),
            now.elapsed()
        );

        Self {
            engine: engine.into(),
            responses,
            sem_to_dm,
            oa_to_rid,
            dm_to_rid,
            orderings,
        }
    }

    fn get_resps<E>(
        entif: &RootInterfaces<E>,
        cols: &RootColumns,
        gets: &Getters,
        names_arc: &[Arc<str>],
        sem_ids_arc: &[Arc<str>],
    ) -> (Box<[SearchResult]>, Vec<String>)
    where
        E: RootInterfaceable + IsTop + DistinctionText,
    {
        let dist_txt = <E as DistinctionText>::get_distinction_text_arr(entif, gets);
        let raw_cites = <E as DistinctionText>::get_raw_cites_arr(entif, gets);
        let ext_txt = &entif.name_exts.0;
        let mut pairs: Vec<(SearchResult, String)> = names_arc
            .iter()
            .zip(sem_ids_arc.iter())
            .zip(dist_txt.to_vec().into_iter())
            .enumerate()
            .filter(|(i, _)| !sem_ids_arc[*i].is_empty())
            .map(|(i, ((name, semantic_id), dist_txt))| {
                let ext = ext_txt.get(i).map(|s| s.as_str()).unwrap_or("");
                let full_name = dedup_search_text(name, ext);
                let raw_c = raw_cites.get(i).copied().flatten();
                let sr = SearchResult::new(
                    i,
                    name.clone(),
                    semantic_id.clone(),
                    dist_txt,
                    raw_c,
                    entif.oa_id[i],
                    cols,
                );
                (sr, full_name)
            })
            .collect();
        pairs.sort_by_key(|e| u32::MAX - e.0.citations);
        let (responses, engine_strs): (Vec<SearchResult>, Vec<String>) = pairs.into_iter().unzip();
        (responses.into_boxed_slice(), engine_strs)
    }

    pub fn response_id_from_dm(&self, dm_id: usize) -> Option<usize> {
        let rid = *self.dm_to_rid.get(dm_id)?;
        if rid == u32::MAX {
            None
        } else {
            Some(rid as usize)
        }
    }
}

// Descending by value, ties keeping arrival order. Zeros skip the sort: most entities score zero
// on the hit columns, and no ordered metric goes below it.
fn order_by(rids: impl Iterator<Item = u32>, value: impl Fn(u32) -> f64) -> Box<[u32]> {
    let mut scored: Vec<(f64, u32)> = Vec::new();
    let mut zeros: Vec<u32> = Vec::new();
    for rid in rids {
        let v = value(rid);
        debug_assert!(
            v >= 0.0,
            "a precomputed ordering reads a negative value: {v}"
        );
        if v > 0.0 {
            scored.push((v, rid));
        } else {
            zeros.push(rid);
        }
    }
    scored.sort_by(|a, b| b.0.total_cmp(&a.0));
    scored
        .into_iter()
        .map(|(_, rid)| rid)
        .chain(zeros)
        .collect()
}

// The ordering and, aligned with it, the value each id was ordered by; each value is read once.
pub(crate) fn order_keyed(
    rids: impl Iterator<Item = u32>,
    value: impl Fn(u32) -> f64,
) -> (Box<[u32]>, Box<[f64]>) {
    let mut keyed: Vec<(f64, u32)> = rids.map(|rid| (value(rid), rid)).collect();
    keyed.sort_by(|a, b| b.0.total_cmp(&a.0));
    let (values, rids): (Vec<f64>, Vec<u32>) = keyed.into_iter().unzip();
    (rids.into_boxed_slice(), values.into_boxed_slice())
}

fn dedup_search_text(name: &str, ext: &str) -> String {
    let ext_spaced = ext.replace(EXT_SEP, " ");
    let mut seen = HashSet::new();
    name.split_whitespace()
        .chain(ext_spaced.split_whitespace())
        .filter(|w| seen.insert(w.to_lowercase()))
        .collect::<Vec<_>>()
        .join(" ")
}
