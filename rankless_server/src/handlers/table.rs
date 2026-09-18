use std::cmp::{max, min};
use std::sync::Arc;

use axum::{
    extract::{Path, Query},
    http::HeaderMap,
    response::{IntoResponse, Response},
    Json,
};
use hashbrown::HashMap;

use rankless_expr::{parse_call, parse_calls, parse_where};
use rankless_trees::metrics::{Cost, METRICS};

use crate::cohort::{BoundCall, Cohort, Ctx};
use crate::consts::{CACHEABLE_FROM, MAX_METRIC_CALLS, MAX_METRIC_IDS, MAX_PINS, MAX_SLICE};
use crate::responses::{
    ColumnDecl, ColumnRegistry, MetricValuesQ, MetricValuesResp, SliceMeta, SliceQ, SliceResp,
    TableRow, WhereQ,
};
use crate::state::InstTrm;
use crate::state::StatesT;
use crate::util::{bad_text, cache_header, get_empty, resolve_dm};

type Reply = (HeaderMap, Response);

// The registry as the clients read it: every metric with its kind per root type, derived from the
// columns each root loaded.
pub(crate) async fn columns_get(states: StatesT) -> Reply {
    let roots: Vec<(&str, Ctx)> = states
        .0
         .0
        .keys()
        .filter_map(|root| Ctx::new(&states, root).map(|ctx| (*root, ctx)))
        .collect();
    let metrics = METRICS
        .iter()
        .map(|decl| ColumnDecl {
            decl,
            kinds: roots
                .iter()
                .filter_map(|(root, ctx)| ctx.kind(decl).map(|k| (*root, k)))
                .collect(),
        })
        .collect();
    (
        cache_header(1440),
        Json(ColumnRegistry { metrics }).into_response(),
    )
}

// The parsed tree of a `where` expression, for a client that shows it as chips.
pub(crate) async fn where_get(Query(q): Query<WhereQ>) -> Reply {
    match parse_where(&q.q) {
        Ok(e) => (cache_header(1440), Json(e).into_response()),
        Err(e) => bad_text(e.to_string()),
    }
}

// One page of a root type's entities in the active ordering, with the meta the page is read
// against: `{ rows, meta }`, never a bare array — a caller that only wants the ranking reads
// `rows` and ignores the rest.
pub(crate) async fn slice_get(
    Path((etype, pstart, pend)): Path<(String, usize, usize)>,
    Query(q): Query<SliceQ>,
    states: StatesT,
) -> Reply {
    let Some(ctx) = Ctx::new(&states, &etype) else {
        return get_empty();
    };
    let sort = match parse_call(q.sort.as_deref().unwrap_or("citations")).map_err(|e| e.to_string())
    {
        Ok(call) => match ctx.bind_call(&call) {
            Ok(b) => b,
            Err(r) => return bad_text(r.0),
        },
        Err(msg) => return bad_text(format!("sort: {msg}")),
    };
    let filter = match q.r#where.as_deref().filter(|s| !s.trim().is_empty()) {
        None => None,
        Some(text) => match parse_where(text) {
            Ok(e) => match ctx.bind_where(&e) {
                Ok(b) => Some(b),
                Err(r) => return bad_text(r.0),
            },
            Err(e) => return bad_text(format!("where: {e}")),
        },
    };
    let cohort = match Cohort::new(ctx, sort, filter) {
        Ok(c) => c,
        Err(r) => return bad_text(r.0),
    };
    // Pinned rows are the named entities in the active ordering, whatever the page bounds.
    let rows: Vec<TableRow> = match q.pin.as_deref() {
        Some(pins) => pins
            .split(',')
            .filter_map(|sem| resolve_dm(&states.0 .0, &etype, sem.trim()))
            .filter_map(|(_, dm)| ctx.state.response_id_from_dm(dm))
            .take(MAX_PINS)
            .map(|rid| cohort.row(cohort.rank_of(rid as u32), rid as u32))
            .collect(),
        None => {
            let n = cohort.len();
            let start = min(pstart, n.saturating_sub(1));
            let end = min(max(start + 1, min(start + MAX_SLICE, pend)), n);
            (start..end)
                .map(|pos| {
                    let rid = cohort.rid_at(pos);
                    cohort.row(Some(cohort.rank(rid)), rid)
                })
                .collect()
        }
    };
    let meta = SliceMeta {
        total: cohort.total,
        screened: cohort.screened.then(|| cohort.len()),
        columns: cohort.column_keys(),
    };
    (
        cache_header(60),
        Json(SliceResp { rows, meta }).into_response(),
    )
}

