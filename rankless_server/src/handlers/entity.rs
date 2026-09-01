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
    steps::{
        a1_entity_mapping::YearInterface,
        derive_links2::{MAX_YEAR, MIN_YEAR},
    },
};
use rankless_trees::{
    interfacing::Getters,
    io::{ShallowQ, ShallowTreesResponse, TreeQ, TreeResponse},
    AttributeLabelUnion,
};

use crate::consts::{CACHEABLE_FROM, MAX_SHALLOW_IDS, N_SUBFIELDS};
use crate::responses::{LadderResp, StatsQ, StatsResp, StatsSubfield, TopResult, ViewResult};
use crate::state::{EntityExt, StatesT};
use crate::util::{cache_header, get_empty, parse_semantic_id};

pub(crate) async fn tree_get(
    Path((root_type, semantic_id)): Path<(String, String)>,
    tree_q: Query<TreeQ>,
    states: StatesT,
) -> (HeaderMap, Json<Option<TreeResponse>>) {
    let mut tq = tree_q.0;
    let (ns_map, _, tm, _) = states.0;
    if let Some(nstate) = ns_map.get(root_type.as_str()) {
        if (root_type == HitPapers::NAME) && (semantic_id == "all") {
            tq.cacheable = Some(true);
        }
        let psid = parse_semantic_id(semantic_id);
        if let Some(&dm_id) = nstate.semantic_id_map.get(psid.as_str()) {
            let dm_id_u = dm_id as usize;
            let ncite = nstate
                .response_id_from_dm(dm_id_u)
                .map(|rid| nstate.responses[rid].citations)
                .unwrap_or(0);
            tq.cacheable = Some(ncite >= CACHEABLE_FROM);
            let resp = tm.get_single_resp(tq, &root_type, dm_id_u);
            return oresp_cached_if_some(resp);
        }
    }
    (cache_header(0), None.into())
}

pub(crate) async fn shallows_get(
    Path(root_type): Path<String>,
    q: Query<ShallowQ>,
    states: StatesT,
) -> (HeaderMap, Json<Option<ShallowTreesResponse>>) {
    let (ns_map, _, tm, _) = states.0;
    let Some(nstate) = ns_map.get(root_type.as_str()) else {
        return (cache_header(0), None.into());
    };
    // ids arrive raw in the query string; the tree layer trusts handler-validated eids
    let mut sq = q.0;
    sq.ids
        .retain(|&eid| nstate.response_id_from_dm(eid).is_some());
    sq.ids.truncate(MAX_SHALLOW_IDS);
    oresp_cached_if_some(tm.get_shallows(sq, &root_type))
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
    let mut out = None;
    if let Some(state) = states.0 .0.get(etype.as_str()) {
        let psid = parse_semantic_id(semantic_id);
        if let Some(&dm_id) = state.semantic_id_map.get(psid.as_str()) {
            let dm_id_u = dm_id as usize;
            if let Some(i) = state.response_id_from_dm(dm_id_u) {
                let srs = &state.responses[i];
                let similars = state.peers[dm_id_u]
                    .iter()
                    .filter(|&&pid| pid != 0)
                    .filter_map(|&pid| {
                        state
                            .response_id_from_dm(pid as usize)
                            .map(|rid| state.responses[rid].clone())
                    })
                    .collect();
                let gets = &states.0 .2.state.gets;
                let meta = compute_meta(etype.as_str(), dm_id_u, gets, &state.exts[i]);
                let vr = ViewResult {
                    similars,
                    ext: state.exts[i].to_serializable(
                        etype.as_str(),
                        dm_id_u,
                        satts,
                        &states.0 .0,
                        gets,
                    ),
                    sr: srs.clone(),
                    meta,
                };
                out = Some(vr)
            }
        };
    }
    Json(out)
}

pub(crate) async fn stats_get(
    Path((etype, semantic_id)): Path<(String, String)>,
    q: Query<StatsQ>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let Some(state) = states.0 .0.get(etype.as_str()) else {
        return get_empty();
    };
    let satts = &states.0 .1;
    let psid = parse_semantic_id(semantic_id);
    let Some(&dm_id) = state.semantic_id_map.get(psid.as_str()) else {
        return get_empty();
    };
    let dm_id_u = dm_id as usize;
    let Some(rid) = state.response_id_from_dm(dm_id_u) else {
        return get_empty();
    };
    let sr = &state.responses[rid];
    let ext = &state.exts[rid];

    // Yearly resolution exists only for the recent era [era_from, era_to]; clamp the request to it.
    let era_from = YearInterface::reverse(MIN_YEAR as u8);
    let era_to = YearInterface::reverse(MAX_YEAR as u8);
    let window_from = q.year_from.unwrap_or(era_from).max(era_from);
    let window_to = q.year_to.unwrap_or(era_to).min(era_to);
    let (window_papers, window_citations, yearly_papers, yearly_cites) = if window_from <= window_to
    {
        let cf = (window_from - era_from) as usize;
        let ct = (window_to - era_from) as usize;
        let yp = ext.yearly_papers[cf..=ct].to_vec();
        let yc = ext.yearly_cites[cf..=ct].to_vec();
        (yp.iter().sum(), yc.iter().sum(), yp, yc)
    } else {
        (0u32, 0u32, Vec::new(), Vec::new())
    };

    // Per-subfield citing profile only exists for root types with peer aux (cit_subfields).
    let mut top_subfields = Vec::new();
    let mut subfield = None;
    if let Some(aux) = states.0 .3.get(etype.as_str()) {
        let row = aux.cit_subfields.row(dm_id_u);
        top_subfields = build_top_subfields(&row, satts, 10);
        if let Some(s) = q.subfield.as_ref() {
            let sf_psid = parse_semantic_id(s.clone());
            if let Some(sf_state) = states.0 .0.get(Subfields::NAME) {
                if let Some(&sf_dm) = sf_state.semantic_id_map.get(sf_psid.as_str()) {
                    let sf_dm = sf_dm as usize;
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
    }

    let resp = StatsResp {
        name: sr.name.clone(),
        semantic_id: sr.semantic_id.clone(),
        dm_id: dm_id_u,
        papers: sr.papers,
        citations: sr.citations,
        era_from,
        era_to,
        window_from,
        window_to,
        window_papers,
        window_citations,
        yearly_papers,
        yearly_cites,
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
    let Some(nstate) = states.0 .0.get(etype.as_str()) else {
        return get_empty();
    };
    let ladder = nstate
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
    ext: &EntityExt,
) -> Option<HashMap<&'static str, String>> {
    if etype == Authors::NAME {
        author_meta(dm_id, gets, ext)
    } else if etype == Institutions::NAME {
        inst_meta(dm_id, gets)
    } else {
        None
    }
}

fn author_meta(
    dm_id: usize,
    gets: &Getters,
    ext: &EntityExt,
) -> Option<HashMap<&'static str, String>> {
    let slug = String::from_utf8(gets.aslugs(dm_id).to_vec()).unwrap_or_default();
    let any_hits = if (gets.author_citing_once(dm_id).len() > 0)
        || (gets.author_citing_direct(dm_id).len() > 0)
        || (ext.hit_papers.len() > 0)
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
