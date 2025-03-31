import { base } from '$app/paths';
import type * as tt from '$lib/tree-types';
import { COMPLETE_YEAR, DEFAULT_LIMIT_N, MAX_LEVEL_COUNT } from './constants';
import { getSpecMetricObject } from './metric-calculation';

export const DEFAULT_CONTROL_SPEC: tt.ControlSpec = {
	include: [],
	exclude: [],
	limit: DEFAULT_LIMIT_N,
	showTop: true,
	sizeBase: 'specialization'
};

type LevelNodeDescription = { path: tt.PathInTree; node: tt.ResponseNode; derivedWeight: number };

export function getDefaultLevelSpecs() {
	return Array(MAX_LEVEL_COUNT)
		.fill(0)
		.map(() => {
			return {
				totalSize: 0,
				topOffset: 0,
				levelOptions: [],
				isVisible: false
			};
		});
}

export function getDefaultControlSpecs(spec: boolean): tt.FullControlSpecs {
	return {
		globalLimit: 10,
		globalSizeBase: spec ? 'specialization' : 'volume',
		levelSpecs: Array(MAX_LEVEL_COUNT)
			.fill(0)
			.map(() => {
				return { ...DEFAULT_CONTROL_SPEC };
			})
	};
}

export function getBreakdownOptions(treeSpecs: tt.TreeSpecs, rootType: tt.RootType) {
	//TODO: this should be cached, its just clutter
	let entityTreeSpecs = treeSpecs.specs[rootType];
	let out: tt.BreakdownOptions = {};
	for (let [i, v] of entityTreeSpecs.entries()) {
		let boObj = out;
		for (let bd of v.breakdowns) {
			const bDef = idFromBd(bd);
			if (!(bDef in boObj)) {
				boObj[bDef] = { children: {}, treeSpecs: [] };
			}
			boObj[bDef].treeSpecs.push(i);
			boObj = boObj[bDef].children;
		}
	}
	return out;
}

export function idFromBd(bd: tt.BreakdownSpec): string {
	return `${bd.attributeType}-${bd.sourceSide}`;
}

export function treeBeUrl(root: string, conf: tt.FullTreeConfig, shallow: undefined | number = undefined): string {
	let url = `${root}/trees/${conf.rootType}/${conf.semanticId}?tid=${conf.treeId}&year=${conf.year}`;
	if (shallow != undefined) {
		url += `&shallow=${shallow}`
	}
	return url
}


export function entToLink(e: { rootType: tt.RootType; semanticId: string }): string {
	return `${base}/${e.rootType}/${e.semanticId}`;
}

export function decorBaseLink(url: string, conf: tt.FullTreeConfig, selectionState: tt.BareNode): string {
	let params = [];
	if (conf.year != getDefaultYear(conf.rootType)) {
		params.push(`since=${conf.year}`);
	}
	if (conf.treeId != 0) {
		params.push(`tree=${conf.treeId + 1}`);
	}
	let selConfStr = nodeToConfStr(selectionState);
	if (selConfStr.length > 0) {
		params.push(`paths=${selConfStr}`);
	}

	if (params.length > 0) {
		url += '?' + params.join('&');
	}
	return url;
}

export function toLinkWithParams(conf: tt.FullTreeConfig, selectionState: tt.BareNode): string {
	let url = entToLink({ rootType: conf.rootType, semanticId: conf.semanticId });
	return decorBaseLink(url, conf, selectionState)
}
export function parseLinkWithParams(params: URLSearchParams, rootType: tt.RootType): tt.ShareSpec {
	let year = parseInt(params.get('since') || getDefaultYear(rootType).toString());
	let treeId = parseInt(params.get('tree') || '1') - 1 || 0;
	let selectionStateStr = params.get('paths') || '';
	let selectionState = nodeFromConfStr(selectionStateStr);
	return { year, treeId, selectionState };
}

export function getDefaultYear(rt: tt.RootType) {
	if (['authors', 'sources', 'institutions'].includes(rt)) {
		return COMPLETE_YEAR
	}
	return 2020
}

