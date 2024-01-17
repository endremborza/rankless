import type { QcSpec, DerivedLevelInfo, ControlSpec, BareNode, AttributeLabels, PathInTree, TreeInfo, LevelVisual, EmbeddedNode, WeightedNode, TreeGen, OMap, SpecBaseOptions } from './tree-types'
import { DEFAULT_LIMIT_N } from './constants';
import { DEFAULT_SPEC_BASES, getSpecMetricObject } from './metric-calculation';

export const DEFAULT_CONTROL_SPEC: ControlSpec = { include: [], exclude: [], limit_n: DEFAULT_LIMIT_N, show_top: true, size_base: 'volume' }

type LevelNodeDescription = { path: PathInTree, node: WeightedNode, derivedWeight: number };


export function deriveVisibleTree(
    rootId: string,
    root: WeightedNode,
    controls: ControlSpec[],
    selections: BareNode,
    attributeLabels: AttributeLabels,
    qcSpec: QcSpec,
    specBaselineOptions: SpecBaseOptions
): TreeInfo {

    const specCalcFun = (node: WeightedNode, path: PathInTree) => {
        const entityKind = getEntityKind(path, qcSpec);
        return getSpecMetricObject(root, DEFAULT_SPEC_BASES[entityKind], path, rootId, qcSpec, specBaselineOptions, attributeLabels).specMetric;
    }


    const allLevelNodes = flatFilter(root, controls, selections, specCalcFun);

    const meta: DerivedLevelInfo[] = [{ totalNodes: 1, totalWeight: root.weight }]
    const tree: EmbeddedNode = {
        name: '',
        weight: root.weight,
        isSelected: true,
        children: {},
        childrenSumWeight: 0,
        totalOffsetOnLevel: { weight: 0, rank: 0 },
        totalOffsetAmongSiblings: { weight: 0, rank: 0 },
        scaleEnds: { min: 0, max: 1, mid: 0.5 },
        specMetric: { rawMetric: 0, normalizedMetric: 0 }
    }

    const getParent = (n: LevelNodeDescription) => (getNodeByPath(n.path.slice(0, -1), tree))
    const getParentPathStr = (n: LevelNodeDescription) => (n.path.slice(0, -1).join('-'))

    for (const [levelN, levelDesc] of allLevelNodes.slice(1).entries()) {
        const controlSpec = controls[levelN];
        let levelWeight = 0;
        let levelRank = 0;
        const childrenCounts: OMap<number> = {};
        const sortedLevelDesc: LevelNodeDescription[] = [];

        const orderFun = (l: LevelNodeDescription, r: LevelNodeDescription) => {
            const lParent = getParent(l);
            const rParent = getParent(r);
            if (lParent?.totalOffsetOnLevel.rank == rParent?.totalOffsetOnLevel.rank) {
                const order = l.derivedWeight - r.derivedWeight;
                if (order != 0) return order;
                return lastE(l.path) > lastE(r.path) ? -1 : 1
            }
            return (lParent?.totalOffsetOnLevel.rank || 0) - (rParent?.totalOffsetOnLevel.rank || 0)
        }

        for (const preSortNodeDesc of levelDesc) {
            const parentPath = getParentPathStr(preSortNodeDesc);
            childrenCounts[parentPath] = (childrenCounts[parentPath] || 0) + 1
            insertKeepingOrder(preSortNodeDesc, sortedLevelDesc, orderFun)
        }
        for (const nodeDesc of sortedLevelDesc) {
            const parent = getParent(nodeDesc);
            const nChildren = childrenCounts[getParentPathStr(nodeDesc)];
            if (parent?.children != undefined) {
                const scaleStep = (parent?.scaleEnds.max - parent?.scaleEnds.min) / (nChildren || 1);;
                const childId = lastE(nodeDesc.path);
                const rank = Object.keys(parent.children).length;
                const scaleMin = parent.scaleEnds.min + (rank || 0) * scaleStep;
                const scaleMax = scaleMin + scaleStep;

                const specMetric = (controlSpec.size_base == 'specialization') ?
                    { rawMetric: nodeDesc.node.weight, normalizedMetric: 0 } :
                    { rawMetric: 0, normalizedMetric: 0 }

                parent.children[childId] = {
                    name: getChildName(nodeDesc.path, attributeLabels, qcSpec),
                    weight: nodeDesc.derivedWeight,
                    isSelected: isPathInTree(nodeDesc.path, selections),
                    children: {},
                    childrenSumWeight: 0,
                    totalOffsetOnLevel: { weight: levelWeight, rank: levelRank },
                    totalOffsetAmongSiblings: { weight: parent.childrenSumWeight, rank },
                    scaleEnds: { min: scaleMin, max: scaleMax, mid: (scaleMax + scaleMin) / 2 },
                    specMetric
                };
                parent.childrenSumWeight += nodeDesc.derivedWeight;
                levelWeight += nodeDesc.derivedWeight;
                levelRank += 1;
            }
        }
        meta.push({ totalWeight: levelWeight, totalNodes: levelRank })
    }
    return { tree, meta }

}



