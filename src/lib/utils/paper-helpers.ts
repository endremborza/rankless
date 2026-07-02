import type { Paper, PaperAuthorship, EntityAttsForLinks } from '$lib/tree-types';
import { fixName } from '$lib/name-overrides';

export const PRESTIGIOUS_SOURCE_SEM_IDS = new Set(['science', 'nature']);

// Minimal entity table for the SSR fallback only; the browser path decodes all entities natively.
const NAMED_ENTITIES: Record<string, string> = {
	amp: '&',
	lt: '<',
	gt: '>',
	quot: '"',
	apos: "'",
	nbsp: ' '
};

function decodeEntities(s: string): string {
	return s.replace(/&(#x?[0-9a-f]+|[a-z]+);/gi, (m, body: string) => {
		if (body[0] !== '#') return NAMED_ENTITIES[body.toLowerCase()] ?? m;
		const code =
			body[1].toLowerCase() === 'x' ? parseInt(body.slice(2), 16) : parseInt(body.slice(1), 10);
		return Number.isFinite(code) ? String.fromCodePoint(code) : m;
	});
}

// HTML-heavy titles (italics, sub/sup, MathML) → readable plain text for SVG/fitted contexts.
// MathML children are inline, so textContent would jam the notation against neighbouring prose:
// turn each <math> container tag into a space first to detach it. The browser then parses the
// rest (decoding all entities); SSR falls back to stripping tags + decoding common entities.
export function htmlToText(html: string): string {
	const spaced = html.replace(/<\/?(?:math|mml:math)\b[^>]*>/gi, ' ');
	let raw: string;
	if (typeof document !== 'undefined') {
		const tpl = document.createElement('template');
		tpl.innerHTML = spaced;
		raw = tpl.content.textContent ?? '';
	} else {
		raw = decodeEntities(spaced.replace(/<[^>]*>/g, ''));
	}
	return raw
		.replace(/\s+/g, ' ')
		.replace(/\s+([:;,.!?)])/g, '$1')
		.trim();
}

export function reconstructAbstractFromInvIndex(
	idx: Record<string, number[]> | null | undefined
): string | null {
	if (!idx) return null;
	const words: string[] = [];
	for (const [word, positions] of Object.entries(idx)) {
		for (const pos of positions) words[pos] = word;
	}
	const result = words.join(' ');
	return result || null;
}

export async function fetchOaAbstract(semanticId: string): Promise<string | null> {
	const url = semanticId.startsWith('W')
		? `https://api.openalex.org/works/${semanticId}?select=abstract_inverted_index`
		: `https://api.openalex.org/works/https://doi.org/${semanticId}?select=abstract_inverted_index`;
	try {
		const d = await fetch(url).then((r) => r.json());
		return reconstructAbstractFromInvIndex(d?.abstract_inverted_index);
	} catch {
		return null;
	}
}

export type PaperHighlight = {
	key: string; // 'authored' | 'hit' | 'prestigious'
	label?: string; // for prestigious: actual source name
};

// Backend sentinel for a discarded author whose OpenAlex display_name is missing.
const DISC_NAME_SENTINEL = 'Unknown';

export function resolveAuthorNameOrNull(
	ship: PaperAuthorship,
	entityAtts: EntityAttsForLinks,
	discAuthorNames: Record<string, string>
): string | null {
	// entityAtts.authors is keyed by the bare dm_id, but discAuthorNames is keyed by the
	// full prefixed id ("D{id}") — each branch must use its own key form.
	let name: string | null;
	if (ship.author[0] === 'F') {
		name = entityAtts.authors?.[ship.author.slice(1)]?.name ?? null;
	} else {
		const disc = discAuthorNames[ship.author];
		name = disc && disc !== DISC_NAME_SENTINEL ? disc : null;
	}
	return name == null ? null : fixName(name);
}

// Combine entity-att maps without clobbering nested per-type records. A shallow spread would
// let a later source's `sources`/`authors`/`institutions` map replace an earlier, richer one.
export function mergeEntityAtts(...parts: (EntityAttsForLinks | undefined)[]): EntityAttsForLinks {
	const out: EntityAttsForLinks = {};
	for (const part of parts) {
		if (!part) continue;
		for (const [etype, recs] of Object.entries(part)) {
			out[etype] = { ...(out[etype] ?? {}), ...recs };
		}
	}
	return out;
}

export function resolveSourceName(sourceId: number, entityAtts: EntityAttsForLinks): string {
	return entityAtts.sources?.[String(sourceId)]?.name ?? '';
}

export function resolveInstName(instId: number, entityAtts: EntityAttsForLinks): string {
	return entityAtts.institutions?.[String(instId)]?.name ?? '';
}

export function overperf(paper: Paper): number {
	if (!paper.hitBm || paper.hitBm < 5) return 0;
	return paper.citations / paper.hitBm;
}

export type Author = {
	name: string;
	url?: string;
	inst?: string;
	instUrl?: string;
};

// Single resolver behind the shared <AuthorList>: maps a paper's authorships to display rows with
// optional profile + institution links. `skipUnknown` drops co-authors whose display name is
// missing (for compact, capped lists); full bibliographic lists keep them as "(unknown)".
export function resolveAuthors(
	paper: Paper,
	entityAtts: EntityAttsForLinks,
	discAuthorNames: Record<string, string>,
	skipUnknown = false
): Author[] {
	const out: Author[] = [];
	for (const ship of paper.authorships) {
		const name = resolveAuthorNameOrNull(ship, entityAtts, discAuthorNames);
		if (name === null && skipUnknown) continue;
		const author: Author = { name: name ?? '(unknown)' };
		if (ship.author[0] === 'F') {
			const semId = entityAtts.authors?.[ship.author.slice(1)]?.semantic_id;
			if (semId) author.url = `/authors/${semId}`;
		}
		const instId = ship.insts[0];
		if (instId != null) {
			const inst = resolveInstName(instId, entityAtts);
			if (inst) {
				author.inst = inst;
				const instSemId = entityAtts.institutions?.[String(instId)]?.semantic_id;
				if (instSemId) author.instUrl = `/institutions/${instSemId}`;
			}
		}
		out.push(author);
	}
	return out;
}

export function buildPaperMap(papers: Paper[]): Record<number, Paper> {
	const map: Record<number, Paper> = {};
	for (const p of papers) map[p.wid] = p;
	return map;
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

export function logMissingAuthors(
	papers: Paper[],
	entityAtts: EntityAttsForLinks,
	discAuthorNames: Record<string, string>
): void {
	const missing = new Set<string>();
	for (const paper of papers) {
		for (const ship of paper.authorships) {
			if (resolveAuthorNameOrNull(ship, entityAtts, discAuthorNames) === null) {
				missing.add(ship.author);
			}
		}
	}
	if (missing.size) console.warn('Missing author IDs:', [...missing]);
}

export function getPaperHighlights(
	paper: Paper,
	sourceAuthorSemId?: string,
	entityAtts?: EntityAttsForLinks
): PaperHighlight[] {
	const hl: PaperHighlight[] = [];
	if (sourceAuthorSemId && entityAtts && isAuthored(paper, sourceAuthorSemId, entityAtts))
		hl.push({ key: 'authored' });
	if (paper.isHit) hl.push({ key: 'hit' });
	if (entityAtts) {
		const sourceAtt = entityAtts.sources?.[String(paper.source)];
		if (sourceAtt?.semantic_id && PRESTIGIOUS_SOURCE_SEM_IDS.has(sourceAtt.semantic_id))
			hl.push({ key: 'prestigious', label: sourceAtt.name });
	}
	return hl;
}
