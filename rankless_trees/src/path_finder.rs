use std::collections::BinaryHeap;

use hashbrown::{HashMap, HashSet};
use serde::Serialize;

use crate::io::WT;

#[derive(Serialize, Debug, Clone)]
pub enum RefTree {
    Node(Box<HashMap<WT, RefTree>>),
    Leaf,
}

pub trait RefGraph {
    fn get_refs(&self, wid: WT) -> &[WT];
    fn get_cites(&self, wid: WT) -> &[WT];
}

pub fn multi_source_reftree<I1, I2, G, F>(
    graph: &G,
    refed_works: I1,
    citing_works: I2,
    depth: usize,
    wid_fun: &mut F,
) -> (RefTree, Vec<WT>)
where
    G: RefGraph,
    I1: Iterator<Item = WT>,
    I2: Iterator<Item = WT>,
    F: FnMut(WT),
{
    let mut used_works = HashSet::new();
    let mut top_map = HashMap::new();

    let mut mid_from_refside = BinaryHeap::new();
    let mut mid_from_citeside = BinaryHeap::new();
    for cit_wid in citing_works {
        for mid_wid in graph.get_refs(cit_wid) {
            //make sure not in cited_works
        }
    }
    for ref_wid in refed_works {
        for mid_wid in graph.get_refs(ref_wid) {
            //make sure not in refed_works
        }
    }

    (
        RefTree::Node(Box::new(top_map)),
        used_works.into_iter().collect(),
    )
}

pub fn extend_used_works_get_reftree<G, F>(
    graph: &G,
    wid: WT,
    depth: usize,
    wid_fun: &mut F,
    target_works: &HashSet<WT>,
    used_works: &mut HashSet<WT>,
) -> RefTree
where
    G: RefGraph,
    F: FnMut(WT),
{
    let ffun = |rwid: WT| target_works.contains(&rwid);
    let mut results = Vec::new();
    find_paths(graph, &mut results, wid, depth, Vec::new(), &ffun);
    let mut ref_tree_map = HashMap::new();
    let mut inner_wid_fun = |wid: WT| {
        wid_fun(wid);
        if ffun(wid) {
            used_works.insert(wid);
        }
    };
    for path in &results {
        insert_path(&mut ref_tree_map, path, &mut inner_wid_fun);
    }
    RefTree::Node(Box::from(ref_tree_map))
}

fn find_paths<G, F>(
    graph: &G,
    results: Vec<Vec<WT>>,
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
            find_paths(
                graph,
                results,
                refed_wid,
                depth_to_go - 1,
                new_sofar,
                filter_fun,
            );
        }
    }
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

    fn run_find_paths(
        graph: &impl RefGraph,
        wid: WT,
        depth: usize,
        filter: &HashSet<WT>,
    ) -> Vec<Vec<WT>> {
        let mut results = Vec::new();
        find_paths(graph, &mut results, wid, depth, Vec::new(), &|w| {
            filter.contains(&w)
        });
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
        assert_eq!(results, [vec![3]]);
    }

    #[test]
    fn find_paths_depth_one_includes_two_hop_paths() {
        let graph = make_test_graph();
        let filter: HashSet<WT> = [3, 5].into_iter().collect();
        let mut results = run_find_paths(&graph, 0, 1, &filter);
        results.sort();
        assert_eq!(results, [vec![1, 5], vec![2, 3], vec![3]]);
    }

    #[test]
    fn find_paths_self_loop_is_skipped() {
        let graph = TestGraph::new().with_refs(0, vec![0, 1]);
        let filter: HashSet<WT> = [0, 1].into_iter().collect();
        let results = run_find_paths(&graph, 0, 0, &filter);
        assert_eq!(results, [vec![1]]);
    }

    #[test]
    fn find_paths_no_filter_match_yields_nothing() {
        let graph = make_test_graph();
        let results = run_find_paths(&graph, 0, 2, &[99].into_iter().collect());
        assert!(results.is_empty());
    }

    // ---- extend_used_works_get_reftree ----

    #[test]
    fn extend_tracks_used_works_and_builds_tree() {
        let graph = make_test_graph();
        let target_works: HashSet<WT> = [3, 5].into_iter().collect();
        let mut used_works = HashSet::new();
        let mut wid_calls: Vec<WT> = vec![];
        let tree = extend_used_works_get_reftree(
            &graph,
            0,
            1,
            &mut |w| wid_calls.push(w),
            &target_works,
            &mut used_works,
        );
        assert_eq!(used_works, [3u32, 5].into_iter().collect::<HashSet<_>>());
        let top = as_node(&tree);
        assert_eq!(sorted_keys(top), [1, 2, 3]);
        assert!(matches!(top.get(&3), Some(RefTree::Leaf)));
        assert_eq!(sorted_keys(as_node(top.get(&1).unwrap())), [5]);
        assert_eq!(sorted_keys(as_node(top.get(&2).unwrap())), [3]);
    }

    #[test]
    fn extend_with_empty_target_works_yields_empty_tree() {
        let graph = make_test_graph();
        let mut used_works = HashSet::new();
        let tree = extend_used_works_get_reftree(
            &graph,
            0,
            1,
            &mut |_| {},
            &HashSet::new(),
            &mut used_works,
        );
        assert!(used_works.is_empty());
        assert!(as_node(&tree).is_empty());
    }

    // ---- multi_source_reftree ----

    #[test]
    fn multi_source_reftree_merges_paths_from_multiple_sources() {
        let graph = TestGraph::new()
            .with_refs(10, vec![3, 5])
            .with_refs(20, vec![5])
            .with_refs(30, vec![]);
        let targets: HashSet<WT> = [3, 5].into_iter().collect();
        let mut wid_calls: Vec<WT> = vec![];
        let (tree, mut used) = multi_source_reftree(&graph, &[10, 20, 30], &targets, 0, &mut |w| {
            wid_calls.push(w)
        });
        used.sort();
        assert_eq!(used, [3, 5]);
        let top = as_node(&tree);
        assert_eq!(sorted_keys(top), [10, 20]);
        assert!(wid_calls.contains(&10));
        assert!(wid_calls.contains(&20));
        assert!(!wid_calls.contains(&30));
    }

    #[test]
    fn multi_source_reftree_empty_sources_yields_empty() {
        let graph = make_test_graph();
        let targets: HashSet<WT> = [3].into_iter().collect();
        let (tree, used) = multi_source_reftree(&graph, &[], &targets, 0, &mut |_| {});
        assert!(used.is_empty());
        assert!(as_node(&tree).is_empty());
    }
}