function nodeToConfStr(node: tt.BareNode): string {
	let l1cs = [];
	let l2cs = [];
	for (let [ck, cv] of Object.entries(node.children || {})) {
		l1cs.push(ck);
		l2cs.push(cv);
	}
	let l1 = l1cs.join('l');
	return l1;
}

function nodeFromConfStr(confStr: string): tt.BareNode {
	let node: tt.BareNode = { children: {} };
	let levels = confStr.split('x');
	let l1 = levels[0] || '';
	let i = 0;
	for (let e of l1.split('l')) {
		let c = parseInt(e);
		if (c > 0) {
			node.children[c] = { children: {} };
			i += 1;
		}
		if (i > 4) {
			break;
		}
	}
	return node;
}

export function pruneTree(tree: tt.BareNode, depth: number): tt.BareNode {
	if (depth == 0) {
		return { children: {} };
	}
	return {
		children: Object.fromEntries(
			Object.entries(tree.children || {}).map(([k, v]) => [k, pruneTree(v, depth - 1)])
		)
	};
}

export function intersectionTree(smallerTree: tt.BareNode, biggerTree: tt.BareNode): tt.BareNode {
	const children = {};
	for (let kStr of Object.keys(smallerTree.children || {})) {
		if (Object.keys(biggerTree.children || {}).includes(kStr)) {
			let k = parseInt(kStr);
			children[k] = intersectionTree(smallerTree.children[k], biggerTree.children[k] || {});
		}
	}
	return { children };
}

export function deriveVisibleTree(
	root: tt.ResponseNode,
	controls: tt.FullControlSpecs,
	selections: tt.BareNode,
	attributeLabels: tt.AttributeLabels,
	treeSpec: tt.TreeSpec
): tt.TreeInfo {
	const allLevelNodes = flatFilter(root, controls, selections, treeSpec, attributeLabels);

	const meta: tt.DerivedLevelInfo[] = [{ totalNodes: 1, totalWeight: root.linkCount }];
	const tree: tt.EmbeddedNode = {
		name: '',
		weight: root.linkCount,
		isSelected: true,
		children: {},
		childrenSumWeight: 0,
		totalOffsetOnLevel: { weight: 0, rank: 0 },
		totalOffsetAmongSiblings: { weight: 0, rank: 0 },
		scaleEnds: { min: 0, max: 1, mid: 0.5 }
	};

	const getParent = (n: LevelNodeDescription) => getNodeByPath(n.path.slice(0, -1), tree);
	const getParentPathStr = (n: LevelNodeDescription) => n.path.slice(0, -1).join('-');

	for (const levelDesc of allLevelNodes.slice(1)) {
		let levelWeight = 0;
		let levelRank = 0;
		const childrenCounts: tt.OMap<number> = {};
		const sortedLevelDesc: LevelNodeDescription[] = [];

		const orderFun = (l: LevelNodeDescription, r: LevelNodeDescription) => {
			const lParent = getParent(l);
			const rParent = getParent(r);
			if (lParent?.totalOffsetOnLevel.rank == rParent?.totalOffsetOnLevel.rank) {
				const order = r.derivedWeight - l.derivedWeight;
				if (order != 0) return order;
				return lastE(l.path) > lastE(r.path) ? -1 : 1;
			}
			return (lParent?.totalOffsetOnLevel.rank || 0) - (rParent?.totalOffsetOnLevel.rank || 0);
		};

		for (const preSortNodeDesc of levelDesc) {
			const parentPath = getParentPathStr(preSortNodeDesc);
			childrenCounts[parentPath] = (childrenCounts[parentPath] || 0) + 1;
			insertKeepingOrder(preSortNodeDesc, sortedLevelDesc, orderFun);
		}
		for (const nodeDesc of sortedLevelDesc) {
			const parent = getParent(nodeDesc);
			const nChildren = childrenCounts[getParentPathStr(nodeDesc)];
			if (parent?.children != undefined) {
				const scaleStep = (parent?.scaleEnds.max - parent?.scaleEnds.min) / (nChildren || 1);
				const childId = lastE(nodeDesc.path);
				const rank = Object.keys(parent.children).length;
				const scaleMin = parent.scaleEnds.min + (rank || 0) * scaleStep;
				const scaleMax = scaleMin + scaleStep;

				parent.children[childId] = {
					name: getChildName(nodeDesc.path, attributeLabels, treeSpec),
					weight: nodeDesc.derivedWeight,
					isSelected: isPathInTree(nodeDesc.path, selections),
					children: {},
					childrenSumWeight: 0,
					totalOffsetOnLevel: { weight: levelWeight, rank: levelRank },
					totalOffsetAmongSiblings: { weight: parent.childrenSumWeight, rank },
					scaleEnds: { min: scaleMin, max: scaleMax, mid: (scaleMax + scaleMin) / 2 }
				};
				parent.childrenSumWeight += nodeDesc.derivedWeight;
				levelWeight += nodeDesc.derivedWeight;
				levelRank += 1;
			}
		}
		meta.push({ totalWeight: levelWeight, totalNodes: levelRank });
	}
	return { tree, meta };
}

