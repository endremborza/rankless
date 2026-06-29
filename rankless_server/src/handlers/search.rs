use std::cmp::{max, min};

use axum::{
    body::Body,
    extract::{Path, Query},
    http::{HeaderMap, StatusCode},
    response::{IntoResponse, Response},
    Json,
};

use dmove::{Entity, EntityMutableMapperBackend, UnsignedNumber, VattReadingArcMap, ET};
use rankless_rs::{
    gen::{
        a1_entity_mapping::{Authors, Countries, Institutions, Sources, Subfields},
        a2_init_atts::{AuthorOrcids, WorkDois},
        derive_links3::HitPapers,
    },
    steps::{a1_entity_mapping::YearInterface, a2_init_atts::OrcidType},
};
use rankless_trees::io::ManFileHandle;

use crate::consts::MAX_SLICE;
use crate::responses::{
    AuthoredQ, AuthoredResp, BasicQ, ResolveAuthorQ, ResolveAuthorResp, ResolveWorkQ,
    ResolveWorkResp, SearchResult, UnionSearchResult,
};
use crate::state::StatesT;
use crate::util::{cache_header, get_empty, parse_semantic_id};

pub(crate) async fn name_get(
    Path(etype): Path<String>,
    q: Query<BasicQ>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let q_string = q.q.as_deref().unwrap_or("");
    let ns_map = &states.0 .0;
    if etype == "all" {
        const UNION_ORDER: [&str; 6] = [
            Authors::NAME,
            Institutions::NAME,
            Sources::NAME,
            Countries::NAME,
            Subfields::NAME,
            HitPapers::NAME,
        ];
        let out: Vec<UnionSearchResult> = UNION_ORDER
            .iter()
            .filter_map(|&rt| ns_map.get(rt).map(|state| (rt, state)))
            .flat_map(|(rt, state)| {
                state
                    .engine
                    .query(q_string)
                    .into_iter()
                    .filter_map(move |e| {
                        state.responses.get(e as usize).map(|sr| UnionSearchResult {
                            sr: sr.clone(),
                            root_type: rt,
                        })
                    })
            })
            .collect();
        return (cache_header(60), Json(out).into_response());
    }
    if let Some(state) = ns_map.get(etype.as_str()) {
        let top_n_inds = state.engine.query(q_string);
        let resp: Json<Vec<SearchResult>> = Json(
            top_n_inds
                .into_iter()
                .filter(|e| (*e as usize) < state.responses.len())
                .map(|e| state.responses[e as usize].clone())
                .collect(),
        );
        (cache_header(60), resp.into_response())
    } else {
        get_empty()
    }
}

pub(crate) async fn slice_get(
    Path((etype, pstart, pend)): Path<(String, usize, usize)>,
    states: StatesT,
) -> Response<Body> {
    if let Some(state) = states.0 .0.get(etype.as_str()) {
        let start = min(pstart, state.responses.len().saturating_sub(1));
        let end = min(
            max(start + 1, min(start + MAX_SLICE, pend)),
            state.responses.len(),
        );
        Json(&state.responses[start..end]).into_response()
    } else {
        (StatusCode::NOT_FOUND, "no such entity").into_response()
    }
}

pub(crate) async fn sem_id_get(
    Path((etype, oa_id)): Path<(String, u64)>,
    states: StatesT,
) -> Json<[Option<String>; 1]> {
    let mut out = None;
    if let Some(nstate) = states.0 .0.get(etype.as_str()) {
        if let Some(&rid) = nstate.oa_id_map.get(&oa_id) {
            let s = nstate.responses[rid as usize].semantic_id.to_string();
            out = Some(s);
        }
    }
    Json([out])
}

pub(crate) async fn orcid_get(
    Path(orcid_id): Path<String>,
    states: StatesT,
) -> Json<Option<SearchResult>> {
    let mut out = None;
    let obytes: ET<AuthorOrcids> = orcid_id
        .into_bytes()
        .into_iter()
        .collect::<Vec<u8>>()
        .try_into()
        .unwrap_or(<ET<AuthorOrcids> as Default>::default());
    if let Some(&a_dm_id) = states.0 .2.state.gets.orcid_map.get(&obytes) {
        if let Some(nstate) = states.0 .0.get(Authors::NAME) {
            if let Some(a_rid) = nstate.response_id_from_dm(a_dm_id) {
                let s = nstate.responses[a_rid].clone();
                out = Some(s);
            }
        }
    }
    Json(out)
}

