use std::sync::Arc;

use axum::{
    extract::{Path, Query, State},
    http::HeaderMap,
    response::{IntoResponse, Response},
    Json,
};
use hashbrown::HashMap;
use rand::seq::SliceRandom;

use dmove::{Entity, ET};
use rankless_rs::{
    gen::{
        a1_entity_mapping::{Authors, Institutions, Subfields},
        a2_init_atts::AuthorOrcids,
        derive_links3::HitPapers,
    },
    ladder::LADDER_PCT_BANDS,
};
use rankless_trees::{
    interfacing::Getters,
    io::{TreeQ, TreeResponse},
    metrics::era_bounds,
    AttributeLabelUnion,
};

use crate::consts::{CACHEABLE_FROM, N_SUBFIELDS};
use crate::responses::{LadderResp, StatsQ, StatsResp, StatsSubfield, TopResult, ViewResult};
use crate::state::{hit_papers, serializable_ext, year_window, StatesT};
use crate::util::{cache_header, get_empty, resolve_dm, resolve_entity, root_cols};

pub(crate) async fn tree_get(
    Path((root_type, semantic_id)): Path<(String, String)>,
    tree_q: Query<TreeQ>,
    states: StatesT,
) -> (HeaderMap, Json<Option<TreeResponse>>) {
    let mut tq = tree_q.0;
    let (ns_map, _, tm) = states.0;
    if (root_type == HitPapers::NAME) && (semantic_id == "all") {
        tq.cacheable = Some(true);
    }
    let Some((nstate, dm_id)) = resolve_dm(&ns_map, &root_type, &semantic_id) else {
        return (cache_header(0), None.into());
    };
    let ncite = nstate
        .response_id_from_dm(dm_id)
        .map(|rid| nstate.responses[rid].citations)
        .unwrap_or(0);
    tq.cacheable = Some(ncite >= CACHEABLE_FROM);
    oresp_cached_if_some(tm.get_single_resp(tq, &root_type, dm_id))
}

fn oresp_cached_if_some<T>(resp: Option<T>) -> (HeaderMap, Json<Option<T>>) {
    let mins = if resp.is_some() { 60 } else { 0 };
    (cache_header(mins), Json(resp))
}

pub(crate) async fn tops_get(tops_state: State<Arc<Vec<TopResult>>>) -> Json<Vec<TopResult>> {
    let mut rng = rand::thread_rng();
    const TOP_N: usize = 5;
    let out = tops_state
        .iter()
        .map(|e| TopResult {
            name: e.name.clone(),
            entities: e
                .entities
                .choose_multiple(&mut rng, TOP_N)
                .map(Clone::clone)
                .collect(),
        })
        .collect();
    Json(out)
}

pub(crate) async fn view_get(
    Path((etype, semantic_id)): Path<(String, String)>,
    states: StatesT,
) -> Json<Option<ViewResult>> {
    let satts = &states.0 .1;
    let Some((state, dm_id, rid)) = resolve_entity(&states.0 .0, &etype, &semantic_id) else {
        return Json(None);
    };
    let cols = root_cols(&states, &etype);
    let similars = cols.peers[dm_id]
        .iter()
        .filter(|&&pid| pid != 0)
        .filter_map(|&pid| {
            state
                .response_id_from_dm(pid as usize)
                .map(|r| state.responses[r].clone())
        })
        .collect();
    let gets = &states.0 .2.state.gets;
    Json(Some(ViewResult {
        similars,
        ext: serializable_ext(etype.as_str(), dm_id, cols, satts, &states.0 .0, gets),
        sr: state.responses[rid].clone(),
        meta: compute_meta(etype.as_str(), dm_id, gets, hit_papers(cols, dm_id)),
    }))
}