function flatFilter(
	root: tt.ResponseNode,
	controls: tt.FullControlSpecs,
	selections: tt.BareNode,
	treeSpec: tt.TreeSpec,
	attributeLabels: tt.AttributeLabels
): LevelNodeDescription[][] {
	//on each level: (excluded ones should already not be there)
	//collect selected ones
	//collect the spec included ones
	//collect the extreme1
	//go while unfilled

	const outNodes: LevelNodeDescription[][] = [[{ path: [], node: root, derivedWeight: 0 }]];
	if (treeSpec == undefined) return outNodes;

	function getDenomWeight(path: tt.PathInTree) {
		return getNodeByPath(path.slice(0, denomIndex), root)?.linkCount || 0;
	}

	let denomIndex = 0;

	LevelLoop: for (
		let i = 0;
		i < Math.min(controls.levelSpecs.length, treeSpec.breakdowns.length);
		i++
	) {
		const controlSpec = controls.levelSpecs[i];
		let remainingCount = controls.globalLimit || controlSpec.limit;
		const sizeBase = controls.globalSizeBase || controlSpec.sizeBase;
		const lastLevelNodes = outNodes[i];
		const thisLevelNodes: LevelNodeDescription[] = [];
		const includedPaths = new Set();
		const entityKind = treeSpec.breakdowns[i].attributeType;
		denomIndex = treeSpec.breakdowns[i].specDenomInd;

		const weightDerivation =
			sizeBase == 'volume'
				? (node: tt.ResponseNode, childId: number) => childId == 0 ? 0 : (node?.linkCount || 0)
				: (node: tt.ResponseNode, childId: number, denominatorWeight: number) => childId == 0 ? 0 :
					getSpecMetricObject(node, denominatorWeight, attributeLabels[entityKind], childId)
						.specMetric;

		const isBetterExtreme = controlSpec.showTop
			? (l: LevelNodeDescription, r: LevelNodeDescription) => l.derivedWeight - r.derivedWeight
			: (l: LevelNodeDescription, r: LevelNodeDescription) => r.derivedWeight - l.derivedWeight;

		const pushFun = (parent: LevelNodeDescription, childId: number) => {
			if (controlSpec.exclude.includes(childId)) return;
			const path = [...parent.path, childId];
			const node = (parent.node.children || {})[childId];
			includedPaths.add(path.join('-'));
			if (node === undefined) return;
			thisLevelNodes.push({
				node,
				path,
				derivedWeight: weightDerivation(node, childId, getDenomWeight(path))
			});
			remainingCount--;
		};
		const selectedOnLastLevel = lastLevelNodes.filter((e) => isPathInTree(e.path, selections));
		if (selectedOnLastLevel.length == 0) {
			break;
		}
		outNodes.push(thisLevelNodes);

		// forced in due to being selected
		for (const possibleParentOfSelected of selectedOnLastLevel) {
			for (const selectedKey of Object.keys(
				getNodeByPath(possibleParentOfSelected.path, selections)?.children || {}
			)) {
				pushFun(possibleParentOfSelected, parseInt(selectedKey));
				if (remainingCount == 0) continue LevelLoop;
			}
		}

		// forced in due to control
		for (const mustInclude of controlSpec.include) {
			for (const lastLevelsNode of selectedOnLastLevel) {
				if (
					Object.hasOwn(lastLevelsNode.node?.children || {}, mustInclude) &&
					!includedPaths.has([...lastLevelsNode.path, mustInclude].join('-'))
				) {
					pushFun(lastLevelsNode, mustInclude);
					if (remainingCount == 0) continue LevelLoop;
				}
			}
		}

		// keeping it as balanced as possible for the remaining
		// plus what remains in an array
		for (const [i, possibleParent] of selectedOnLastLevel.entries()) {
			const numFromThisLevel = Math.round(remainingCount / (selectedOnLastLevel.length - i));
			if (numFromThisLevel == 0) continue;
			const addFromParent: LevelNodeDescription[] = [];
			const denomWeight = getDenomWeight(possibleParent.path);
			for (const [childIdStr, childNode] of Object.entries(possibleParent.node.children || {})) {
				const childId = parseInt(childIdStr);
				if (controlSpec.exclude.includes(childId)) continue;
				const childPath = [...possibleParent.path, childId];
				if (includedPaths.has(childPath.join('-'))) continue;
				const childLevelNodeDesc = {
					node: childNode,
					path: childPath,
					derivedWeight: weightDerivation(childNode, childId, denomWeight)
				};
				if (addFromParent.length < numFromThisLevel) {
					insertKeepingOrder(childLevelNodeDesc, addFromParent, isBetterExtreme);
				} else {
					if (isBetterExtreme(addFromParent[0], childLevelNodeDesc) < 0) {
						addFromParent.shift();
						insertKeepingOrder(childLevelNodeDesc, addFromParent, isBetterExtreme);
					}
				}
			}
			addFromParent.map((v) => thisLevelNodes.push(v));
			remainingCount -= addFromParent.length;
		}
	}
	return outNodes;
}

