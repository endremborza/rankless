import type { RefTree } from '$lib/tree-types';

export type NodeMeta = { level: number; parents: Set<number>; children: Set<number> };
export type SeenMap = Record<number, NodeMeta>;

function build(node: RefTree, seen: SeenMap, depth: number, parent: number) {
	if (node === 'Leaf') return;
	for (const key of Object.keys(node.Node).map(Number)) {
		const isNew = seen[key] == undefined;
		const promoted = !isNew && seen[key].level > depth;
		if (isNew) {
			seen[key] = { level: depth, parents: new Set(), children: new Set() };
		} else if (promoted) {
			seen[key].level = depth;
		}
		// Always register the edge — even when key sits at a shallower level than depth.
		// The previous code guarded on (depth === seen[key].level), which silently dropped
		// edges for nodes already reached via a shorter path.
		seen[key].parents.add(parent);
		if (parent !== 0) {
			(seen[parent] ??= {
				level: depth - 1,
				parents: new Set(),
				children: new Set()
			}).children.add(key);
		}
		// Only recurse when truly new or promoted; already-processed subtrees are complete.
		if (isNew || promoted) {
			build(node.Node[key], seen, depth + 1, key);
		}
	}
}

export function computeSeen(t: RefTree): SeenMap {
	const seen: SeenMap = {};
	build(t, seen, 0, 0);
	return seen;
}
