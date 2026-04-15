import { browser } from '$app/environment';
import { writable } from 'svelte/store';
import type { OaPaperResp } from '$lib/tree-types';
import { reconstructAbstractFromInvIndex } from '$lib/utils/paper-helpers';

export const resultsHidden = writable(true);

const LS_KEY = 'rankless:papers';
const MAX_CACHE = 300;

const paperCache = new Map<number, OaPaperResp>();
const fetchingSet = new Set<number>();
const pendingCallbacks = new Map<number, Array<() => void>>();

if (browser) {
	try {
		const raw = localStorage.getItem(LS_KEY);
		if (raw) {
			const entries = JSON.parse(raw) as [number, OaPaperResp][];
			for (const [k, v] of entries) paperCache.set(k, v);
		}
	} catch {
		// corrupted storage — start fresh
	}
}

function persistCache() {
	try {
		let entries = [...paperCache.entries()];
		if (entries.length > MAX_CACHE) entries = entries.slice(-MAX_CACHE);
		localStorage.setItem(LS_KEY, JSON.stringify(entries));
	} catch {
		// quota exceeded — ignore
	}
}

export function getCachedPaper(id: number) {
	return paperCache.get(id);
}

export function prefetchPaper(workId: number, onDone?: () => void) {
	if (!browser || workId === 0) return;
	if (paperCache.has(workId)) {
		onDone?.();
		return;
	}
	if (onDone) {
		const cbs = pendingCallbacks.get(workId) ?? [];
		cbs.push(onDone);
		pendingCallbacks.set(workId, cbs);
	}
	if (fetchingSet.has(workId)) return;
	fetchingSet.add(workId);
	const oaUrl = `https://api.openalex.org/works/W${workId}?select=publication_year,title,doi,authorships,abstract_inverted_index`;
	fetch(oaUrl)
		.then((r) => r.json())
		.then((o) => {
			// eslint-disable-next-line @typescript-eslint/no-explicit-any
			const authors = o.authorships.map((aship: any) => {
				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				const institutions = (aship.institutions || []).map((aff: any) => aff.id);
				const lElems = aship.author.id.split('/');
				const link = `/oa-id/${lElems[lElems.length - 1]}`;
				return { name: aship.author.display_name, link, institutions };
			});
			paperCache.set(workId, {
				title: o.title,
				doi: o.doi || '',
				year: o.publication_year,
				abstract: reconstructAbstractFromInvIndex(o.abstract_inverted_index) ?? '',
				authors
			});
			if (browser) persistCache();
			pendingCallbacks.get(workId)?.forEach((cb) => cb());
			pendingCallbacks.delete(workId);
		})
		.catch(() => pendingCallbacks.delete(workId))
		.finally(() => fetchingSet.delete(workId));
}
