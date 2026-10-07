import type { AttributeLabelOut } from './wire/rankless_trees/io';
import type { ResponseNode, OMap } from './tree-types';
export type SpecInfo = { nodeRate: number; baselineRate: number; specMetric: number };

export function getSpecMetricObject(
	node: ResponseNode,
	nodeDivisor: number,
	attributeLabels: OMap<AttributeLabelOut> | undefined,
	childId: number
): SpecInfo {
	const nodeRate = (node?.linkCount || 0) / nodeDivisor;
	const baselineRate = attributeLabels?.[childId]?.specBaseline || nodeRate * 0.5;
	const specMetric = nodeRate / baselineRate;
	return { nodeRate, baselineRate, specMetric };
}
