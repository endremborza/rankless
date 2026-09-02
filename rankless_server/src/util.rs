use std::sync::Arc;

use axum::{
    body::Body,
    extract::State,
    http::{header::CACHE_CONTROL, HeaderMap, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::get,
    Router,
};
use percent_encoding::percent_decode_str;
use serde::Serialize;

use crate::consts::STAMP_FNAME;

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

//  frontend's `urlFriendlify` pre-encodes `/` inside the id so a DOI stays a single segment
pub(crate) fn parse_semantic_id(id: String) -> String {
    percent_decode_str(&id).decode_utf8_lossy().into_owned()
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

#[cfg(test)]
mod tests {
    use super::parse_semantic_id;

    #[test]
    fn decodes_any_percent_escape_case_insensitively() {
        assert_eq!(
            parse_semantic_id("10.1038%2Fnmeth.2019".into()),
            "10.1038/nmeth.2019"
        );
        assert_eq!(
            parse_semantic_id("10.1038%2fnmeth.2019".into()),
            "10.1038/nmeth.2019"
        );
        assert_eq!(
            parse_semantic_id("10.1038%2Fnmeth%2E2019".into()),
            "10.1038/nmeth.2019"
        );
        assert_eq!(parse_semantic_id("plain-slug".into()), "plain-slug");
    }
}
