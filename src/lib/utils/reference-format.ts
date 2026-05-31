import type { Paper, PaperAuthorship, EntityAttsForLinks } from '$lib/tree-types';
import { resolveAuthorNameOrNull } from '$lib/utils/paper-helpers';

export type CitationStyle = 'html' | 'apa' | 'mla' | 'chicago';
export type { Paper };

export interface SourcesMap {
	[id: string]: { name: string; spec_baseline?: number };
}

export interface AuthorMap {
	[id: string]: string;
}

function buildKnownAuthorNames(
	authorships: PaperAuthorship[],
	entityAtts: EntityAttsForLinks,
	discAuthorNames: Record<string, string>
): string[] {
	return authorships
		.map((s) => resolveAuthorNameOrNull(s, entityAtts, discAuthorNames))
		.filter((n): n is string => n !== null);
}

function splitName(full: string): { last: string; given: string[] } {
	if (!full) return { last: 'Unknown', given: [] };
	const s = full.trim();
	if (s.includes(',')) {
		const [lastPart, givenPart] = s.split(',', 2);
		const last = lastPart.trim();
		const given = givenPart ? givenPart.trim().split(/\s+/) : [];
		return { last, given };
	}
	const parts = s.split(/\s+/);
	if (parts.length === 1) return { last: parts[0], given: [] };
	const last = parts[parts.length - 1];
	const given = parts.slice(0, parts.length - 1);
	return { last, given };
}

function initialsFromGiven(given: string[]): string {
	return given.map((g) => (g ? g[0].toUpperCase() + '.' : '')).join(' ');
}

export function formatAuthorNames(
	names: string[],
	style: CitationStyle,
	forceEtAl = false
): string {
	const parsed = names.map(splitName);

	const apaName = (p: { last: string; given: string[] }) =>
		p.given.length ? `${p.last}, ${initialsFromGiven(p.given)}` : p.last;

	const mlaName = (p: { last: string; given: string[] }, originalFull: string) =>
		p.given.length ? `${p.last}, ${p.given.join(' ')}` : originalFull;

	const chicagoName = (p: { last: string; given: string[] }, originalFull: string) =>
		p.given.length ? `${p.last}, ${p.given.join(' ')}` : originalFull;

	if (style === 'apa') {
		if (parsed.length > 5) {
			return `${parsed.slice(0, 5).map(apaName).join(', ')}, et al.`;
		}
		const base = parsed.map(apaName).reduce((acc, cur, idx) => {
			if (idx === 0) return cur;
			if (idx === parsed.length - 1) return `${acc}, & ${cur}`;
			return `${acc}, ${cur}`;
		}, '');
		return forceEtAl ? `${base}, et al.` : base;
	}

	if (style === 'mla') {
		if (parsed.length > 3) return `${mlaName(parsed[0], names[0])}, et al.`;
		if (forceEtAl) return `${mlaName(parsed[0], names[0])}, et al.`;
		if (parsed.length === 1) return mlaName(parsed[0], names[0]);
		if (parsed.length === 2) {
			const first = mlaName(parsed[0], names[0]);
			const second = `${parsed[1].given.join(' ')} ${parsed[1].last}`.trim();
			return `${first} and ${second}`;
		}
		const list = parsed.map((p, i) =>
			i === 0 ? mlaName(p, names[i]) : `${p.given.join(' ')} ${p.last}`.trim()
		);
		return `${list[0]}, ${list[1]}, and ${list[2]}`;
	}

	// chicago
	if (parsed.length === 1) {
		const base = chicagoName(parsed[0], names[0]);
		return forceEtAl ? `${base}, et al.` : base;
	}
	if (parsed.length === 2) {
		if (forceEtAl) return `${chicagoName(parsed[0], names[0])}, et al.`;
		const a = chicagoName(parsed[0], names[0]);
		const b = `${parsed[1].given.join(' ')} ${parsed[1].last}`.trim();
		return `${a} & ${b}`;
	}
	if (parsed.length <= 5) {
		if (forceEtAl) return `${chicagoName(parsed[0], names[0])}, et al.`;
		const list = parsed.map((p, i) =>
			i === 0 ? chicagoName(p, names[i]) : `${p.given.join(' ')} ${p.last}`.trim()
		);
		const last = list.pop();
		return `${list.join(', ')}, & ${last}`;
	}
	const firstThree = parsed
		.slice(0, 3)
		.map((p, i) => (i === 0 ? chicagoName(p, names[i]) : `${p.given.join(' ')} ${p.last}`.trim()));
	return `${firstThree.join(', ')}, et al.`;
}

function pagesText(b: Paper['biblio']): string {
	if (!b) return '';
	const { first_page, last_page } = b;
	if (first_page && last_page) return `${first_page}–${last_page}`;
	if (first_page) return first_page;
	if (last_page) return last_page;
	return '';
}