export function insertKeepingOrder<T>(elem: T, arr: T[], f: (l: T, r: T) => number) {
	//0 if equal, -x if l is 'less desirable'
	let left = 0;
	let right = arr.length - 1;
	let mid: number;
	let compRes: number;

	while (left <= right) {
		mid = Math.floor((left + right) / 2);
		compRes = f(arr[mid], elem);

		if (compRes == 0) {
			return arr.splice(mid, 0, elem);
		} else if (compRes < 0) {
			left = mid + 1;
		} else {
			right = mid - 1;
		}
	}
	arr.splice(left, 0, elem);
}

export function getNodeByPath<S, T extends tt.TreeGen<S>>(
	path: tt.PathInTree,
	root: T | undefined
): T | undefined {
	let lChild = root;
	for (const cid of path) {
		lChild = (lChild?.children || {})[cid] as T | undefined;
		if (lChild === undefined) {
			return lChild;
		}
	}
	return lChild;
}

export function isPathInTree(path: tt.PathInTree, root: tt.BareNode): boolean {
	return getNodeByPath(path, root) != undefined;
}

export function getSomePath(tree: tt.BareNode): tt.PathInTree {
	const path: tt.PathInTree = [];
	for (const [k, v] of Object.entries(tree.children || {})) {
		return [parseInt(k), ...getSomePath(v)];
	}
	return path;
}

export function getChildName(
	path: tt.PathInTree,
	attributeLabels: tt.AttributeLabels,
	treeSpec: tt.TreeSpec
) {
	if (attributeLabels === undefined) {
		return 'Loading...';
	}
	return nameById(attributeLabels, getEntityKind(path, treeSpec), lastE(path));
}

export function nameById(labels: tt.AttributeLabels, atype: tt.EntityType, id: number) {
	const DEFAULT = 'Unknown';
	let emap = labels[atype];
	if (emap === undefined) {
		return DEFAULT;
	}
	return emap[id]?.name || DEFAULT;
}

export function getEntityKind(path: tt.PathInTree, treeSpec: tt.TreeSpec) {
	return treeSpec.breakdowns[path.length - 1].attributeType;
}

export const treePathToStr = (path: tt.PathInTree) => path.join('x');

export const pathStrToPath = (pathStr: string) => pathStr.split('x');

function lastE<T>(arr: T[]): T {
	return arr[arr.length - 1];
}
