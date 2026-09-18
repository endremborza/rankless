import { isAsciiOnly } from './text-format-util';
import type { RootType, SearchResult, SliceResp, TableRow } from '$lib/tree-types';
import { BE_URL } from './constants';

// The rows of one `/slice` page that can carry a sitemap URL: a semantic id outside ASCII has no
// place in one.
export async function sitemapRows(url: string): Promise<TableRow[]> {
	const { rows }: SliceResp = await fetch(url).then((r) => r.json());
	return rows.filter((e) => isAsciiOnly(e.semanticId));
}

export async function respsFromLinks(
	links: { url: string; name: RootType }[]
): Promise<SearchResult[]> {
	const resps: SearchResult[] = [];
	for (const link of links) {
		for (const e of await sitemapRows(link.url)) {
			resps.push({ ...e, rootType: link.name });
		}
	}
	return resps;
}

export async function getLinks(
	start: number,
	end: number
): Promise<{ url: string; name: RootType }[]> {
	return fetch(`${BE_URL}/counts`)
		.then((r) =>
			r.json().then((entities) => {
				if (!Array.isArray(entities)) return [];
				const out: { url: string; name: RootType }[] = [];
				entities.forEach((e: { count: number; name: string }) => {
					if (e.count > start && e.name != 'hit-papers') {
						const url = `${BE_URL}/slice/${e.name}/${start}/${end}`;
						out.push({ url, name: e.name as RootType });
					}
				});
				return out;
			})
		)
		.catch(() => []);
}

export async function getMaxPage(stepSize: number): Promise<number> {
	return fetch(`${BE_URL}/counts`)
		.then((r) =>
			r.json().then((entities) => {
				if (!Array.isArray(entities)) return 0;
				let max = 0;
				entities.forEach((e: { count: number; name: string }) => {
					const maxPage = Math.floor(e.count / stepSize);
					if (maxPage > max) {
						max = maxPage;
					}
				});
				return max;
			})
		)
		.catch(() => 0);
}