export function formatReference(
	paper: Paper,
	entityAtts: EntityAttsForLinks,
	discAuthorNames: Record<string, string>,
	style: CitationStyle = 'html',
	includeDoi = true
): string {
	const knownNames = buildKnownAuthorNames(paper.authorships, entityAtts, discAuthorNames);
	const hasMore = knownNames.length < paper.authorships.length;
	const authorStr = knownNames.length
		? formatAuthorNames(knownNames, style === 'html' ? 'chicago' : style, hasMore)
		: '';
	const container = entityAtts.sources?.[String(paper.source)]?.name || '';
	const vol = paper.biblio?.volume ?? '';
	const issue = paper.biblio?.issue ?? '';
	const pagest = pagesText(paper.biblio);

	if (style === 'html') {
		const titleHtml = paper.doi
			? `<a href="https://doi.org/${paper.doi}" target="_blank" rel="noopener">${paper.name}</a>`
			: paper.name;
		const parts = [authorStr, `(${paper.year})`, titleHtml];
		if (container) parts.push(`<em>${container}</em>`);
		if (vol) parts.push(issue ? `${vol}(${issue})` : vol);
		if (pagest) parts.push(pagest);
		return parts.filter(Boolean).join('. ') + '.';
	}

	const doiPart = includeDoi && paper.doi ? ` https://doi.org/${paper.doi}` : '';

	switch (style) {
		case 'apa': {
			const volIssue = vol ? `${vol}${issue ? `(${issue})` : ''}` : '';
			const pagesPart = pagest ? `, ${pagest}` : '';
			return `${authorStr} (${paper.year}). ${paper.name}. ${container}${volIssue ? `, ${volIssue}` : ''}${pagesPart}.${doiPart}`;
		}
		case 'mla': {
			const volIssue = vol ? `${vol}${issue ? `.${issue}` : ''}` : '';
			const pagesPart = pagest ? `: ${pagest}` : '';
			return `${authorStr}. "${paper.name}." *${container}*${volIssue ? ` ${volIssue}` : ''} (${paper.year})${pagesPart}.${doiPart}`;
		}
		case 'chicago':
		default: {
			const volIssue = vol ? `${vol}` : '';
			const volIssuePart = volIssue ? `${volIssue}${issue ? `(${issue})` : ''}` : '';
			const pagesPart = pagest ? `: ${pagest}` : '';
			return `${authorStr} (${paper.year}). "${paper.name}." *${container}*${volIssuePart ? ` ${volIssuePart}` : ''}${pagesPart}.${doiPart}`;
		}
	}
}

function escapeBibField(s: string): string {
	return (s ?? '').replace(/[{}]/g, '').trim();
}

export function bibtexKey(names: string[], year: number): string {
	const first = names.length ? names[0].split(/\s+/)[0].toLowerCase() : 'anon';
	return `${first}${year}`;
}

function nextSuffix(s: string): string {
	if (!s) return 'a';
	const last = s[s.length - 1];
	if (last < 'z') return s.slice(0, -1) + String.fromCharCode(last.charCodeAt(0) + 1);
	return s + 'a';
}

export function toBibtexEntry(
	paper: Paper,
	entityAtts: EntityAttsForLinks,
	discAuthorNames: Record<string, string>,
	key: string
): string {
	const names = buildKnownAuthorNames(paper.authorships, entityAtts, discAuthorNames);
	const authorList = names.join(' and ');
	const journal = entityAtts.sources?.[String(paper.source)]?.name ?? '';
	const pages = pagesText(paper.biblio);
	return `@article{${key},
  author = {${escapeBibField(authorList)}},
  title = {${escapeBibField(paper.name)}},
  journal = {${escapeBibField(journal)}},
  year = {${paper.year}},
  volume = {${escapeBibField(paper.biblio?.volume ?? '')}},
  number = {${escapeBibField(paper.biblio?.issue ?? '')}},
  pages = {${escapeBibField(pages)}},
  doi = {${escapeBibField(paper.doi ?? '')}}
}`;
}

export function toBibtexFile(
	papers: Paper[],
	entityAtts: EntityAttsForLinks,
	discAuthorNames: Record<string, string>
): string {
	const baseCounts = new Map<string, number>();
	for (const p of papers) {
		const names = buildKnownAuthorNames(p.authorships, entityAtts, discAuthorNames);
		const base = bibtexKey(names, p.year);
		baseCounts.set(base, (baseCounts.get(base) ?? 0) + 1);
	}
	const usedSuffix = new Map<string, string>();
	return papers
		.map((p) => {
			const names = buildKnownAuthorNames(p.authorships, entityAtts, discAuthorNames);
			const base = bibtexKey(names, p.year);
			let key = base;
			if ((baseCounts.get(base) ?? 0) > 1) {
				const prev = usedSuffix.get(base) ?? '';
				const suffix = prev ? nextSuffix(prev) : 'a';
				usedSuffix.set(base, suffix);
				key = base + suffix;
			}
			return toBibtexEntry(p, entityAtts, discAuthorNames, key);
		})
		.join('\n\n');
}
