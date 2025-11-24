export type CitationStyle = 'apa' | 'mla' | 'chicago';

export interface PaperBiblio {
	volume?: string;
	issue?: string;
	first_page?: string;
	last_page?: string;
}

export interface Paper {
	year: number;
	name: string;
	doi?: string;
	citations: number;
	source: number;
	authors: string[]; // array of author IDs
	biblio: PaperBiblio;
}

export interface SourcesMap {
	[id: number]: { name: string; specBaseline?: number };
}

export interface AuthorMap {
	[id: string]: string; // id -> full name (e.g. "Ágnes Lőrincz")
}

/**
 * Turn a full name string into { last, givenParts[] }.
 * - If name contains comma ("Last, First Middle") assume it's "Last, First".
 * - Otherwise assume last token is last name, rest are given names.
 */
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

/** Format initials from given name parts: ["Anna", "Maria"] -> "A. M." */
function initialsFromGiven(given: string[]): string {
	return given.map((g) => (g ? g[0].toUpperCase() + '.' : '')).join(' ');
}

/**
 * Format author names list according to style rules.
 * - APA: "Last, F. M., Last2, F. M., & LastN, F. M." (if > 7 -> first 6, ... et al. per strict APA; here use 5+ -> et al.)
 * - MLA: "Last, First Middle, Second Last, First Middle, et al." (MLA often lists up to 3 authors; here we'll show up to 3 then et al.)
 * - Chicago (author-date, simplified): "Last, First M., SecondFirst Last, & ThirdFirst Last"
 *
 * You can tweak the thresholds in this function.
 */
export function formatAuthors(authorIds: string[], authorMap: AuthorMap, style: CitationStyle): string {
	const names = authorIds.map((id) => authorMap[id] || id || 'Unknown Author').map((n) => n.trim());
	const parsed = names.map(splitName);

	// helper builders
	const apaName = (p: { last: string; given: string[] }) =>
		p.given.length ? `${p.last}, ${initialsFromGiven(p.given)}` : p.last;

	const mlaName = (p: { last: string; given: string[] }, originalFull: string) =>
		// MLA typically uses full given names for the first author
		p.given.length ? `${p.last}, ${p.given.join(' ')}` : originalFull;

	const chicagoName = (p: { last: string; given: string[] }, originalFull: string) =>
		// Chicago often prints "Last, First M." for first author, others "First M. Last"
		p.given.length ? `${p.last}, ${p.given.join(' ')}` : originalFull;

	// Decide thresholds
	if (style === 'apa') {
		// simplified: if <= 5 show all, if >5 show first 5 + ", et al."
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
		// MLA: if 1 author -> "Last, First"; 2 authors -> "FirstAuthorLast, First; SecondFirst Last"; 3+ -> first author + "et al."
		if (parsed.length === 1) {
			return mlaName(parsed[0], names[0]);
		}
		if (parsed.length === 2) {
			// "Last1, First1 and First2 Last2" — but MLA older variations exist; we'll return "Last1, First1 and First2 Last2"
			const first = mlaName(parsed[0], names[0]);
			const second = `${parsed[1].given.join(' ')} ${parsed[1].last}`.trim();
			return `${first} and ${second}`;
		}
		if (parsed.length === 3) {
			// all three full
			const list = parsed.map((p, i) => (i === 0 ? mlaName(p, names[i]) : `${p.given.join(' ')} ${p.last}`.trim()));
			return `${list[0]}, ${list[1]}, and ${list[2]}`;
		}
		// 4 or more
		return `${mlaName(parsed[0], names[0])}, et al.`;
	}

	// chicago (default)
	if (parsed.length === 1) return chicagoName(parsed[0], names[0]);
	if (parsed.length === 2) {
		const a = chicagoName(parsed[0], names[0]);
		const b = `${parsed[1].given.join(' ')} ${parsed[1].last}`.trim();
		return `${a} & ${b}`;
	}
	// 3+ authors -> "A, B, & C" with initials for subsequent:
	if (parsed.length <= 5) {
		const list = parsed.map((p, i) => (i === 0 ? chicagoName(p, names[i]) : `${p.given.join(' ')} ${p.last}`.trim()));
		const last = list.pop();
		return `${list.join(', ')}, & ${last}`;
	}
	// more than 5 -> first 3 then et al.
	const firstThree = parsed.slice(0, 3).map((p, i) => (i === 0 ? chicagoName(p, names[i]) : `${p.given.join(' ')} ${p.last}`.trim()));
	return `${firstThree.join(', ')}, et al.`;
}