// Page-local metric values: one call carries the page's dm ids and a list of metric calls, and
// answers each call as a column keyed by its canonical text, aligned with `ids`.
pub(crate) async fn metric_values_get(
    Path(etype): Path<String>,
    Query(q): Query<MetricValuesQ>,
    states: StatesT,
) -> Reply {
    let Some(ctx) = Ctx::new(&states, &etype) else {
        return get_empty();
    };
    let calls = match parse_calls(&q.metrics) {
        Ok(calls) if calls.len() <= MAX_METRIC_CALLS => calls,
        Ok(_) => return bad_text(format!("metrics: at most {MAX_METRIC_CALLS} calls")),
        Err(e) => return bad_text(format!("metrics: {e}")),
    };
    let ids: Vec<usize> = q
        .ids
        .split(',')
        .filter_map(|s| s.trim().parse().ok())
        .filter(|&dm| ctx.state.response_id_from_dm(dm).is_some())
        .take(MAX_METRIC_IDS)
        .collect();
    let mut values: HashMap<Arc<str>, Vec<Option<f64>>> = HashMap::new();
    for call in &calls {
        let bound = match ctx.bind_call(call) {
            Ok(b) => b,
            Err(r) => return bad_text(r.0),
        };
        let col: Vec<Option<f64>> = if bound.decl.cost == Cost::Walk {
            let shares = profile_shares(&ctx, &bound, &ids, &states.0 .2);
            ids.iter().map(|dm| shares.get(dm).copied()).collect()
        } else {
            ids.iter().map(|&dm| ctx.num(&bound, dm)).collect()
        };
        values.insert(bound.key, col);
    }
    (
        cache_header(60),
        Json(MetricValuesResp { ids, values }).into_response(),
    )
}

// One first-level profile per entity, read as the argument's share of the root's links. An entity
// whose profile could not be produced, or whose share the profile cannot settle, is absent.
fn profile_shares(ctx: &Ctx, call: &BoundCall, ids: &[usize], tm: &InstTrm) -> HashMap<usize, f64> {
    let level = call.decl.profile.expect("a walk metric names its profile");
    let leaf = match call.arg {
        rankless_trees::metrics::Arg::Country(c) => c as u32,
        _ => return HashMap::new(),
    };
    let cacheable = ids
        .iter()
        .map(|&dm| (dm, ctx.cols.citations[dm] >= CACHEABLE_FROM));
    tm.first_levels(ctx.etype, level, None, cacheable)
        .into_iter()
        .filter_map(|(eid, fl)| fl.share(leaf).map(|s| (eid, s)))
        .collect()
}

#[cfg(test)]
mod tests {
    use axum::http::Uri;

    use super::*;

    #[test]
    fn the_slice_query_carries_one_where_string() {
        let uri: Uri =
            "/x?sort=field_score(oncology)&where=country%3Dhun+and+papers%3E%3D100&pin=a,b"
                .parse()
                .unwrap();
        let q: SliceQ = Query::try_from_uri(&uri).unwrap().0;
        assert_eq!(q.sort.as_deref(), Some("field_score(oncology)"));
        assert_eq!(q.r#where.as_deref(), Some("country=hun and papers>=100"));
        assert_eq!(q.pin.as_deref(), Some("a,b"));
    }
}
