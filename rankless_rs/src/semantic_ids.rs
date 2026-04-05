use std::collections::BinaryHeap;

use dmove::{Entity, NamespacedEntity, VarAttBuilder};
use hashbrown::HashSet;
use muwo_search::StackWordSet;

use crate::{
    common::{init_empty_slice, MainEntity},
    SemanticIdMarker, Stowage,
};

impl Stowage {
    /// `wcounts` drives priority: high-work-count entities claim their preferred semantic ID first.
    pub fn write_semantic_id<E>(&self, wcounts: &[usize], names: &[Vec<String>])
    where
        E: MainEntity + NamespacedEntity,
    {
        let mut eid_heap = BinaryHeap::new();
        let mut sem_set = HashSet::new();
        for (eid, name_vec) in names.iter().enumerate() {
            if !name_vec.is_empty() {
                eid_heap.push((wcounts[eid], eid));
            }
        }

        let suffs = get_suffs();
        let mut ids = init_empty_slice::<E, String>();
        while let Some((_, eid)) = eid_heap.pop() {
            let id_opts_vec = &names[eid];
            if id_opts_vec.is_empty() {
                continue;
            }
            let for_suff = id_opts_vec.last().unwrap().clone();
            for sid in id_opts_vec
                .clone()
                .into_iter()
                .chain(suffs.iter().map(|e| for_suff.clone() + e))
            {
                if ifnotin(&mut sem_set, sid, |e| ids[eid] = e) {
                    break;
                }
            }
        }
        self.decsem::<E, _>(ids.iter().map(|e| e.to_owned()))
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

pub fn semantify(s: &str) -> String {
    StackWordSet::new(s).to_words().join("-")
}

fn ifnotin<F>(set: &mut HashSet<String>, e: String, mut f: F) -> bool
where
    F: FnMut(String),
{
    if !set.contains(&e) {
        set.insert(e.clone());
        f(e);
        return true;
    }
    false
}

fn get_suffs() -> Vec<String> {
    "23456789abcdefghijklmno"
        .chars()
        .map(|e| format!("-{e}").to_string())
        .collect()
}
