import type { EntityType } from './constants';
import { getEntityKind, getNodeByPath } from './tree-functions';

import type { QcSpec, SpecializationBasis, PathInTree, AttributeLabels, WeightedNode, SpecBaseOptions } from './tree-types'

export const IGNORED_BASES = [ // too large files...
    'i-Institution-Country-Global',
    'i-Concept-Continent-Institution',
    'i-Institution-Country-Country',
    'i-Concept-Country-Institution'
]

export const DEFAULT_SPEC_BASES: Record<EntityType, SpecializationBasis> = {
    Institution: { basis: 'Global', hierarchy: 'Global' },
    Concept: { basis: 'Global', hierarchy: 'Global' },
    Country: { basis: 'Global', hierarchy: 'Global' },
    SubConcept: { basis: 'Global', hierarchy: 'Global' },
    Continent: { basis: 'Global', hierarchy: 'Global' },
    Period: { basis: 'Global', hierarchy: 'Global' },
    Year: { basis: 'Global', hierarchy: 'Global' },
    InstitutionType: { basis: 'Global', hierarchy: 'Global' }
}

const ID_MAP = {
    Continent: 'continent__id',
    Country: 'country__id'
}

export function getSpecMetricObject(
    weightedRoot: WeightedNode,
    baseKind: SpecializationBasis,
    path: PathInTree,
    rootId: string,
    qcSpec: QcSpec,
    specBaselineOptions: SpecBaseOptions,
    attributeLabels: AttributeLabels
): { nodeDivisor: number, nodeRate: number, baselineRate: number, specMetric: number } {


    const entityKind = getEntityKind(path, qcSpec);
    const node = getNodeByPath(path, weightedRoot);
    const childId = path[path.length - 1]

    const parent = getNodeByPath(path.slice(0, -1), weightedRoot);
    const siblingCount = Object.keys(parent?.children || {}).length;
    const normalizerEps = 1 / siblingCount
    // const nOnLevel = 1; TODO for fallback spec metric

    const rootTypeId = qcSpec.root_entity_type.slice(0, 1).toLowerCase()

    let nodeDivisor = weightedRoot.weight;
    let leafD = specBaselineOptions[specBaseKindToStr(rootTypeId, entityKind, baseKind.basis, baseKind.hierarchy)];
    if (leafD === undefined) {
        console.log("cannot find metric for", rootTypeId)
        const nodeRate = (node?.weight || 0) / nodeDivisor
        return { nodeRate, nodeDivisor, baselineRate: nodeRate, specMetric: 1 }
    }

    if (baseKind.basis != 'Global') {
        const attIdKey: number = attributeLabels[qcSpec.root_entity_type][rootId].meta[ID_MAP[baseKind.basis] || baseKind.basis]
        leafD = leafD[attIdKey]
    }
    if (baseKind.hierarchy != 'Global') {
        for (let i = path.length - 2; i >= 0; i--) {
            if (baseKind.hierarchy == qcSpec.bifurcations[i].attribute_kind) {
                const parentId = path[i]
                const relevantParent = getNodeByPath(path.slice(0, i + 1), weightedRoot)
                leafD = leafD[parentId]
                nodeDivisor = relevantParent?.weight;
                break
            }
        }

    } else {
        for (let i = path.length - 2; i > 0; i--) {
            if (qcSpec.root_entity_type == qcSpec.bifurcations[i].attribute_kind) {
                nodeDivisor = getNodeByPath(path.slice(0, i + 1), weightedRoot)?.weight;
                break
            }
        }

    }

    const baselineRate: number = leafD[childId] || 0
    const nodeRate = (node?.weight || 0) / nodeDivisor


    return {
        nodeRate, nodeDivisor, baselineRate, specMetric: (nodeRate + normalizerEps) / (baselineRate + normalizerEps)
    }
}


export function specBaseKindToStr(rootTypeId: string, target: EntityType, basis: string, hierarchy: string) {
    // TODO this knows a naming scheme that it shouldn't
    return `${rootTypeId}-${target}-${basis}-${hierarchy}`
}

export function specBaseStrToKind(specBaseStr: string): { target: EntityType } & SpecializationBasis {
    const [_, target, basis, hierarchy] = specBaseStr.split('-');
    return { target, basis, hierarchy }
}

// TODO sibling level RCA for some
// TODO normalize metric to show -1 - 1