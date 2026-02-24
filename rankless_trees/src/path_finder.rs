use std::{cell::RefCell, rc::Rc};

use hashbrown::{HashMap, HashSet};
use serde::Serialize;

use crate::io::WT;

type RefDAGNodeT = Rc<RefCell<HashMap<WT, RefDAG>>>;

pub struct CitingConnection {
    pub tree: RefDAG,
    pub wids: HashSet<WT>,
}

#[derive(Serialize, Debug, Clone)]
pub enum RefDAG {
    Node(RefDAGNodeT),
    Leaf,
}

pub trait RefGraph {
    fn get_refs(&self, wid: WT) -> &[WT];
    fn get_cites(&self, wid: WT) -> &[WT];
}

impl RefDAG {
    pub fn new_map() -> Self {
        Self::from_tree(HashMap::new())
    }

    fn from_tree(tree: HashMap<WT, RefDAG>) -> Self {
        RefDAG::Node(Self::wrap_tree(tree))
    }

    fn wrap_tree(tree: HashMap<WT, RefDAG>) -> RefDAGNodeT {
        Rc::new(RefCell::new(tree))
    }

    pub fn merge(&mut self, other: Self) {
        let mut visited = HashSet::new();
        self.merge_with_visited(other, &mut visited);
    }

    fn merge_with_visited(&mut self, other: Self, visited: &mut HashSet<(usize, usize)>) {
        match self {
            Self::Leaf => {
                *self = other;
            }

            Self::Node(self_node) => {
                if let Self::Node(other_node) = other {
                    if Rc::ptr_eq(self_node, &other_node) {
                        return;
                    }

                    let self_ptr = Rc::as_ptr(self_node) as usize;
                    let other_ptr = Rc::as_ptr(&other_node) as usize;

                    if !visited.insert((self_ptr, other_ptr)) {
                        return;
                    }

                    let mut to_recurse = Vec::new();
                    let mut to_insert = Vec::new();

                    {
                        let mut self_map = self_node.borrow_mut();
                        let other_map = other_node.borrow();

                        for (k, other_child) in other_map.iter() {
                            if let Some(self_child) = self_map.get_mut(k) {
                                to_recurse.push((self_child.clone(), other_child.clone()));
                            } else {
                                to_insert.push((k.clone(), other_child.clone()));
                            }
                        }

                        for (k, v) in to_insert {
                            self_map.insert(k, v);
                        }
                    }

                    for (mut self_child, other_child) in to_recurse {
                        self_child.merge_with_visited(other_child, visited);
                    }
                }
            }
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
    let mut tree_map: HashMap<WT, RefDAG> = HashMap::new();
    let mut reached: HashSet<WT> = HashSet::new();

    for &cit in citing_wids {
        let mut sub: HashMap<WT, RefDAG> = HashMap::new();
        for &refed in graph.get_refs(cit) {
            if refed_set.contains(&refed) {
                reached.insert(refed);
                reached.insert(cit);
                sub.insert(refed, RefDAG::Leaf);
            }
        }
        if !sub.is_empty() {
            tree_map.insert(cit, RefDAG::from_tree(sub));
        }
    }
    CitingConnection {
        tree: RefDAG::from_tree(tree_map),
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
        let mut sub: HashMap<WT, RefDAG> = HashMap::new();
        for &mid_wid in graph.get_refs(cit) {
            if !refed_set.contains(&mid_wid) & inter_from_refed.contains_key(&mid_wid) {
                inter_from_citing.entry(mid_wid).or_default().push(cit);
                resp.wids.insert(mid_wid);
                resp.wids.insert(cit);
                let mid_tree = found_mids.entry(mid_wid).or_insert_with(|| {
                    RefDAG::wrap_tree(HashMap::from_iter(
                        inter_from_refed[&mid_wid]
                            .iter()
                            .map(|ref_wid| (*ref_wid, RefDAG::Leaf)),
                    ))
                });
                sub.insert(mid_wid, RefDAG::Node(mid_tree.clone()));
            }
        }
        if !sub.is_empty() {
            l2_map.insert(cit, RefDAG::from_tree(sub));
        }
    }

    resp.tree.merge(RefDAG::from_tree(l2_map));
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_utils::TestGraph;

    fn node_map(tree: &RefDAG) -> std::cell::Ref<'_, HashMap<WT, RefDAG>> {
        match tree {
            RefDAG::Node(rc) => rc.borrow(),
            RefDAG::Leaf => panic!("expected Node, got Leaf"),
        }
    }

    fn sorted_keys(map: &HashMap<WT, RefDAG>) -> Vec<WT> {
        let mut keys: Vec<WT> = map.keys().copied().collect();
        keys.sort();
        keys
    }

    fn refed_set(wids: &[WT]) -> HashSet<WT> {
        wids.iter().copied().collect()
    }

    // ---- direct links ----

    #[test]
    fn direct_refs_to_refed() {
        let graph = TestGraph::new()
            .with_refs(10, vec![3, 5])
            .with_refs(20, vec![5])
            .with_refs(30, vec![]);
        let conn = get_direct_links(&graph, refed_set(&[3, 5]), &[10, 20, 30]);
        let top = node_map(&conn.tree);
        assert_eq!(sorted_keys(&top), [10, 20]);
        assert!(conn.wids.contains(&10));
        assert!(conn.wids.contains(&20));
        assert!(!conn.wids.contains(&30));
    }

    #[test]
    fn direct_empty_citing_yields_empty() {
        let graph = TestGraph::new().with_refs(10, vec![3]);
        let conn = get_direct_links(&graph, refed_set(&[3]), &[]);
        assert!(conn.wids.is_empty());
        assert!(node_map(&conn.tree).is_empty());
    }

    #[test]
    fn direct_no_refed_match_yields_empty() {
        let graph = TestGraph::new().with_refs(10, vec![2]);
        let conn = get_direct_links(&graph, refed_set(&[3]), &[10]);
        assert!(conn.wids.is_empty());
        assert!(node_map(&conn.tree).is_empty());
    }

    // ---- once-removed ----

    #[test]
    fn once_removed_finds_intermediate() {
        let graph = TestGraph::new()
            .with_refs(10, vec![4])
            .with_refs(4, vec![3]);
        let mut conn = get_direct_links(&graph, refed_set(&[3]), &[10]);
        extend_with_once_removed(&graph, refed_set(&[3]), &[10], &mut conn);
        let top = node_map(&conn.tree);
        assert_eq!(sorted_keys(&top), [10]);
        let sub10 = node_map(top.get(&10).unwrap());
        assert_eq!(sorted_keys(&sub10), [4]);
        let sub_4 = node_map(sub10.get(&4).unwrap());
        assert!(matches!(sub_4.get(&3), Some(RefDAG::Leaf)));
    }

    #[test]
    fn once_removed_shared_intermediate_deduplicates() {
        let graph = TestGraph::new()
            .with_refs(10, vec![4])
            .with_refs(20, vec![4])
            .with_refs(4, vec![3]);
        let mut conn = get_direct_links(&graph, refed_set(&[3]), &[10, 20]);
        extend_with_once_removed(&graph, refed_set(&[3]), &[10, 20], &mut conn);
        let top = node_map(&conn.tree);
        assert_eq!(sorted_keys(&top), [10, 20]);
        for &cit in &[10, 20] {
            let sub = node_map(top.get(&cit).unwrap());
            assert_eq!(sorted_keys(&sub), [4]);
            let sub_4 = node_map(sub.get(&4).unwrap());
            assert!(matches!(sub_4.get(&3), Some(RefDAG::Leaf)));
        }
    }

    #[test]
    fn once_removed_no_path_excluded() {
        let graph = TestGraph::new()
            .with_refs(10, vec![4])
            .with_refs(20, vec![6])
            .with_refs(4, vec![3])
            .with_refs(6, vec![]);
        let mut conn = get_direct_links(&graph, refed_set(&[3]), &[10, 20]);
        extend_with_once_removed(&graph, refed_set(&[3]), &[10, 20], &mut conn);
        let top = node_map(&conn.tree);
        assert_eq!(sorted_keys(&top), [10]);
    }

    #[test]
    fn direct_and_once_removed_in_same_citing() {
        let graph = TestGraph::new()
            .with_refs(10, vec![3, 4])
            .with_refs(4, vec![5]);
        let rs = refed_set(&[3, 5]);
        let mut conn = get_direct_links(&graph, rs.clone(), &[10]);
        extend_with_once_removed(&graph, rs, &[10], &mut conn);
        let top = node_map(&conn.tree);
        let sub10 = node_map(top.get(&10).unwrap());
        assert!(matches!(sub10.get(&3), Some(RefDAG::Leaf)));
        let sub_4 = node_map(sub10.get(&4).unwrap());
        assert!(matches!(sub_4.get(&5), Some(RefDAG::Leaf)));
    }

    #[test]
    fn merge_when_both_sides_share_same_inner_rc() {
        // Diamond shape: two outer nodes both map key 1 → the same inner Rc.
        // merge calls borrow_mut on that Rc (via `self`) then borrow on the same Rc
        // (via `other`) in the recursive step → RefCell double-borrow panic.
        let shared = RefDAG::wrap_tree(HashMap::from([(3, RefDAG::Leaf)]));
        let mut dag = RefDAG::from_tree(HashMap::from([(1, RefDAG::Node(shared.clone()))]));
        let other = RefDAG::from_tree(HashMap::from([(1, RefDAG::Node(shared))]));
        dag.merge(other);
    }

    #[test]
    fn merge_simple_branching() {
        let mut a = RefDAG::new_map();
        let b = RefDAG::new_map();

        // a: 1 -> {2}
        if let RefDAG::Node(ref node) = a {
            node.borrow_mut().insert(1, {
                let child = RefDAG::new_map();
                if let RefDAG::Node(ref cnode) = child {
                    cnode.borrow_mut().insert(2, RefDAG::Leaf);
                }
                child
            });
        }

        // b: 1 -> {3}
        if let RefDAG::Node(ref node) = b {
            node.borrow_mut().insert(1, {
                let child = RefDAG::new_map();
                if let RefDAG::Node(ref cnode) = child {
                    cnode.borrow_mut().insert(3, RefDAG::Leaf);
                }
                child
            });
        }

        a.merge(b);

        // Expect: 1 -> {2,3}
        if let RefDAG::Node(node) = a {
            let map = node.borrow();
            let child = map.get(&1).unwrap();

            if let RefDAG::Node(cnode) = child {
                let c = cnode.borrow();
                assert!(c.contains_key(&2));
                assert!(c.contains_key(&3));
            } else {
                panic!("expected node");
            }
        }
    }

    #[test]
    fn merge_preserves_sharing() {
        let shared = RefDAG::new_map();

        // Insert child 42 into shared
        if let RefDAG::Node(ref node) = shared {
            node.borrow_mut().insert(42, RefDAG::Leaf);
        }

        let mut a = RefDAG::new_map();
        let b = RefDAG::new_map();

        // both point to same shared node
        if let RefDAG::Node(ref node) = a {
            node.borrow_mut().insert(1, shared.clone());
        }
        if let RefDAG::Node(ref node) = b {
            node.borrow_mut().insert(1, shared.clone());
        }

        a.merge(b);

        // after merge, child must still be same Rc
        if let RefDAG::Node(node) = a {
            let map = node.borrow();
            let child = map.get(&1).unwrap();

            if let RefDAG::Node(child_node) = child {
                assert_eq!(Rc::strong_count(child_node), 2);
            }
        }
    }

    #[test]
    fn merge_handles_cycle() {
        let mut a = RefDAG::new_map();
        let b = RefDAG::new_map();

        // create cycle in a
        if let RefDAG::Node(ref node) = a {
            node.borrow_mut().insert(1, a.clone());
        }

        // create cycle in b
        if let RefDAG::Node(ref node) = b {
            node.borrow_mut().insert(1, b.clone());
        }

        // should NOT stack overflow
        a.merge(b);
    }

    #[test]
    fn merge_does_not_double_merge_shared_nodes() {
        let shared = RefDAG::new_map();

        let mut a = RefDAG::new_map();
        let b = RefDAG::new_map();

        if let RefDAG::Node(ref node) = a {
            node.borrow_mut().insert(1, shared.clone());
            node.borrow_mut().insert(2, shared.clone());
        }

        if let RefDAG::Node(ref node) = b {
            node.borrow_mut().insert(1, shared.clone());
            node.borrow_mut().insert(2, shared.clone());
        }

        a.merge(b);

        // if visited logic is wrong, this may recurse exponentially
        // or duplicate children
    }

    #[test]
    fn leaf_becomes_node() {
        let mut a = RefDAG::Leaf;

        let b = RefDAG::new_map();
        if let RefDAG::Node(ref node) = b {
            node.borrow_mut().insert(7, RefDAG::Leaf);
        }

        a.merge(b);

        if let RefDAG::Node(node) = a {
            assert!(node.borrow().contains_key(&7));
        } else {
            panic!("Leaf should become Node");
        }
    }

    #[test]
    fn once_removed_wids_covers_all_tree_nodes() {
        let graph = TestGraph::new()
            .with_refs(10, vec![4])
            .with_refs(20, vec![])
            .with_refs(4, vec![3]);
        let mut conn = get_direct_links(&graph, refed_set(&[3]), &[10, 20]);
        extend_with_once_removed(&graph, refed_set(&[3]), &[10, 20], &mut conn);
        assert!(conn.wids.contains(&10));
        assert!(conn.wids.contains(&4));
        assert!(!conn.wids.contains(&20));
    }
}
