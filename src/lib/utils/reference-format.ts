import type { Paper, PaperAuthorship, EntityAttsForLinks } from '$lib/tree-types';
import { resolveAuthorName } from '$lib/utils/paper-helpers';

export type CitationStyle = 'apa' | 'mla' | 'chicago';
export type { Paper };

export interface SourcesMap {
	[id: string]: { name: string; spec_baseline?: number };
}

export interface AuthorMap {
	[id: string]: string;
}

function buildAuthorNames(
	authorships: PaperAuthorship[],
	entityAtts: EntityAttsForLinks,
	discAuthorNames: Record<string, string>
): string[] {
	return authorships.map((s) => resolveAuthorName(s, entityAtts, discAuthorNames));
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

export function formatAuthorNames(names: string[], style: CitationStyle): string {
	const parsed = names.map(splitName);

	const apaName = (p: { last: string; given: string[] }) =>
		p.given.length ? `${p.last}, ${initialsFromGiven(p.given)}` : p.last;

	const mlaName = (p: { last: string; given: string[] }, originalFull: string) =>
		p.given.length ? `${p.last}, ${p.given.join(' ')}` : originalFull;

	const chicagoName = (p: { last: string; given: string[] }, originalFull: string) =>
		p.given.length ? `${p.last}, ${p.given.join(' ')}` : originalFull;

	if (style === 'apa') {
		if (parsed.length <= 5) {
			return parsed.map(apaName).reduce((acc, cur, idx) => {
				if (idx === 0) return cur;
				if (idx === parsed.length - 1) return `${acc}, & ${cur}`;
				return `${acc}, ${cur}`;
			}, '');
		} else {
			const first = parsed.slice(0, 5).map(apaName).join(', ');
			return `${first}, et al.`;
		}
	}

	if (style === 'mla') {
		if (parsed.length === 1) return mlaName(parsed[0], names[0]);
		if (parsed.length === 2) {
			const first = mlaName(parsed[0], names[0]);
			const second = `${parsed[1].given.join(' ')} ${parsed[1].last}`.trim();
			return `${first} and ${second}`;
		}
		if (parsed.length === 3) {
			const list = parsed.map((p, i) => (i === 0 ? mlaName(p, names[i]) : `${p.given.join(' ')} ${p.last}`.trim()));
			return `${list[0]}, ${list[1]}, and ${list[2]}`;
		}
		return `${mlaName(parsed[0], names[0])}, et al.`;
	}

	if (parsed.length === 1) return chicagoName(parsed[0], names[0]);
	if (parsed.length === 2) {
		const a = chicagoName(parsed[0], names[0]);
		const b = `${parsed[1].given.join(' ')} ${parsed[1].last}`.trim();
		return `${a} & ${b}`;
	}
	if (parsed.length <= 5) {
		const list = parsed.map((p, i) => (i === 0 ? chicagoName(p, names[i]) : `${p.given.join(' ')} ${p.last}`.trim()));
		const last = list.pop();
		return `${list.join(', ')}, & ${last}`;
	}
	const firstThree = parsed.slice(0, 3).map((p, i) => (i === 0 ? chicagoName(p, names[i]) : `${p.given.join(' ')} ${p.last}`.trim()));
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
	style: CitationStyle = 'chicago',
	includeDoi = true
): string {
	const names = buildAuthorNames(paper.authorships, entityAtts, discAuthorNames);
	const authorStr = formatAuthorNames(names, style);
	const container = entityAtts.sources?.[String(paper.source)]?.name || 'Unknown Source';
	const vol = paper.biblio?.volume ?? '';
	const issue = paper.biblio?.issue ?? '';
	const pagest = pagesText(paper.biblio);
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

export function toBibtex(
	paper: Paper,
	entityAtts: EntityAttsForLinks,
	discAuthorNames: Record<string, string>
): string {
	const names = buildAuthorNames(paper.authorships, entityAtts, discAuthorNames);
	const authorList = names.join(' and ');
	const journal = entityAtts.sources?.[String(paper.source)]?.name || 'Unknown Source';
	const pages = pagesText(paper.biblio);
	const key = `${(names[0] ?? 'anon').split(/\s+/)[0].toLowerCase()}${paper.year}`;
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
	return papers.map((p) => toBibtex(p, entityAtts, discAuthorNames)).join('\n\n');
}
