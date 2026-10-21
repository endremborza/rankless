use std::sync::LazyLock;

use axum::{routing::get, Router};
use wiretypes::wire;

use crate::handlers::{
    authored_get, intersect_get, ladder_get, metric_values_get, name_get, orcid_get, paper_profile,
    peers_get, resolve_author_get, resolve_work_get, sem_id_get, slice_get, stats_get, tree_get,
    view_get, where_get, works_get,
};
use crate::state::{FullStates, TreeStates};

pub(crate) const API_PREFIX: &str = "/v1";

/// Every path the backend serves, in axum's syntax (`:param`, `*rest`).
#[wire]
pub(crate) static API_ROUTES: LazyLock<Vec<String>> = LazyLock::new(|| {
    [TREE_PATHS, SERVER_PATHS, NESTED_PATHS]
        .concat()
        .iter()
        .map(|path| format!("{API_PREFIX}{path}"))
        .collect()
});

macro_rules! route_table {
    ($paths:ident, $build:ident<$state:ty> { $($path:literal => $handler:ident),+ $(,)? }) => {
        const $paths: &[&str] = &[$($path),+];

        pub(crate) fn $build() -> Router<$state> {
            Router::new()$(.route($path, get($handler)))+
        }
    };
}

macro_rules! nest_table {
    ($paths:ident, $build:ident { $($path:literal => $router:ident),+ $(,)? }) => {
        const $paths: &[&str] = &[$($path),+];

        pub(crate) fn $build($($router: Router),+) -> Router {
            Router::new()$(.nest($path, $router))+
        }
    };
}

route_table!(TREE_PATHS, tree_routes<TreeStates> {
    "/names/:etype" => name_get,
    "/slice/:etype/:from/:to" => slice_get,
    "/where" => where_get,
    "/metrics/:etype" => metric_values_get,
    "/stats/:etype/:semantic_id" => stats_get,
    "/sem-id-via-oa/:etype/:oa_id" => sem_id_get,
    "/peers/:etype/:semantic_id" => peers_get,
    "/ladder/:etype" => ladder_get,
    "/trees/:root_type/:semantic_id" => tree_get,
});

route_table!(SERVER_PATHS, server_routes<FullStates> {
    "/views/:etype/:semantic_id" => view_get,
    "/orcid/:orcid_id" => orcid_get,
    "/resolve/work" => resolve_work_get,
    "/resolve/author" => resolve_author_get,
    "/authored" => authored_get,
    "/paper-profile/:asem" => paper_profile,
    "/works/:etype/:semantic_id/:from" => works_get,
    "/works-intersect/*spec" => intersect_get,
});

nest_table!(NESTED_PATHS, nested_routes {
    "/counts" => counts,
    "/columns" => columns,
    "/tops" => tops,
    "/specs" => specs,
});
