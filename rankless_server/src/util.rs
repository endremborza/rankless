use std::sync::Arc;

use axum::{
    body::Body,
    extract::State,
    http::{header::CACHE_CONTROL, HeaderMap, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::get,
    Router,
};
use serde::Serialize;

use crate::consts::STAMP_FNAME;
use crate::state::{NameState, NameStateMap};

pub(crate) fn cache_header(mins: usize) -> HeaderMap {
    let mut headers = HeaderMap::new();
    headers.insert(
        CACHE_CONTROL,
        HeaderValue::from_str(&format!("public, max-age={}", mins * 60)).unwrap(),
    );
    headers
}

pub(crate) fn static_router<O: Serialize>(o: &O) -> Router {
    let arc: Arc<str> = Arc::from(serde_json::to_string(o).unwrap().as_str());
    Router::new().route("/", get(state_get)).with_state(arc)
}

/// Build + data identity: `<git commit>|<compile env>|<data-root stamp>`.
/// The warm-fleet preflight compares this across boxes — it proves the
/// *running* process is the expected build serving the expected data.
pub(crate) fn version_stamp(data_root: &str) -> String {
    let stamp = std::fs::read_to_string(std::path::Path::new(data_root).join(STAMP_FNAME))
        .map(|s| s.trim().to_string())
        .unwrap_or_else(|_| "unstamped".to_string());
    format!(
        "{}|{}|{}",
        env!("GIT_COMMIT"),
        rankless_rs::env_consts::RANKLESS_ENV,
        stamp
    )
}

/// Semantic id → its entity type's state and dmove id. Callers get the id
/// already percent-decoded: the client encodes it once, axum decodes it once.
pub(crate) fn resolve_dm<'a>(
    ns_map: &'a NameStateMap,
    etype: &str,
    sem_id: &str,
) -> Option<(&'a NameState, usize)> {
    let nstate = ns_map.get(etype)?;
    Some((nstate, *nstate.sem_to_dm.get(sem_id)? as usize))
}

/// As `resolve_dm`, plus the response id — `None` for an entity that has a
/// dmove id but no search response (below the response cutoff).
pub(crate) fn resolve_entity<'a>(
    ns_map: &'a NameStateMap,
    etype: &str,
    sem_id: &str,
) -> Option<(&'a NameState, usize, usize)> {
    let (nstate, dm_id) = resolve_dm(ns_map, etype, sem_id)?;
    Some((nstate, dm_id, nstate.response_id_from_dm(dm_id)?))
}

pub(crate) fn get_empty() -> (HeaderMap, Response) {
    (
        HeaderMap::new(),
        (StatusCode::NOT_FOUND, "no such entity").into_response(),
    )
}

pub(crate) fn bad_request(msg: &'static str) -> (HeaderMap, Response) {
    (
        HeaderMap::new(),
        (StatusCode::BAD_REQUEST, msg).into_response(),
    )
}

async fn state_get(str_state: State<Arc<str>>) -> (HeaderMap, Response<Body>) {
    (cache_header(60), str_state.to_string().into_response())
}
