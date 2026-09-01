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

export function buildSubgraphs(
	seen: SeenMap,
	paperMap: Record<number, { year: number }>,
	groupSize = 2
): number[][] {
	const topWids = Object.keys(seen)
		.map(Number)
		.filter((w) => {
			const meta = seen[w];
			return meta && [...meta.parents].every((p) => p === 0);
		})
		.sort((a, b) => (paperMap[b]?.year ?? 0) - (paperMap[a]?.year ?? 0));

	const subgraphs: number[][] = [];
	for (let i = 0; i < topWids.length; i += groupSize) {
		const roots = topWids.slice(i, i + groupSize);
		const rootSet = new Set(topWids);
		const collected = new Set<number>();
		const queue = [...roots];
		for (const r of roots) collected.add(r);
		while (queue.length) {
			const wid = queue.pop()!;
			const meta = seen[wid];
			if (!meta) continue;
			for (const child of meta.children) {
				if (!collected.has(child) && !rootSet.has(child)) {
					collected.add(child);
					queue.push(child);
				}
			}
		}
		subgraphs.push([...collected]);
	}
	return subgraphs;
}

export type ComponentLayers = { top: number[]; mid: number[]; bottom: number[] };

export function classifyComponentLayers(
	wids: number[],
	seen: SeenMap,
	isAuthoredFn: (wid: number) => boolean
): ComponentLayers {
	const top: number[] = [];
	const mid: number[] = [];
	const bottom: number[] = [];

	for (const wid of wids) {
		if (isAuthoredFn(wid)) {
			bottom.push(wid);
		} else {
			const meta = seen[wid];
			const hasOnlyRoot = !meta || [...meta.parents].every((p) => p === 0);
			if (hasOnlyRoot) top.push(wid);
			else mid.push(wid);
		}
	}

	return { top, mid, bottom };
}
