use std::{cell::RefCell, rc::Rc};

use hashbrown::{HashMap, HashSet};
use serde::Serialize;

use crate::io::WT;

type RefTreeNodeT = Rc<RefCell<HashMap<WT, RefTree>>>;

pub struct CitingConnection {
    tree: RefTree,
    wids: HashSet<WT>,
}

#[derive(Serialize, Debug, Clone)]
pub enum RefTree {
    Node(RefTreeNodeT),
    Leaf,
}

pub trait RefGraph {
    fn get_refs(&self, wid: WT) -> &[WT];
    fn get_cites(&self, wid: WT) -> &[WT];
}

impl RefTree {
    fn new_map() -> Self {
        Self::from_tree(HashMap::new())
    }

    fn from_tree(tree: HashMap<WT, RefTree>) -> Self {
        RefTree::Node(Self::wrap_tree(tree))
    }

    fn wrap_tree(tree: HashMap<WT, RefTree>) -> RefTreeNodeT {
        Rc::new(RefCell::new(tree))
    }

    fn merge(&mut self, other: Self) {
        match self {
            Self::Leaf => {
                *self = other;
            }
            Self::Node(node) => {
                if let Self::Node(other_node) = other {
                    for (k, v) in other_node.as_ref().borrow() {
                        v;
                    }
                }
            }
        }
    }
}

fn extend_child(tree: &mut HashMap<WT, RefTree>, k: WT, new_children: &Vec<WT>) {
    let entry = tree.entry(k).or_insert_with(|| RefTree::new_map());
    if let RefTree::Leaf = entry {
        *entry = RefTree::new_map();
    }
    if let RefTree::Node(map_rc) = entry {
        let mut map = map_rc.borrow_mut();
        for &new_child in new_children.iter() {
            map.entry(new_child).or_insert(RefTree::Leaf);
        }
    }
}

pub fn get_direct_links<G>(
    graph: &G,
    refed_set: HashSet<WT>,
    citing_wids: &[WT],
) -> CitingConnection
where
    G: RefGraph,
{
    let mut tree_map: HashMap<WT, RefTree> = HashMap::new();
    let mut reached: HashSet<WT> = HashSet::new();

    for &cit in citing_wids {
        let mut sub: HashMap<WT, RefTree> = HashMap::new();
        for &refed in graph.get_refs(cit) {
            if refed_set.contains(&refed) {
                reached.insert(refed);
                reached.insert(cit);
                sub.insert(refed, RefTree::Leaf);
            }
        }
        if !sub.is_empty() {
            tree_map.insert(cit, RefTree::from_tree(sub));
        }
    }
    CitingConnection {
        tree: RefTree::from_tree(tree_map),
        wids: reached,
    }
}

