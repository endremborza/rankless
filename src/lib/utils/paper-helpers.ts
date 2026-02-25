import type { Paper, PaperAuthorship, EntityAttsForLinks } from '$lib/tree-types';

export const PRESTIGIOUS_SOURCE_SEM_IDS = new Set(['science', 'nature']);

export type PaperHighlight = {
	key: string; // 'authored' | 'hit' | 'prestigious'
	label?: string; // for prestigious: actual source name
};

export function resolveAuthorName(
	ship: PaperAuthorship,
	entityAtts: EntityAttsForLinks,
	discAuthorNames: Record<string, string>
): string {
	const prefix = ship.author[0];
	const id = ship.author.slice(1);
	if (prefix === 'F') {
		return entityAtts.authors?.[id]?.name ?? 'Unknown';
	}
	return discAuthorNames[id] ?? `Unknown - disc ${ship.author}`;
}

export function resolveSourceName(
	sourceId: number,
	entityAtts: EntityAttsForLinks
): string {
	return entityAtts.sources?.[String(sourceId)]?.name ?? '';
}

export function resolveInstName(
	instId: number,
	entityAtts: EntityAttsForLinks
): string {
	return entityAtts.institutions?.[String(instId)]?.name ?? '';
}

export function buildPaperMap(papers: Paper[]): Record<number, Paper> {
	const map: Record<number, Paper> = {};
	for (const p of papers) map[p.wid] = p;
	return map;
}

export type ChipAuthor = {
	name: string;
	url?: string;
	inst?: string;
	instUrl?: string;
};

export function getChipAuthors(
	paper: Paper,
	entityAtts: EntityAttsForLinks,
	discAuthorNames: Record<string, string>,
	maxN = 3
): ChipAuthor[] {
	return paper.authorships.slice(0, maxN).map((ship) => {
		const name = resolveAuthorName(ship, entityAtts, discAuthorNames);
		const result: ChipAuthor = { name };
		if (ship.author[0] === 'F') {
			const att = entityAtts.authors?.[ship.author.slice(1)];
			if (att?.semantic_id) result.url = `/authors/${att.semantic_id}`;
		}
		if (ship.insts[0] != null) {
			result.inst = resolveInstName(ship.insts[0], entityAtts);
			const instAtt = entityAtts.institutions?.[String(ship.insts[0])];
			if (instAtt?.semantic_id) result.instUrl = `/institutions/${instAtt.semantic_id}`;
		}
		return result;
	});
}

export function isAuthored(
	paper: Paper,
	authorSemId: string,
	entityAtts: EntityAttsForLinks
): boolean {
	return paper.authorships.some((s) => {
		if (s.author[0] !== 'F') return false;
		return entityAtts.authors?.[s.author.slice(1)]?.semantic_id === authorSemId;
	});
}

export function getPaperHighlights(
	paper: Paper,
	sourceAuthorSemId?: string,
	entityAtts?: EntityAttsForLinks
): PaperHighlight[] {
	const hl: PaperHighlight[] = [];
	if (sourceAuthorSemId && entityAtts && isAuthored(paper, sourceAuthorSemId, entityAtts))
		hl.push({ key: 'authored' });
	if (paper.is_hit) hl.push({ key: 'hit' });
	if (entityAtts) {
		const sourceAtt = entityAtts.sources?.[String(paper.source)];
		if (sourceAtt?.semantic_id && PRESTIGIOUS_SOURCE_SEM_IDS.has(sourceAtt.semantic_id))
			hl.push({ key: 'prestigious', label: sourceAtt.name });
	}
	return hl;
}
