import type { ResponseNode, OMap, AttributeLabel } from './tree-types';
export type SpecInfo = { nodeRate: number; baselineRate: number; specMetric: number };

export const ALPHA = 0.1;

export function getSpecMetricObject(
	node: ResponseNode,
	nodeDivisor: number,
	attributeLabels: OMap<AttributeLabel> | undefined,
	childId: number
): SpecInfo {
	const nodeRate = (node?.linkCount || 0) / nodeDivisor;
	const baselineRate: number =
		attributeLabels === undefined
			? nodeRate * 0.5
			: attributeLabels[childId]?.specBaseline || nodeRate * 0.5;
	const specMetric = nodeRate / baselineRate;
	return { nodeRate, baselineRate, specMetric };
}