pub fn extend_with_once_removed<G>(
    graph: &G,
    refed_set: HashSet<WT>,
    citing_wids: &[WT],
    resp: &mut CitingConnection,
) where
    G: RefGraph,
{
    //resp.tree should only contain first level keys that are present in refed_set
    let mut inter_from_refed: HashMap<WT, Vec<WT>> = HashMap::new();
    for &refed in refed_set.iter() {
        for &mid_wid in graph.get_cites(refed) {
            if !refed_set.contains(&mid_wid) {
                inter_from_refed.entry(mid_wid).or_default().push(refed);
            }
        }
    }

    let mut inter_from_citing: HashMap<WT, Vec<WT>> = HashMap::new();
    let mut found_mids = HashMap::new();
    let mut l2_map = HashMap::new();
    for &cit in citing_wids {
        let mut sub: HashMap<WT, RefTree> = HashMap::new();
        for &mid_wid in graph.get_refs(cit) {
            if !refed_set.contains(&mid_wid) & inter_from_refed.contains_key(&mid_wid) {
                inter_from_citing.entry(mid_wid).or_default().push(cit);
                resp.wids.insert(mid_wid);
                resp.wids.insert(cit);
                let mid_tree = found_mids.entry(mid_wid).or_insert_with(|| {
                    RefTree::wrap_tree(HashMap::from_iter(
                        inter_from_refed[&mid_wid]
                            .iter()
                            .map(|ref_wid| (*ref_wid, RefTree::Leaf)),
                    ))
                });
                sub.insert(mid_wid, RefTree::Node(mid_tree.clone()));
            }
        }
        if !sub.is_empty() {
            l2_map.insert(cit, RefTree::from_tree(sub));
        }
    }

    resp.tree.merge(RefTree::from_tree(l2_map));
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

    // ---- depth=0 ----

    #[test]
    fn depth0_direct_refs_to_refed() {
        // citing 10 refs [3,5], citing 20 refs [5], citing 30 refs nothing
        // refed = [3, 5]
        let graph = TestGraph::new()
            .with_refs(10, vec![3, 5])
            .with_refs(20, vec![5])
            .with_refs(30, vec![]);
        let mut wid_calls: Vec<WT> = vec![];
        let (tree, mut used) = multi_source_reftree(&graph, &[3, 5], &[10, 20, 30], 0, &mut |w| {
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
    fn depth0_empty_citing_yields_empty() {
        let graph = TestGraph::new().with_refs(10, vec![3]);
        let (tree, used) = multi_source_reftree(&graph, &[3], &[], 0, &mut |_| {});
        assert!(used.is_empty());
        assert!(as_node(&tree).is_empty());
    }

    #[test]
    fn depth0_no_refed_match_yields_empty() {
        let graph = TestGraph::new().with_refs(10, vec![2]);
        let (tree, used) = multi_source_reftree(&graph, &[3], &[10], 0, &mut |_| {});
        assert!(used.is_empty());
        assert!(as_node(&tree).is_empty());
    }

    // ---- depth=1 bidirectional ----

    #[test]
    fn depth1_finds_intermediate_via_both_sides() {
        // citing 10 refs intermediate 4; 4 cites refed 3 (i.e. refs[4]=[3])
        // with_refs auto-builds cites, so get_cites(3)=[4] and get_cites(4)=[10]
        let graph = TestGraph::new()
            .with_refs(10, vec![4])
            .with_refs(4, vec![3]);
        let (tree, mut used) = multi_source_reftree(&graph, &[3], &[10], 1, &mut |_| {});
        used.sort();
        assert_eq!(used, [3]);
        let top = as_node(&tree);
        assert_eq!(sorted_keys(top), [10]);
        let sub10 = as_node(top.get(&10).unwrap());
        assert_eq!(sorted_keys(sub10), [4]);
        let sub_4 = as_node(sub10.get(&4).unwrap());
        assert!(matches!(sub_4.get(&3), Some(RefTree::Leaf)));
    }

    #[test]
    fn depth1_shared_intermediate_deduplicates() {
        // citing 10 and 20 both ref intermediate 4; 4 refs refed 3
        let graph = TestGraph::new()
            .with_refs(10, vec![4])
            .with_refs(20, vec![4])
            .with_refs(4, vec![3]);
        let (tree, _) = multi_source_reftree(&graph, &[3], &[10, 20], 1, &mut |_| {});
        let top = as_node(&tree);
        assert_eq!(sorted_keys(top), [10, 20]);
        for &cit in &[10u32, 20] {
            let sub = as_node(top.get(&cit).unwrap());
            assert_eq!(sorted_keys(sub), [4]);
            assert!(matches!(
                as_node(sub.get(&4).unwrap()).get(&3),
                Some(RefTree::Leaf)
            ));
        }
    }

    #[test]
    fn depth1_citing_with_no_path_excluded() {
        // citing 10 goes through 4→3; citing 20 goes through 6 which has no path
        let graph = TestGraph::new()
            .with_refs(10, vec![4])
            .with_refs(20, vec![6])
            .with_refs(4, vec![3])
            .with_refs(6, vec![]);
        let (tree, _) = multi_source_reftree(&graph, &[3], &[10, 20], 1, &mut |_| {});
        let top = as_node(&tree);
        assert_eq!(sorted_keys(top), [10]);
    }

    #[test]
    fn depth1_direct_and_intermediate_in_same_citing() {
        // citing 10: refs [3 (direct refed), 4 (intermediate to refed 5)]
        let graph = TestGraph::new()
            .with_refs(10, vec![3, 4])
            .with_refs(4, vec![5]);
        let (tree, mut used) = multi_source_reftree(&graph, &[3, 5], &[10], 1, &mut |_| {});
        used.sort();
        assert_eq!(used, [3, 5]);
        let top = as_node(&tree);
        let sub10 = as_node(top.get(&10).unwrap());
        assert!(matches!(sub10.get(&3), Some(RefTree::Leaf)));
        let sub_4 = as_node(sub10.get(&4).unwrap());
        assert!(matches!(sub_4.get(&5), Some(RefTree::Leaf)));
    }

    #[test]
    fn depth1_wid_fun_covers_all_tree_nodes() {
        let graph = TestGraph::new()
            .with_refs(10, vec![4])
            .with_refs(20, vec![])
            .with_refs(4, vec![3]);
        let mut seen: HashSet<WT> = HashSet::new();
        multi_source_reftree(&graph, &[3], &[10, 20], 1, &mut |w| {
            seen.insert(w);
        });
        assert!(seen.contains(&10)); // citing
        assert!(seen.contains(&4)); // intermediate
        assert!(seen.contains(&3)); // refed
        assert!(!seen.contains(&20)); // no path
    }
}
