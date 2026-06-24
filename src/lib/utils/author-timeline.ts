import type { Paper, EntityAttsForLinks } from '$lib/tree-types';
import { resolveAuthorNameOrNull } from '$lib/utils/paper-helpers';

export type SortMode = 'first' | 'recent' | 'count';

// One marker on a co-author's row: every paper they share with the hero in a given year.
export type YearGroup = { year: number; papers: Paper[]; hasHit: boolean };

export type CoAuthor = {
	key: string; // the authorship id ("F{id}" / "D{id}") — stable identity across papers
	name: string;
	url: string | null; // profile link for filtered (F) authors; null for discarded (D) ones
	count: number;
	hitCount: number;
	firstYear: number;
	lastYear: number;
	groups: YearGroup[]; // ascending by year
};

export type YearDomain = { lo: number; hi: number; span: number };

const NICE_STEPS = [1, 2, 5, 10, 20, 25, 50];

// Aggregate every named co-author across the hero's loaded works. The hero is dropped, papers
// without a usable year are skipped, and discarded (D) authors are kept (name only, no link) so
// recent or minor collaborators missing from the top-N network still surface here.
export function buildCoauthors(
	papers: Paper[],
	entityAtts: EntityAttsForLinks,
	discAuthorNames: Record<string, string>,
	heroSemanticId: string
): CoAuthor[] {
	const map = new Map<string, { name: string; url: string | null; byYear: Map<number, Paper[]> }>();

	for (const p of papers) {
		if (!p.year || p.year <= 0) continue;
		for (const ship of p.authorships) {
			let url: string | null = null;
			if (ship.author[0] === 'F') {
				const att = entityAtts.authors?.[ship.author.slice(1)];
				if (att?.semantic_id === heroSemanticId) continue; // the hero links everyone — leave out
				if (att?.semantic_id) url = `/authors/${att.semantic_id}`;
			}
			const name = resolveAuthorNameOrNull(ship, entityAtts, discAuthorNames);
			if (name === null) continue;

			let entry = map.get(ship.author);
			if (!entry) {
				entry = { name, url, byYear: new Map() };
				map.set(ship.author, entry);
			}
			entry.name = name; // later pages may resolve a name/link the first occurrence lacked
			entry.url = url;
			const bucket = entry.byYear.get(p.year);
			if (bucket) bucket.push(p);
			else entry.byYear.set(p.year, [p]);
		}
	}

	const out: CoAuthor[] = [];
	for (const [key, e] of map) {
		const years = [...e.byYear.keys()].sort((a, b) => a - b);
		let count = 0;
		let hitCount = 0;
		const groups = years.map((year) => {
			const ps = e.byYear.get(year)!;
			const hits = ps.filter((p) => p.isHit).length;
			count += ps.length;
			hitCount += hits;
			return { year, papers: ps, hasHit: hits > 0 };
		});
		out.push({
			key,
			name: e.name,
			url: e.url,
			count,
			hitCount,
			firstYear: years[0],
			lastYear: years[years.length - 1],
			groups
		});
	}
	return out;
}

export function sortCoauthors(list: CoAuthor[], mode: SortMode): CoAuthor[] {
	const arr = [...list];
	if (mode === 'count') arr.sort((a, b) => b.count - a.count || a.firstYear - b.firstYear);
	else if (mode === 'recent') arr.sort((a, b) => b.lastYear - a.lastYear || b.count - a.count);
	else arr.sort((a, b) => a.firstYear - b.firstYear || b.count - a.count);
	return arr;
}

export function yearDomain(papers: Paper[]): YearDomain {
	let lo = Infinity;
	let hi = -Infinity;
	for (const p of papers) {
		if (!p.year || p.year <= 0) continue;
		if (p.year < lo) lo = p.year;
		if (p.year > hi) hi = p.year;
	}
	if (!Number.isFinite(lo)) return { lo: 0, hi: 0, span: 1 };
	return { lo, hi, span: Math.max(1, hi - lo) };
}

function niceStep(raw: number): number {
	for (const s of NICE_STEPS) if (s >= raw) return s;
	return Math.ceil(raw / 50) * 50;
}

// Round year ticks at a human-friendly interval, fitting roughly `target` labels across the span.
export function makeTicks(domain: YearDomain, target: number): number[] {
	if (domain.hi <= domain.lo) return domain.lo > 0 ? [domain.lo] : [];
	const step = niceStep(domain.span / Math.max(1, target));
	const out: number[] = [];
	for (let y = Math.ceil(domain.lo / step) * step; y <= domain.hi; y += step) out.push(y);
	return out;
}
