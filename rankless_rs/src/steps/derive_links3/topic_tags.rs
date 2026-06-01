use dmove::{
    Entity, MarkedAttribute, NamespacedEntity, UnsignedNumber, VarAttBuilder,
    VariableSizeAttribute, ET, MAA,
};
use hashbrown::HashMap;

use crate::{
    common::{MainWorkMarker, TopicDominatorMarker},
    gen::a1_entity_mapping::{Topics, Works},
    steps::a1_entity_mapping::{YearInterface, Years},
    ReadIter, Stowage,
};

use super::hit_papers::CCUI;

// Topic-creator: a topic is creator-eligible only if its earliest paper is published in this year or
// later (guards against the START_YEAR floor manufacturing fake "originators" for old topics).
pub(super) const CREATOR_CUTOFF_YEAR: u16 = 2000;
// Impact floor for a creator paper. Deliberately lower than the regular hit bar so genuine topic
// originators are admitted, but kept above the absolute hit floor (MIN_NEEDED = 10).
pub(super) const MIN_CREATOR_CITATIONS: usize = 50;

// Dominator: a topic is too small for a citation share to be meaningful below this many papers.
const _MIN_DOM_TOPIC_PAPERS: u32 = 50;
// Per-entity-type cited-share thresholds. A country naturally captures a far larger share of a
// topic's citations than a single author, so the bar scales with entity granularity. Tuning knobs.
pub(super) const _DOM_PCT_AUTHORS: f64 = 0.02;
pub(super) const _DOM_PCT_INSTITUTIONS: f64 = 0.10;
pub(super) const _DOM_PCT_SOURCES: f64 = 0.20;
pub(super) const _DOM_PCT_COUNTRIES: f64 = 0.35;

// (topic, captured citation share in basis points). Stored per dominating entity.
type _DomTag = (ET<Topics>, u16);

// For each topic, the earliest-published paper assigned that topic (tiebroken by citations) that
// clears the impact floor, restricted to topics first seen at/after the cutoff year. Returns the
// work -> created-topic map plus the per-topic paper counts (reused as the dominator size guard).
pub(super) fn compute_creators(
    w_topics: &[Box<[ET<Topics>]>],
    w_years: &[ET<Years>],
    cc: &[CCUI],
) -> (HashMap<ET<Works>, ET<Topics>>, Box<[u32]>) {
    let cutoff = YearInterface::parse(CREATOR_CUTOFF_YEAR);
    let mut rec: Vec<Option<(ET<Years>, CCUI, ET<Works>)>> = vec![None; Topics::N + 1];
    let mut papers_in_t = vec![0u32; Topics::N + 1];
    for (wid, topics) in w_topics.iter().enumerate() {
        let year = w_years[wid];
        let wcc = cc[wid];
        for t in topics.iter() {
            let ti = t.to_usize();
            papers_in_t[ti] += 1;
            let better = match rec[ti] {
                None => true,
                Some((y, c, _)) => year < y || (year == y && wcc > c),
            };
            if better {
                rec[ti] = Some((year, wcc, ET::<Works>::from_usize(wid)));
            }
        }
    }
    let mut creates = HashMap::new();
    for (ti, r) in rec.into_iter().enumerate() {
        if ti == 0 {
            continue;
        }
        if let Some((y, c, wid)) = r {
            if y >= cutoff && c.to_usize() >= MIN_CREATOR_CITATIONS {
                creates.entry(wid).or_insert(ET::<Topics>::from_usize(ti));
            }
        }
    }
    (creates, papers_in_t.into_boxed_slice())
}

// Per topic: every incoming citation edge whose citing paper carries that topic, edge-weighted. This
// is the dominator denominator (the numerator below restricts the same count to one entity's works).
fn _compute_denominator(
    wciting: &[Box<[ET<Works>]>],
    w_topics: &[Box<[ET<Topics>]>],
) -> Box<[u64]> {
    let mut denom = vec![0u64; Topics::N + 1];
    for citers in wciting.iter() {
        for c in citers.iter() {
            for t in w_topics[c.to_usize()].iter() {
                denom[t.to_usize()] += 1;
            }
        }
    }
    denom.into_boxed_slice()
}

// For entity type E, tag the topics where E captures at least `threshold` of the topic's citation
// flow. One pass over each entity's works, counting the topics of the citing papers, then comparing
// against the global denominator. Writes a per-entity variable-length list of dominated topics.
fn _emit_dominators<E>(
    stowage: &Stowage,
    wciting: &[Box<[ET<Works>]>],
    w_topics: &[Box<[ET<Topics>]>],
    denom: &[u64],
    papers_in_t: &[u32],
    threshold: f64,
) where
    E: Entity + MarkedAttribute<MainWorkMarker>,
    MAA<E, MainWorkMarker>: Entity<T = Box<[ET<Works>]>> + NamespacedEntity + VariableSizeAttribute,
{
    let mut counts: HashMap<usize, u32> = HashMap::new();
    let mut out: Vec<Box<[_DomTag]>> = Vec::new();
    for works in stowage.get_entity_interface::<MAA<E, MainWorkMarker>, ReadIter>() {
        counts.clear();
        for w in works.iter() {
            for c in wciting[w.to_usize()].iter() {
                for t in w_topics[c.to_usize()].iter() {
                    *counts.entry(t.to_usize()).or_insert(0) += 1;
                }
            }
        }
        let mut tags: Vec<_DomTag> = counts
            .iter()
            .filter_map(|(&ti, &cnt)| {
                if ti == 0 || papers_in_t[ti] < _MIN_DOM_TOPIC_PAPERS || denom[ti] == 0 {
                    return None;
                }
                // Clamp: a work listed under one entity more than once (e.g. multi-location
                // sources) can nudge the count past the denominator; a share can't exceed 1.
                let share = (cnt as f64 / denom[ti] as f64).min(1.0);
                (share >= threshold).then(|| {
                    (
                        ET::<Topics>::from_usize(ti),
                        (share * 10_000.0).round() as u16,
                    )
                })
            })
            .collect();
        tags.sort_unstable_by(|a, b| b.1.cmp(&a.1));
        out.push(tags.into_boxed_slice());
    }
    stowage.declare_iter::<VarAttBuilder, _, _, E, TopicDominatorMarker>(
        out.into_iter(),
        &format!("{}-dominated-topics", E::NAME),
    );
}
