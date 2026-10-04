import type { Paper, EntityAttsForLinks, AuthorMeta } from '$lib/tree-types';
import { hasNobelCoauthor, PRESTIGIOUS_SOURCE_SEM_IDS } from '$lib/utils/paper-helpers';

export type ImpactSummary = {
	nobelCount: number;
	prestigiousCount: number;
	hitCount: number;
};

export function computeImpactSummary(
	impactedWids: number[],
	paperMap: Record<number, Paper>,
	entityAtts: EntityAttsForLinks,
	authorsMeta: Record<string, AuthorMeta>
): ImpactSummary {
	let nobelCount = 0;
	let prestigiousCount = 0;
	let hitCount = 0;

	for (const wid of impactedWids) {
		const paper = paperMap[wid];
		if (!paper) continue;

		if (paper.isHit) hitCount++;

		const sourceAtt = entityAtts.sources?.[String(paper.source)];
		if (sourceAtt?.semantic_id && PRESTIGIOUS_SOURCE_SEM_IDS.has(sourceAtt.semantic_id)) {
			prestigiousCount++;
		}

		if (hasNobelCoauthor(paper, authorsMeta)) nobelCount++;
	}

	return { nobelCount, prestigiousCount, hitCount };
}

export function nobelPhrase(count: number): string {
	return `${count} by Nobel laureates`;
}

export function prestigiousPhrase(count: number): string {
	return `${count} from Science/Nature`;
}