pub(crate) async fn stats_get(
    Path((etype, semantic_id)): Path<(String, String)>,
    q: Query<StatsQ>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let satts = &states.0 .1;
    let Some((state, dm_id, rid)) = resolve_entity(&states.0 .0, &etype, &semantic_id) else {
        return get_empty();
    };
    let sr = &state.responses[rid];
    let (era_from, era_to) = era_bounds();
    let window = year_window(root_cols(&states, &etype), dm_id, q.year_from, q.year_to);

    // Per-subfield citing profile only exists for root types carrying the subfield profiles.
    let mut top_subfields = Vec::new();
    let mut subfield = None;
    let sf_profiles = states
        .0
         .2
        .state
        .gets
        .columns_for(etype.as_str())
        .and_then(|c| c.subfields.as_ref());
    if let Some(sfs) = sf_profiles {
        let row = sfs.citing.row(dm_id);
        top_subfields = build_top_subfields(&row, satts, 10);
        if let Some(sf_sem) = q.subfield.as_ref() {
            if let Some((_, sf_dm)) = resolve_dm(&states.0 .0, Subfields::NAME, sf_sem) {
                let att = &satts[Subfields::NAME][sf_dm];
                subfield = Some(StatsSubfield {
                    name: att.name.clone(),
                    semantic_id: att.semantic_id.clone(),
                    dm_id: sf_dm,
                    citations: row[sf_dm],
                });
            }
        }
    }

    let resp = StatsResp {
        name: sr.name.clone(),
        semantic_id: sr.semantic_id.clone(),
        dm_id,
        papers: sr.papers,
        citations: sr.citations,
        era_from,
        era_to,
        window,
        top_subfields,
        subfield,
    };
    (cache_header(60), Json(resp).into_response())
}

fn build_top_subfields(
    row: &[u32],
    satts: &AttributeLabelUnion,
    limit: usize,
) -> Vec<StatsSubfield> {
    let sf_atts = &satts[Subfields::NAME];
    let mut scored: Vec<(usize, u32)> = (0..N_SUBFIELDS)
        .map(|si| (si, row[si]))
        .filter(|&(_, c)| c > 0)
        .collect();
    scored.sort_unstable_by(|a, b| b.1.cmp(&a.1));
    scored
        .into_iter()
        .take(limit)
        .map(|(si, c)| {
            let att = &sf_atts[si];
            StatsSubfield {
                name: att.name.clone(),
                semantic_id: att.semantic_id.clone(),
                dm_id: si,
                citations: c,
            }
        })
        .collect()
}

pub(crate) async fn ladder_get(
    Path(etype): Path<String>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let Some(cols) = states.2.state.gets.columns_for(etype.as_str()) else {
        return get_empty();
    };
    let ladder = cols
        .cit_rank_ladder
        .iter()
        .map(|row| row.iter().map(|&t| (t != u32::MAX).then_some(t)).collect())
        .collect();
    let resp = LadderResp {
        pct_bands: &LADDER_PCT_BANDS,
        ladder,
    };
    (cache_header(1440), Json(resp).into_response())
}

fn compute_meta(
    etype: &str,
    dm_id: usize,
    gets: &Getters,
    hits: &[ET<HitPapers>],
) -> Option<HashMap<&'static str, String>> {
    if etype == Authors::NAME {
        author_meta(dm_id, gets, hits)
    } else if etype == Institutions::NAME {
        inst_meta(dm_id, gets)
    } else {
        None
    }
}

fn author_meta(
    dm_id: usize,
    gets: &Getters,
    hits: &[ET<HitPapers>],
) -> Option<HashMap<&'static str, String>> {
    let slug = String::from_utf8(gets.aslugs(dm_id).to_vec()).unwrap_or_default();
    let any_hits = if (gets.author_citing_once(dm_id).len() > 0)
        || (gets.author_citing_direct(dm_id).len() > 0)
        || !hits.is_empty()
    {
        "1"
    } else {
        "0"
    };
    let na_orcid: ET<AuthorOrcids> = <ET<AuthorOrcids> as Default>::default();
    let orcid_o = gets.author_orcids(&dm_id);
    let orcid = if orcid_o == &na_orcid {
        ""
    } else {
        std::str::from_utf8(orcid_o).unwrap_or("")
    };
    let kvs = vec![
        ("wikiSlug", slug),
        ("rawCites", gets.raw_cites(&dm_id).to_string()),
        ("rawPapers", gets.raw_works(&dm_id).to_string()),
        ("anyHits", any_hits.to_string()),
        ("orcid", orcid.to_string()),
    ];
    Some(HashMap::from_iter(kvs.into_iter()))
}

fn inst_meta(dm_id: usize, gets: &Getters) -> Option<HashMap<&'static str, String>> {
    let loc = gets.iloc(&dm_id);
    let kvs = vec![("lat", loc.0.to_string()), ("lon", loc.1.to_string())];
    Some(HashMap::from_iter(kvs.into_iter()))
}
