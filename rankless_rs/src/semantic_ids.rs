use std::collections::BinaryHeap;

use dmove::{Entity, NamespacedEntity, VarAttBuilder};
use hashbrown::HashSet;
use muwo_search::StackWordSet;

use crate::{
    common::{init_empty_slice, MainEntity},
    SemanticIdMarker, Stowage,
};

/// The slugs an entity may take, in order: `preferred`, its display `name`, then `fallbacks`.
/// A display-name slug belongs to the entities bearing that name: no other entity takes it as a
/// preferred or fallback slug. Once every candidate is taken, a suffix extends the name.
pub struct SemCandidates {
    pub preferred: Vec<String>,
    pub name: String,
    pub fallbacks: Vec<String>,
}

impl SemCandidates {
    pub fn name_only(name: String) -> Self {
        Self {
            preferred: Vec::new(),
            name,
            fallbacks: Vec::new(),
        }
    }

    fn stem(&self) -> Option<&str> {
        std::iter::once(&self.name)
            .chain(self.fallbacks.iter().rev())
            .chain(self.preferred.iter().rev())
            .find(|s| !s.is_empty())
            .map(String::as_str)
    }
}

impl Stowage {
    pub fn write_semantic_id<E>(
        &self,
        wcounts: &[usize],
        candidates: &[Option<SemCandidates>],
        pinned: &[(usize, String)],
    ) where
        E: MainEntity + NamespacedEntity,
    {
        let mut ids = init_empty_slice::<E, String>();
        assign_sem_ids(&mut ids, wcounts, candidates, pinned);
        self.decsem::<E, _>(ids.into_vec().into_iter())
    }

    pub fn decsem<E, I>(&self, it: I)
    where
        E: Entity,
        I: Iterator<Item = String>,
    {
        self.declare_iter::<VarAttBuilder, _, _, E, SemanticIdMarker>(
            it,
            &format!("{}-semantic-ids", E::NAME),
        );
    }
}

/// `wcounts` drives priority: high-work-count entities claim their preferred semantic ID first.
/// `pinned` slugs are assigned before any candidate; an entity without candidates gets no slug.
fn assign_sem_ids(
    ids: &mut [String],
    wcounts: &[usize],
    candidates: &[Option<SemCandidates>],
    pinned: &[(usize, String)],
) {
    let mut taken = HashSet::new();
    for (eid, sid) in pinned {
        if candidates[*eid].is_some() {
            assert!(taken.insert(sid.clone()), "{sid} pinned twice");
            ids[*eid] = sid.clone();
        }
    }
    let names: HashSet<&str> = candidates
        .iter()
        .flatten()
        .map(|c| c.name.as_str())
        .collect();
    let mut eid_heap: BinaryHeap<(usize, usize)> = candidates
        .iter()
        .enumerate()
        .filter(|(eid, c)| c.is_some() && ids[*eid].is_empty())
        .map(|(eid, _)| (wcounts[eid], eid))
        .collect();

    let suffs = get_suffs();
    while let Some((_, eid)) = eid_heap.pop() {
        let c = candidates[eid].as_ref().unwrap();
        let unclaimed = |s: &&String| !s.is_empty() && !names.contains(s.as_str());
        let named = c
            .preferred
            .iter()
            .filter(unclaimed)
            .chain(Some(&c.name).filter(|s| !s.is_empty()))
            .chain(c.fallbacks.iter().filter(unclaimed))
            .cloned();
        let suffixed = c
            .stem()
            .into_iter()
            .flat_map(|stem| suffs.iter().map(move |suff| format!("{stem}{suff}")));
        if let Some(sid) = named.chain(suffixed).find(|s| !taken.contains(s)) {
            taken.insert(sid.clone());
            ids[eid] = sid;
        }
    }
}

pub fn semantify(s: &str) -> String {
    StackWordSet::new(s).to_words().join("-")
}

fn get_suffs() -> Vec<String> {
    "23456789abcdefghijklmno"
        .chars()
        .map(|e| format!("-{e}"))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cands(preferred: &[&str], name: &str, fallbacks: &[&str]) -> Option<SemCandidates> {
        let own = |v: &[&str]| v.iter().map(|s| s.to_string()).collect();
        Some(SemCandidates {
            preferred: own(preferred),
            name: name.to_string(),
            fallbacks: own(fallbacks),
        })
    }

    fn assign(
        wcounts: &[usize],
        candidates: &[Option<SemCandidates>],
        pinned: &[(usize, String)],
    ) -> Vec<String> {
        let mut ids = vec![String::new(); candidates.len()];
        assign_sem_ids(&mut ids, wcounts, candidates, pinned);
        ids
    }

    #[test]
    fn name_outranks_fallbacks_and_preferred_outranks_name() {
        let ids = assign(
            &[10, 5],
            &[
                cands(&[], "science", &["science-online"]),
                cands(&["mit"], "massachusetts-institute-of-technology", &[]),
            ],
            &[],
        );
        assert_eq!(ids, ["science", "mit"]);
    }

    #[test]
    fn a_display_name_slug_is_never_another_entitys_alias() {
        let ids = assign(
            &[10, 5],
            &[
                cands(&["genomics"], "bmc-genomics", &[]),
                cands(&[], "genomics", &[]),
            ],
            &[],
        );
        assert_eq!(ids, ["bmc-genomics", "genomics"]);
    }

    #[test]
    fn a_shared_name_falls_back_then_suffixes_the_name() {
        let ids = assign(
            &[10, 5, 1],
            &[
                cands(&[], "ministry-of-health", &[]),
                cands(&[], "ministry-of-health", &["ministry-health-saudi-arabia"]),
                cands(&[], "ministry-of-health", &["ministry-health-saudi-arabia"]),
            ],
            &[],
        );
        assert_eq!(
            ids,
            [
                "ministry-of-health",
                "ministry-health-saudi-arabia",
                "ministry-of-health-2"
            ]
        );
    }

    #[test]
    fn a_pin_wins_over_every_candidate_and_needs_a_page() {
        let ids = assign(
            &[10, 5, 1],
            &[
                cands(&[], "plos-one", &[]),
                cands(&["plos"], "plos-one", &[]),
                None,
            ],
            &[(1, "plos-one".to_string()), (2, "orphan".to_string())],
        );
        assert_eq!(ids, ["plos-one-2", "plos-one", ""]);
    }
}
