use std::cmp::{max, min};

use axum::{
    extract::{Path, Query},
    http::{HeaderMap, HeaderValue},
    response::{IntoResponse, Response},
    Json,
};
use hashbrown::HashMap;

use dmove::Entity;
use rankless_rs::{
    gen::a1_entity_mapping::Subfields,
    metrics::{self, size_adjusted_score, Level, MetricDecl, MetricKind, METRICS},
};
use rankless_trees::interfacing::RootColumns;

use crate::consts::{CACHEABLE_FROM, COHORT_TOTAL_HEADER, MAX_METRIC_IDS, MAX_SLICE};
use crate::responses::{MetricValuesQ, MetricValuesResp, SliceQ, TableRow};
use crate::state::{order_by, InstTrm, NameState, StatesT};
use crate::util::{bad_request, cache_header, get_empty, resolve_dm};

// Per-entity metric reads of one root type: its search state plus the columns carrying the
// per-subfield citation profile and, for authors, the h-index and career centroid.
#[derive(Clone, Copy)]
struct RootMetrics<'a> {
    state: &'a NameState,
    cols: Option<&'a RootColumns>,
}

struct Cohort<'a> {
    root: RootMetrics<'a>,
    field: Option<usize>,
    sort: &'static str,
    rids: Rids<'a>,
}

// Response ids in one cohort ordering: the citation order is the response array itself, the other
// global orderings are precomputed at startup, a field-narrowed cohort is scanned per request.
enum Rids<'a> {
    Identity(usize),
    Fixed(&'a [u32]),
    Scanned(Box<[u32]>),
}

impl<'a> RootMetrics<'a> {
    fn new(states: &'a StatesT, etype: &str) -> Option<Self> {
        Some(Self {
            state: states.0 .0.get(etype)?,
            cols: states.2.state.gets.columns_for(etype),
        })
    }

    fn global(&self, decl: &MetricDecl, rid: usize) -> Option<f64> {
        let sr = &self.state.responses[rid];
        match decl.id {
            metrics::CITATIONS => Some(sr.citations as f64),
            metrics::PAPERS => Some(sr.papers as f64),
            metrics::IMPACT_SCORE => Some(self.state.impact_scores[rid] as f64),
            metrics::H_INDEX => self.h_index(rid).map(f64::from),
            metrics::YEAR_CENTROID => self.year_centroid(rid).map(f64::from),
            _ => None,
        }
    }

    fn h_index(&self, rid: usize) -> Option<u32> {
        let dm = self.state.responses[rid].dm_id;
        self.cols?.h_indices.as_ref().map(|h| h[dm])
    }

    fn year_centroid(&self, rid: usize) -> Option<f32> {
        let dm = self.state.responses[rid].dm_id;
        self.cols?.year_centroids.as_ref().map(|y| y[dm])
    }

    // Field metrics are declared only for the root types carrying the subfield profiles.
    fn field_citations(&self, rid: usize, sf: usize) -> u32 {
        let sfs = self
            .cols
            .and_then(|c| c.subfields.as_ref())
            .expect("field metric on a root type without a subfield profile");
        sfs.citing.elem(self.state.responses[rid].dm_id, sf)
    }

    fn field_score(&self, rid: usize, sf: usize) -> f32 {
        let sr = &self.state.responses[rid];
        size_adjusted_score(
            self.field_citations(rid, sf),
            sr.papers,
            self.state.mean_papers,
        )
    }
}

impl Rids<'_> {
    fn len(&self) -> usize {
        match self {
            Self::Identity(n) => *n,
            Self::Fixed(s) => s.len(),
            Self::Scanned(v) => v.len(),
        }
    }

    fn at(&self, pos: usize) -> u32 {
        match self {
            Self::Identity(_) => pos as u32,
            Self::Fixed(s) => s[pos],
            Self::Scanned(v) => v[pos],
        }
    }
}

impl<'a> Cohort<'a> {
    fn new(root: RootMetrics<'a>, field: Option<usize>, sort: &'static str) -> Self {
        let n = root.state.responses.len();
        let mut cohort = Self {
            root,
            field,
            sort,
            rids: Rids::Identity(n),
        };
        cohort.rids = match field {
            Some(sf) => Rids::Scanned(order_by(
                (0..n as u32).filter(|&rid| root.field_citations(rid as usize, sf) > 0),
                |rid| cohort.value(rid),
            )),
            None => {
                let o = &root.state.orderings;
                match sort {
                    metrics::PAPERS => Rids::Fixed(&o.papers),
                    metrics::IMPACT_SCORE => Rids::Fixed(&o.impact_score),
                    metrics::H_INDEX => Rids::Fixed(o.h_index.as_deref().unwrap_or(&[])),
                    metrics::YEAR_CENTROID => {
                        Rids::Fixed(o.year_centroid.as_deref().unwrap_or(&[]))
                    }
                    _ => Rids::Identity(n),
                }
            }
        };
        cohort
    }