pub(crate) async fn resolve_work_get(
    q: Query<ResolveWorkQ>,
    states: StatesT,
) -> (StatusCode, Json<Option<ResolveWorkResp>>) {
    let trm = &states.0 .2;
    let gets = &trm.state.gets;
    let wid = if let Some(wid) = q.wid {
        if wid >= gets.work_oa.len() {
            return (StatusCode::NOT_FOUND, Json(None));
        }
        wid
    } else if let Some(oa_id) = q.oa_id {
        match gets.work_oa.iter().position(|&x| x == oa_id) {
            Some(i) => i,
            None => return (StatusCode::NOT_FOUND, Json(None)),
        }
    } else if q.doi.is_some() {
        // Phase 1: doi-only lookup not implemented (no reverse index built);
        // claim flow stores doi as primary identifier without resolution.
        return (StatusCode::NOT_IMPLEMENTED, Json(None));
    } else {
        return (StatusCode::BAD_REQUEST, Json(None));
    };
    let mut wname_handler: ManFileHandle = trm.get_file_handle();
    let mut doi_handler: VattReadingArcMap<WorkDois> = trm.get_file_handle();
    let name = wname_handler
        .get_via_mut(&wid)
        .unwrap_or_else(|| "Unknown".to_string());
    let doi = doi_handler.get_via_mut(&wid).unwrap_or_default();
    let resp = ResolveWorkResp {
        oa_id: gets.work_oa[wid],
        wid,
        doi,
        year: YearInterface::reverse(*gets.year(&wid)),
        name,
    };
    (StatusCode::OK, Json(Some(resp)))
}

pub(crate) async fn resolve_author_get(
    q: Query<ResolveAuthorQ>,
    states: StatesT,
) -> (StatusCode, Json<Option<ResolveAuthorResp>>) {
    let nstate = match states.0 .0.get(Authors::NAME) {
        Some(s) => s,
        None => return (StatusCode::NOT_FOUND, Json(None)),
    };
    let gets = &states.0 .2.state.gets;
    let dm_id: usize = if let Some(d) = q.dm_id {
        d
    } else if let Some(sem_id) = &q.semantic_id {
        let psid = parse_semantic_id(sem_id.clone());
        match nstate.semantic_id_map.get(psid.as_str()) {
            Some(&d) => d as usize,
            None => return (StatusCode::NOT_FOUND, Json(None)),
        }
    } else if let Some(orcid_str) = &q.orcid {
        let obytes: OrcidType = match orcid_str.as_bytes().try_into() {
            Ok(b) => b,
            Err(_) => return (StatusCode::BAD_REQUEST, Json(None)),
        };
        match gets.orcid_map.get(&obytes) {
            Some(&d) => d,
            None => return (StatusCode::NOT_FOUND, Json(None)),
        }
    } else if let Some(oa_id) = q.oa_id {
        match nstate.oa_id_map.get(&oa_id) {
            Some(&rid) => nstate.responses[rid as usize].dm_id,
            None => return (StatusCode::NOT_FOUND, Json(None)),
        }
    } else {
        return (StatusCode::BAD_REQUEST, Json(None));
    };
    let rid = match nstate.response_id_from_dm(dm_id) {
        Some(r) => r,
        None => return (StatusCode::NOT_FOUND, Json(None)),
    };
    let sr = &nstate.responses[rid];
    let na_orcid = OrcidType::default();
    let orcid = if dm_id < <Authors as Entity>::N {
        let bytes = *gets.author_orcids(&dm_id);
        if bytes == na_orcid {
            None
        } else {
            String::from_utf8(bytes.to_vec()).ok()
        }
    } else {
        None
    };
    let resp = ResolveAuthorResp {
        oa_id: sr.oa_id,
        dm_id: sr.dm_id,
        semantic_id: sr.semantic_id.to_string(),
        orcid,
        name: sr.name.to_string(),
    };
    (StatusCode::OK, Json(Some(resp)))
}

// Does the author behind `orcid` author work `wid`? Backs the ledger's merge_papers
// authorization: a user may only merge papers they authored (checked against their
// MainWorkMarker production set). Unknown orcid / malformed input -> false (deny).
pub(crate) async fn authored_get(q: Query<AuthoredQ>, states: StatesT) -> Json<AuthoredResp> {
    let gets = &states.0 .2.state.gets;
    let obytes: OrcidType = match q.orcid.as_bytes().try_into() {
        Ok(b) => b,
        Err(_) => return Json(AuthoredResp { authored: false }),
    };
    let authored = match gets.orcid_map.get(&obytes) {
        Some(&aid) => gets
            .aworks(ET::<Authors>::from_usize(aid))
            .iter()
            .any(|&w| w.to_usize() == q.wid),
        None => false,
    };
    Json(AuthoredResp { authored })
}
