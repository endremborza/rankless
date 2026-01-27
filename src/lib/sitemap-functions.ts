import { isAsciiOnly } from "./text-format-util";
import type { RootType, SearchResult } from '$lib/tree-types';
import { BE_URL } from "./constants";

export async function respsFromLinks(links: { url: string, name: RootType }[]): Promise<SearchResult[]> {
	const resps: SearchResult[] = []
	for (let i = 0; i < links.length; i++) {
		await fetch(links[i].url).then((r) =>
			r.json().then((l) => {
				l.forEach(
					(e: SearchResult) => {
						if (isAsciiOnly(e.semanticId)) {
							resps.push({ ...e, rootType: links[i].name });
						}
					})
			})
		);
	}
	return resps
}

export async function getLinks(start: number, end: number): Promise<{ url: string, name: RootType }[]> {
	return fetch(`${BE_URL}/counts`).then((r) =>
		r.json().then((entities) => {
			let out: { url: string; name: RootType }[] = [];
			entities.forEach((e: { count: number; name: string }) => {
				if (e.count > start && e.name != 'hit-papers') {
					let url = `${BE_URL}/slice/${e.name}/${start}/${end}`;
					out.push({ url, name: e.name as RootType });
				}
			});
			return out;
		})
	);
}

export async function getMaxPage(stepSize): Promise<number> {
	return fetch(`${BE_URL}/counts`).then((r) =>
		r.json().then((entities) => {
			let max = 0;
			entities.forEach((e: { count: number; name: string }) => {
				let maxPage = Math.floor(e.count / stepSize);
				if (maxPage > max) {
					max = maxPage;
				}
			});
			return max;
		})
	);
}