    fn len(&self) -> usize {
        self.rids.len()
    }

    // The sort metric's value for one response id: the key both the ordering and the rank use.
    fn value(&self, rid: u32) -> f64 {
        let rid = rid as usize;
        match (self.sort, self.field) {
            (metrics::FIELD_CITATIONS, Some(sf)) => self.root.field_citations(rid, sf) as f64,
            (metrics::FIELD_SCORE, Some(sf)) => self.root.field_score(rid, sf) as f64,
            _ => self
                .root
                .global(metrics::metric(self.sort).unwrap(), rid)
                .unwrap_or(0.0),
        }
    }

    // 1-based rank: entities strictly above in the sort value, plus one, so ties share a rank.
    fn rank(&self, rid: u32) -> u32 {
        let v = self.value(rid);
        let (mut lo, mut hi) = (0usize, self.len());
        while lo < hi {
            let mid = (lo + hi) / 2;
            if self.value(self.rids.at(mid)) > v {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        lo as u32 + 1
    }

    // None for an entity outside a field-narrowed cohort.
    fn rank_of(&self, rid: u32) -> Option<u32> {
        match self.field {
            Some(sf) if self.root.field_citations(rid as usize, sf) == 0 => None,
            _ => Some(self.rank(rid)),
        }
    }

    fn row(&self, rank: u32, rid: u32) -> TableRow {
        let rid = rid as usize;
        TableRow {
            sr: self.root.state.responses[rid].clone(),
            rank,
            impact_score: self.root.state.impact_scores[rid],
            h_index: self.root.h_index(rid),
            year_centroid: self.root.year_centroid(rid),
            field_citations: self.field.map(|sf| self.root.field_citations(rid, sf)),
            field_score: self.field.map(|sf| self.root.field_score(rid, sf)),
        }
    }
}

// The registry with every profile metric limited to the roots whose trees yield its level.
pub(crate) async fn metrics_get(states: StatesT) -> (HeaderMap, Response) {
    let specs = &states.0 .2.specs;
    let metrics: Vec<MetricDecl> = METRICS
        .iter()
        .map(|m| m.resolved(|root, level| specs.has_level(root, level)))
        .collect();
    (
        cache_header(1440),
        Json(serde_json::json!({ "metrics": metrics })).into_response(),
    )
}

pub(crate) async fn slice_get(
    Path((etype, pstart, pend)): Path<(String, usize, usize)>,
    Query(q): Query<SliceQ>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let Some(root) = RootMetrics::new(&states, &etype) else {
        return get_empty();
    };
    let Some(sort) = metrics::metric(q.sort.as_deref().unwrap_or(metrics::CITATIONS)) else {
        return bad_request("unknown sort metric");
    };
    if sort.kind_for(&etype) != Some(MetricKind::Global) {
        return bad_request("metric does not order this cohort");
    }
    let field = match q.subfield.as_deref() {
        None => None,
        Some(sem) => {
            if metrics::metric_kind(metrics::FIELD_SCORE, &etype) != Some(MetricKind::Global) {
                return bad_request("field filter does not narrow this cohort");
            }
            let Some((_, sf)) = resolve_dm(&states.0 .0, Subfields::NAME, sem) else {
                return get_empty();
            };
            Some(sf)
        }
    };
    if sort.params.contains(&metrics::PARAM_SUBFIELD) && field.is_none() {
        return bad_request("sort needs subfield=");
    }
    let cohort = Cohort::new(root, field, sort.id);
    let rows: Vec<TableRow> = match q.q.as_deref().filter(|s| !s.trim().is_empty()) {
        Some(name_q) => {
            let mut hits: Vec<(u32, u32)> = root
                .state
                .engine
                .query(name_q)
                .into_iter()
                .map(|e| e as u32)
                .filter(|&rid| (rid as usize) < root.state.responses.len())
                .filter_map(|rid| cohort.rank_of(rid).map(|rank| (rank, rid)))
                .collect();
            hits.sort_unstable();
            hits.into_iter()
                .map(|(rank, rid)| cohort.row(rank, rid))
                .collect()
        }
        None => {
            let n = cohort.len();
            let start = min(pstart, n.saturating_sub(1));
            let end = min(max(start + 1, min(start + MAX_SLICE, pend)), n);
            (start..end)
                .map(|pos| {
                    let rid = cohort.rids.at(pos);
                    cohort.row(cohort.rank(rid), rid)
                })
                .collect()
        }
    };
    let mut headers = cache_header(60);
    headers.insert(COHORT_TOTAL_HEADER, HeaderValue::from(cohort.len()));
    (headers, Json(rows).into_response())
}

// Page-local metric values: one call carries the page's dm ids and every parameter, and answers
// each requested metric as a column aligned with `ids`.
pub(crate) async fn metric_values_get(
    Path(etype): Path<String>,
    Query(q): Query<MetricValuesQ>,
    states: StatesT,
) -> (HeaderMap, Response) {
    let Some(root) = RootMetrics::new(&states, &etype) else {
        return get_empty();
    };
    let state = root.state;
    // (dm id, response id) of every requested entity the root type has a response for.
    let ids: Vec<(usize, usize)> = q
        .ids
        .split(',')
        .filter_map(|s| s.trim().parse().ok())
        .filter_map(|dm| state.response_id_from_dm(dm).map(|rid| (dm, rid)))
        .take(MAX_METRIC_IDS)
        .collect();
    let mut values: HashMap<&'static str, Vec<Option<f64>>> = HashMap::new();
    for mid in q
        .metrics
        .split(',')
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        let Some(decl) = metrics::metric(mid) else {
            return bad_request("unknown metric");
        };
        let specs = &states.0 .2.specs;
        if decl
            .kind_if(&etype, |root, level| specs.has_level(root, level))
            .is_none()
        {
            return bad_request("metric is not defined for this root type");
        }
        let col: Vec<Option<f64>> = match decl.id {
            metrics::WINDOW_PAPERS | metrics::WINDOW_CITATIONS => ids
                .iter()
                .map(|&(_, rid)| {
                    let w = state.exts[rid].window(q.year_from, q.year_to);
                    let v = if decl.id == metrics::WINDOW_PAPERS {
                        w.papers
                    } else {
                        w.citations
                    };
                    Some(v as f64)
                })
                .collect(),
            metrics::FIELD_CITATIONS | metrics::FIELD_SCORE => {
                let Some(sem) = q.subfield.as_deref() else {
                    return bad_request("metric needs subfield=");
                };
                let Some((_, sf)) = resolve_dm(&states.0 .0, Subfields::NAME, sem) else {
                    return get_empty();
                };
                ids.iter()
                    .map(|&(_, rid)| {
                        Some(if decl.id == metrics::FIELD_CITATIONS {
                            root.field_citations(rid, sf) as f64
                        } else {
                            root.field_score(rid, sf) as f64
                        })
                    })
                    .collect()
            }
            metrics::CITING_COUNTRY_SHARE => {
                let Some(sem) = q.country.as_deref() else {
                    return bad_request("metric needs country=");
                };
                let level = decl.profile.expect("a share metric names its profile");
                let Some((_, leaf)) = resolve_dm(&states.0 .0, level.entity, sem) else {
                    return get_empty();
                };
                let shares = profile_shares(&etype, level, leaf, &ids, state, &states.0 .2);
                ids.iter().map(|(dm, _)| shares.get(dm).copied()).collect()
            }
            _ => ids.iter().map(|&(_, rid)| root.global(decl, rid)).collect(),
        };
        values.insert(decl.id, col);
    }
    let ids = ids.into_iter().map(|(dm, _)| dm).collect();
    (
        cache_header(60),
        Json(MetricValuesResp { ids, values }).into_response(),
    )
}

// One first-level profile per entity, read as the chosen leaf's share of the root's links. An
// entity whose profile could not be produced, or whose share the profile cannot settle, is absent.
fn profile_shares(
    etype: &str,
    level: Level,
    leaf: usize,
    ids: &[(usize, usize)],
    state: &NameState,
    tm: &InstTrm,
) -> HashMap<usize, f64> {
    let cacheable = ids
        .iter()
        .map(|&(dm, rid)| (dm, state.responses[rid].citations >= CACHEABLE_FROM));
    tm.first_levels(etype, level, None, cacheable)
        .into_iter()
        .filter_map(|(eid, fl)| fl.share(leaf as u32).map(|s| (eid, s)))
        .collect()
}
