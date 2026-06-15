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

pub(crate) fn parse_semantic_id(id: String) -> String {
    id.replace("%2F", "/")
}

pub(crate) fn get_empty() -> (HeaderMap, Response) {
    (
        HeaderMap::new(),
        (StatusCode::NOT_FOUND, "no such entity").into_response(),
    )
}

async fn state_get(str_state: State<Arc<str>>) -> (HeaderMap, Response<Body>) {
    (cache_header(60), str_state.to_string().into_response())
}