function flatFilter(root: WeightedNode, controls: ControlSpec[], selections: BareNode, specCalcFun: (n: WeightedNode, p: PathInTree) => number): LevelNodeDescription[][] {
    //on each level: (excluded ones should already not be there)
    //collect selected ones
    //collect the spec included ones
    //collect the extreme1
    //go while unfilled

    const outNodes: LevelNodeDescription[][] = [[{ path: [], node: root, derivedWeight: 0 }]]

    LevelLoop:
    for (let i = 0; i < controls.length; i++) {
        const controlSpec = controls[i];
        let remainingCount = controlSpec.limit_n;
        const lastLevelNodes = outNodes[i];
        const thisLevelNodes: LevelNodeDescription[] = []
        const includedPaths = new Set();

        const weightDerivation = (controlSpec.size_base == 'volume') ?
            (node: WeightedNode) => (node.weight) : specCalcFun;

        const isBetterExtreme = (controlSpec.show_top) ?
            (l: LevelNodeDescription, r: LevelNodeDescription) => (l.derivedWeight - r.derivedWeight) :
            (l: LevelNodeDescription, r: LevelNodeDescription) => (r.derivedWeight - l.derivedWeight);


        const pushFun = (parent: LevelNodeDescription, childId: string) => {
            if (controlSpec.exclude.includes(childId)) return;
            const path = [...parent.path, childId];
            const node = parent.node.children[childId];
            includedPaths.add(path.join("-"));
            thisLevelNodes.push({ node, path, derivedWeight: weightDerivation(node, path) })
            remainingCount--;
        }
        const selectedOnLastLevel = lastLevelNodes.filter((e) => (isPathInTree(e.path, selections)))
        if (selectedOnLastLevel.length == 0) {
            break
        }
        outNodes.push(thisLevelNodes)

        // forced in due to being selected
        for (const possibleParentOfSelected of selectedOnLastLevel) {
            for (const selectedKey of Object.keys(getNodeByPath(possibleParentOfSelected.path, selections)?.children || {})) {
                pushFun(possibleParentOfSelected, selectedKey)
                if (remainingCount == 0) continue LevelLoop;
            }
        }

        // forced in due to control
        for (const mustInclude of controlSpec.include) {
            for (const lastLevelsNode of selectedOnLastLevel) {
                if (Object.hasOwn(lastLevelsNode.node?.children || {}, mustInclude) && !includedPaths.has([...lastLevelsNode.path, mustInclude].join('-'))) {
                    pushFun(lastLevelsNode, mustInclude)
                    if (remainingCount == 0) continue LevelLoop;
                }
            }
        }

        // keeping it as balanced as possible for the remaining
        // plus what remains in an array
        for (const [i, possibleParent] of selectedOnLastLevel.entries()) {
            const numFromThisLevel = Math.round(remainingCount / (selectedOnLastLevel.length - i));
            if (numFromThisLevel == 0) continue;
            const addFromParent: LevelNodeDescription[] = []
            for (const [childId, childNode] of Object.entries(possibleParent.node.children || {})) {
                if (controlSpec.exclude.includes(childId)) continue;
                const childPath = [...possibleParent.path, childId];
                if (includedPaths.has(childPath.join("-"))) continue;
                const childLevelNodeDesc = { node: childNode, path: childPath, derivedWeight: weightDerivation(childNode, childPath) }
                if (addFromParent.length < numFromThisLevel) {
                    insertKeepingOrder(childLevelNodeDesc, addFromParent, isBetterExtreme)
                } else {
                    if (isBetterExtreme(addFromParent[0], childLevelNodeDesc) < 0) {
                        addFromParent.shift();
                        insertKeepingOrder(childLevelNodeDesc, addFromParent, isBetterExtreme)
                    }
                }
            }
            addFromParent.map((v) => thisLevelNodes.push(v))
            remainingCount -= addFromParent.length;
        }
    }
    return outNodes;
}


export function getLevelVisuals(visInfo: TreeInfo, svgHeight: number, expandedControlInd: number | undefined): LevelVisual {
    const out = [];
    const levelCount = Math.max(((visInfo?.meta || []).length || 0) - 1, 1);
    let topOffset = 0;
    const stepSize = (expandedControlInd === undefined) ? svgHeight / levelCount : svgHeight / levelCount / 2;
    for (let i = 0; i < levelCount; i++) {
        const totalSize = (expandedControlInd == i) ? svgHeight / 2 + stepSize : stepSize
        out.push({ totalSize, topOffset });
        topOffset += totalSize;
    }
    return out;
}

export function insertKeepingOrder<T>(elem: T, arr: T[], f: (l: T, r: T) => number) {
    //0 if equal, -x if l is 'less desirable' 
    let left = 0;
    let right = arr.length - 1;
    let mid: number;
    let compRes: number

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


export function getNodeByPath<S, T extends TreeGen<S>>(
    path: PathInTree,
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

export function isPathInTree(path: PathInTree, root: BareNode): boolean {
    return getNodeByPath(path, root) != undefined
}

export function getSomePath(tree: BareNode): PathInTree {
    const path: PathInTree = [];
    for (const [k, v] of Object.entries(tree.children || {})) {
        return [k, ...getSomePath(v)]
    }
    return path;
}

export function getChildName(path: PathInTree, attributeLabels: AttributeLabels, qcSpec: QcSpec) {
    if (attributeLabels === undefined) {
        return 'Loading...';
    }
    const childId = lastE(path);
    const attKind = getEntityKind(path, qcSpec);
    return attributeLabels[attKind][childId]?.name || 'Unknown';
}

export function getEntityKind(path: PathInTree, qcSpec: QcSpec) {
    return qcSpec.bifurcations[path.length - 1].attribute_kind
}

export const treePathToStr = (path: PathInTree) => (path.join('x'))
export const pathStrToPath = (pathStr: string) => (pathStr.split('x'))

function lastE<T>(arr: T[]): T {
    return arr[arr.length - 1]
}
