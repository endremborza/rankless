import type { Paper, EntityAttsForLinks, AuthorMeta } from '$lib/tree-types';
import { PRESTIGIOUS_SOURCE_SEM_IDS } from '$lib/utils/paper-helpers';

export type ImpactSummary = {
	nobelCount: number;
	prestigiousCount: number;
	standoutCount: number;
};

export function computeImpactSummary(
	impactedWids: number[],
	paperMap: Record<number, Paper>,
	entityAtts: EntityAttsForLinks,
	authorsMeta: Record<string, AuthorMeta>
): ImpactSummary {
	let nobelCount = 0;
	let prestigiousCount = 0;
	let standoutCount = 0;

	for (const wid of impactedWids) {
		const paper = paperMap[wid];
		if (!paper) continue;

		if (paper.isHit) standoutCount++;

		const sourceAtt = entityAtts.sources?.[String(paper.source)];
		if (sourceAtt?.semantic_id && PRESTIGIOUS_SOURCE_SEM_IDS.has(sourceAtt.semantic_id)) {
			prestigiousCount++;
		}

		for (const ship of paper.authorships) {
			if (ship.author[0] !== 'F') continue;
			const dmId = ship.author.slice(1);
			if ((authorsMeta[dmId]?.prize ?? 0) > 0) {
				nobelCount++;
				break;
			}
		}
	}

	return { nobelCount, prestigiousCount, standoutCount };
}