/** Utility for pages formatting */
function pagesText(b: PaperBiblio): string {
	if (!b) return '';
	const { first_page, last_page } = b;
	if (first_page && last_page) return `${first_page}–${last_page}`;
	if (first_page) return first_page;
	if (last_page) return last_page;
	return '';
}

/**
 * Format a reference string for a single paper according to style.
 * Includes journal/container name, volume(issue), pages, and DOI optionally.
 */
export function formatReference(
	paper: Paper,
	authors: AuthorMap,
	sources: SourcesMap,
	style: CitationStyle = 'chicago',
	includeDoi = true
): string {
	const authorStr = formatAuthors(paper.authors, authors, style);
	const container = sources[paper.source]?.name || 'Unknown Source';
	const vol = paper.biblio?.volume ?? '';
	const issue = paper.biblio?.issue ?? '';
	const pagest = pagesText(paper.biblio);
	const doiPart = includeDoi && paper.doi ? ` https://doi.org/${paper.doi}` : '';

	switch (style) {
		case 'apa': {
			// "Last, F. M., Last2, F. M., & LastN, F. M. (YEAR). Title. Journal, 12(3), 45–56. https..."
			const volIssue = vol ? `${vol}${issue ? `(${issue})` : ''}` : '';
			const pagesPart = pagest ? `, ${pagest}` : '';
			const title = paper.name;
			return `${authorStr} (${paper.year}). ${title}. ${container}${volIssue ? `, ${volIssue}` : ''}${pagesPart}.${doiPart}`;
		}
		case 'mla': {
			// "Last, First. "Title." Journal vol.issue (YEAR): 45-56. https..."
			const volIssue = vol ? `${vol}${issue ? `.${issue}` : ''}` : '';
			const pagesPart = pagest ? `: ${pagest}` : '';
			const title = paper.name;
			// MLA uses quotes around title and italics for journal - in plain text we'll use *journal*
			return `${authorStr}. "${title}." *${container}*${volIssue ? ` ${volIssue}` : ''} (${paper.year})${pagesPart}.${doiPart}`;
		}
		case 'chicago':
		default: {
			// "Last, First. "Title." Journal 12(3): 45–56. https..."
			const volIssue = vol ? `${vol}` : '';
			const volIssuePart = volIssue ? `${volIssue}${issue ? `(${issue})` : ''}` : '';
			const pagesPart = pagest ? `: ${pagest}` : '';
			const title = paper.name;
			// prefer double quotes for titles in Chicago
			return `${authorStr} (${paper.year}). "${title}." *${container}*${volIssuePart ? ` ${volIssuePart}` : ''}${pagesPart}.${doiPart}`;
		}
	}
}

/** BibTeX utilities */
function escapeBibField(s: string): string {
	return (s ?? '').replace(/[{}]/g, '').trim();
}

export function toBibtex(paper: Paper, authors: AuthorMap, sources: SourcesMap): string {
	const authorList = paper.authors.map((id) => authors[id] || id || 'Unknown Author').join(' and ');
	const journal = sources[paper.source]?.name || 'Unknown Source';
	const pages = pagesText(paper.biblio);
	const key = `${(authors[paper.authors[0]] ?? 'anon').split(/\s+/)[0].toLowerCase()}${paper.year}`;
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

export function toBibtexFile(papers: Paper[], authors: AuthorMap, sources: SourcesMap): string {
	return papers.map((p) => toBibtex(p, authors, sources)).join('\n\n');
}
