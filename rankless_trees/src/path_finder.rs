use std::{cell::RefCell, rc::Rc};

use hashbrown::{HashMap, HashSet};
use serde::Serialize;

use crate::io::WT;

type RefTreeNodeT = Rc<RefCell<HashMap<WT, RefDAG>>>;

pub struct CitingConnection {
    pub tree: RefDAG,
    pub wids: HashSet<WT>,
}

#[derive(Serialize, Debug, Clone)]
pub enum RefDAG {
    Node(RefTreeNodeT),
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

    fn wrap_tree(tree: HashMap<WT, RefDAG>) -> RefTreeNodeT {
        Rc::new(RefCell::new(tree))
    }

    fn merge(&mut self, other: Self) {
        match self {
            Self::Leaf => {
                *self = other;
            }
            Self::Node(node) => {
                if let Self::Node(other_node) = other {
                    let mut map = node.borrow_mut();
                    for (k, v) in other_node.borrow().iter() {
                        match map.get_mut(k) {
                            Some(existing) => existing.merge(v.clone()),
                            None => {
                                map.insert(*k, v.clone());
                            }
                        }
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
        for &cit in &[10u32, 20] {
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
