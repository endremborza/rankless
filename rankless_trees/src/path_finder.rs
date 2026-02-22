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

impl RefTree {
    pub fn has_paths(&self) -> bool {
        match self {
            RefTree::Node(map) => !map.is_empty(),
            RefTree::Leaf => true,
        }
    }
}

pub trait RefGraph {
    fn get_refs(&self, wid: WT) -> &[WT];
    fn get_aworks(&self, aid: ET<Authors>) -> &[WT];
}

impl RefGraph for Getters {
    fn get_refs(&self, wid: WT) -> &[WT] {
        self.wor_refs(wid)
    }

    fn get_aworks(&self, aid: ET<Authors>) -> &[WT] {
        self.aworks(aid)
    }
}

fn find_paths<G, F>(
    graph: &G,
    results: &mut Vec<Vec<WT>>,
    wid: WT,
    depth_to_go: usize,
    so_far: Vec<WT>,
    filter_fun: &F,
) where
    G: RefGraph,
    F: Fn(WT) -> bool,
{
    for &refed_wid in graph.get_refs(wid) {
        if refed_wid == wid {
            continue;
        }
        if filter_fun(refed_wid) {
            let mut new_line = so_far.clone();
            new_line.push(refed_wid);
            results.push(new_line);
        }
        if depth_to_go > 0 {
            let mut new_sofar = so_far.clone();
            new_sofar.push(refed_wid);
            find_paths(graph, results, refed_wid, depth_to_go - 1, new_sofar, filter_fun);
        }
    }
}

pub fn author_to_work_paths<G, F>(
    graph: &G,
    widu: usize,
    aidu: usize,
    depth: usize,
    wid_fun: &mut F,
) -> (RefTree, Vec<WT>)
where
    G: RefGraph,
    F: FnMut(WT),
{
    let aid = aidu as ET<Authors>;
    let wid = widu as WT;
    let aworks: HashSet<WT> = graph.get_aworks(aid).iter().copied().collect();
    let mut used_aworks: HashSet<WT> = HashSet::new();
    let res = extend_used_aworks_get_results(graph, wid, depth, wid_fun, &aworks, &mut used_aworks);
    (res, used_aworks.into_iter().collect())
}

