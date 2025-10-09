use dmove::ET;
use hashbrown::{HashMap, HashSet};
use rankless_rs::gen::a1_entity_mapping::Authors;
use serde::Serialize;

use crate::{interfacing::Getters, io::WT};

#[derive(Serialize, Debug, Clone)]
pub enum RefTree {
    Node(Box<HashMap<WT, RefTree>>),
    Leaf,
}

fn find_paths<F>(
    gets: &Getters,
    results: &mut Vec<Vec<WT>>,
    wid: WT,
    depth_to_go: usize,
    so_far: Vec<WT>,
    filter_fun: &F,
) where
    F: Fn(WT) -> bool,
{
    for refed_wid in gets.wor_refs(wid) {
        if *refed_wid == wid {
            continue;
        }
        if filter_fun(*refed_wid) {
            let mut new_line = so_far.clone();
            new_line.push(*refed_wid);
            results.push(new_line);
        }
        if depth_to_go > 0 {
            let mut new_sofar = so_far.clone();
            new_sofar.push(*refed_wid);
            find_paths(
                gets,
                results,
                *refed_wid,
                depth_to_go - 1,
                new_sofar,
                filter_fun,
            );
        }
    }
}

pub fn author_to_work_paths<F>(
    gets: &Getters,
    widu: usize,
    aidu: usize,
    depth: usize,
    mut wid_fun: F,
) -> (RefTree, Vec<WT>)
where
    F: FnMut(WT),
{
    let aid = aidu as ET<Authors>;
    let aworks: HashSet<WT> = HashSet::from_iter(gets.aworks(aid).iter().map(|e| *e));
    let mut used_aworks: HashSet<WT> = HashSet::new();
    let ffun = |rwid: WT| aworks.contains(&rwid);
    let mut results = Vec::new();
    let wid = widu as WT;
    find_paths(gets, &mut results, wid, depth, Vec::new(), &ffun);
    let mut ref_tree_map = HashMap::new();
    let mut inner_wid_fun = |wid: WT| {
        wid_fun(wid);
        if ffun(wid) {
            used_aworks.insert(wid);
        }
    };
    for path in &results {
        insert_path(&mut ref_tree_map, path, &mut inner_wid_fun);
    }
    (
        RefTree::Node(Box::from(ref_tree_map)),
        used_aworks.into_iter().collect(),
    )
}

fn insert_path<F>(map: &mut HashMap<WT, RefTree>, path: &[WT], f: &mut F)
where
    F: FnMut(WT),
{
    if path.is_empty() {
        return;
    }
    let first = path[0];
    f(first);
    if path.len() == 1 {
        map.insert(first, RefTree::Leaf);
    } else {
        let entry = map
            .entry(first)
            .or_insert_with(|| RefTree::Node(Box::new(HashMap::new())));
        match entry {
            RefTree::Leaf => {
                *entry = RefTree::Node(Box::new(HashMap::new()));
                if let RefTree::Node(submap) = entry {
                    insert_path(submap, &path[1..], f);
                }
            }
            RefTree::Node(submap) => {
                insert_path(submap, &path[1..], f);
            }
        }
    }
}