pub fn extend_used_aworks_get_results<G, F>(
    graph: &G,
    wid: WT,
    depth: usize,
    wid_fun: &mut F,
    aworks: &HashSet<WT>,
    used_aworks: &mut HashSet<WT>,
) -> RefTree
where
    G: RefGraph,
    F: FnMut(WT),
{
    let ffun = |rwid: WT| aworks.contains(&rwid);
    let mut results = Vec::new();
    find_paths(graph, &mut results, wid, depth, Vec::new(), &ffun);
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
    RefTree::Node(Box::from(ref_tree_map))
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_utils::TestGraph;

    fn as_node(tree: &RefTree) -> &HashMap<WT, RefTree> {
        match tree {
            RefTree::Node(map) => map,
            RefTree::Leaf => panic!("expected Node, got Leaf"),
        }
    }

    fn sorted_keys(map: &HashMap<WT, RefTree>) -> Vec<WT> {
        let mut keys: Vec<WT> = map.keys().copied().collect();
        keys.sort();
        keys
    }

    fn make_test_graph() -> TestGraph {
        TestGraph::new()
            .with_refs(0, vec![1, 2, 3])
            .with_refs(1, vec![4, 5])
            .with_refs(2, vec![3, 6])
            .with_refs(3, vec![])
            .with_refs(4, vec![])
            .with_refs(5, vec![])
            .with_refs(6, vec![])
    }

    fn run_find_paths(graph: &impl RefGraph, wid: WT, depth: usize, filter: &HashSet<WT>) -> Vec<Vec<WT>> {
        let mut results = Vec::new();
        find_paths(graph, &mut results, wid, depth, Vec::new(), &|w| filter.contains(&w));
        results
    }

    // ---- insert_path ----

    #[test]
    fn insert_path_empty_is_noop() {
        let mut map = HashMap::new();
        let mut called: Vec<WT> = vec![];
        insert_path(&mut map, &[], &mut |w| called.push(w));
        assert!(map.is_empty());
        assert!(called.is_empty());
    }

    #[test]
    fn insert_path_single_becomes_leaf() {
        let mut map = HashMap::new();
        let mut called: Vec<WT> = vec![];
        insert_path(&mut map, &[5], &mut |w| called.push(w));
        assert!(matches!(map.get(&5), Some(RefTree::Leaf)));
        assert_eq!(called, [5]);
    }

    #[test]
    fn insert_path_two_elements_creates_nested_node() {
        let mut map = HashMap::new();
        let mut called: Vec<WT> = vec![];
        insert_path(&mut map, &[5, 3], &mut |w| called.push(w));
        assert_eq!(called, [5, 3]);
        let submap = as_node(map.get(&5).unwrap());
        assert!(matches!(submap.get(&3), Some(RefTree::Leaf)));
        assert_eq!(submap.len(), 1);
    }

    #[test]
    fn insert_path_leaf_promoted_when_longer_path_added() {
        let mut map = HashMap::new();
        let mut noop = |_: WT| {};
        insert_path(&mut map, &[5], &mut noop);
        assert!(matches!(map.get(&5), Some(RefTree::Leaf)));
        insert_path(&mut map, &[5, 3], &mut noop);
        let submap = as_node(map.get(&5).unwrap());
        assert!(matches!(submap.get(&3), Some(RefTree::Leaf)));
    }

    #[test]
    fn insert_path_shared_prefix_merges() {
        let mut map = HashMap::new();
        let mut noop = |_: WT| {};
        insert_path(&mut map, &[5, 3], &mut noop);
        insert_path(&mut map, &[5, 7], &mut noop);
        let submap = as_node(map.get(&5).unwrap());
        assert_eq!(sorted_keys(submap), [3, 7]);
    }

    // ---- find_paths ----

    #[test]
    fn find_paths_empty_graph_yields_nothing() {
        let graph = TestGraph::new();
        let results = run_find_paths(&graph, 0, 2, &[3].into_iter().collect());
        assert!(results.is_empty());
    }

    #[test]
    fn find_paths_depth_zero_only_direct_matches() {
        let graph = make_test_graph();
        let filter: HashSet<WT> = [3, 5].into_iter().collect();
        let results = run_find_paths(&graph, 0, 0, &filter);
        // Only direct refs of 0 that match: 3 (1 and 2 don't match)
        assert_eq!(results, [vec![3]]);
    }

    #[test]
    fn find_paths_depth_one_includes_two_hop_paths() {
        let graph = make_test_graph();
        let filter: HashSet<WT> = [3, 5].into_iter().collect();
        let mut results = run_find_paths(&graph, 0, 1, &filter);
        results.sort();
        // Direct: [3]; via 1: [1,5]; via 2: [2,3]
        assert_eq!(results, [vec![1, 5], vec![2, 3], vec![3]]);
    }

    #[test]
    fn find_paths_self_loop_is_skipped() {
        let graph = TestGraph::new().with_refs(0, vec![0, 1]);
        let filter: HashSet<WT> = [0, 1].into_iter().collect();
        let results = run_find_paths(&graph, 0, 0, &filter);
        // 0 refs itself (skipped) and 1 (matches filter)
        assert_eq!(results, [vec![1]]);
    }

    #[test]
    fn find_paths_no_filter_match_yields_nothing() {
        let graph = make_test_graph();
        let results = run_find_paths(&graph, 0, 2, &[99].into_iter().collect());
        assert!(results.is_empty());
    }

    // ---- extend_used_aworks_get_results ----

    #[test]
    fn extend_tracks_used_aworks_and_builds_tree() {
        let graph = make_test_graph();
        let aworks: HashSet<WT> = [3, 5].into_iter().collect();
        let mut used_aworks = HashSet::new();
        let mut wid_calls: Vec<WT> = vec![];
        let tree = extend_used_aworks_get_results(
            &graph,
            0,
            1,
            &mut |w| wid_calls.push(w),
            &aworks,
            &mut used_aworks,
        );
        assert_eq!(used_aworks, [3u32, 5].into_iter().collect::<HashSet<_>>());
        let top = as_node(&tree);
        // Top-level keys: 1 (via path [1,5]), 2 (via path [2,3]), 3 (direct)
        assert_eq!(sorted_keys(top), [1, 2, 3]);
        assert!(matches!(top.get(&3), Some(RefTree::Leaf)));
        assert_eq!(sorted_keys(as_node(top.get(&1).unwrap())), [5]);
        assert_eq!(sorted_keys(as_node(top.get(&2).unwrap())), [3]);
    }

    #[test]
    fn extend_with_empty_aworks_yields_empty_tree() {
        let graph = make_test_graph();
        let mut used_aworks = HashSet::new();
        let tree = extend_used_aworks_get_results(
            &graph,
            0,
            1,
            &mut |_| {},
            &HashSet::new(),
            &mut used_aworks,
        );
        assert!(used_aworks.is_empty());
        assert!(as_node(&tree).is_empty());
    }

    // ---- author_to_work_paths ----

    #[test]
    fn author_to_work_paths_finds_reachable_aworks() {
        let graph = make_test_graph().with_aworks(7, vec![3, 5]);
        let mut wid_calls: Vec<WT> = vec![];
        let (tree, mut used) = author_to_work_paths(&graph, 0, 7, 1, &mut |w| wid_calls.push(w));
        used.sort();
        assert_eq!(used, [3, 5]);
        assert!(sorted_keys(as_node(&tree)).contains(&3));
    }

    #[test]
    fn author_to_work_paths_no_aworks_yields_empty() {
        let graph = make_test_graph().with_aworks(7, vec![]);
        let (tree, used) = author_to_work_paths(&graph, 0, 7, 1, &mut |_| {});
        assert!(used.is_empty());
        assert!(as_node(&tree).is_empty());
    }
}
