import { browser } from '$app/environment';
import { writable } from 'svelte/store';
import type { OaPaperResp } from '$lib/tree-types';
import { fetchOaJson, oaWorkToPaperResp, type OaWorkJson } from '$lib/utils/paper-helpers';

export const resultsHidden = writable(true);

const LS_KEY = 'rankless:papers';
const MAX_CACHE = 300;

type PaperCallback = (paper?: OaPaperResp) => void;

const paperCache = new Map<number, OaPaperResp>();
const fetchingSet = new Set<number>();
const pendingCallbacks = new Map<number, PaperCallback[]>();

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

// Every waiter is settled exactly once, with the paper or with nothing — a failed load has to
// reach the callers, or their placeholders stay up for the life of the page.
function settle(workId: number, paper?: OaPaperResp) {
	pendingCallbacks.get(workId)?.forEach((cb) => cb(paper));
	pendingCallbacks.delete(workId);
}

export function prefetchPaper(workId: number, onDone?: PaperCallback) {
	if (!browser || workId === 0) {
		onDone?.();
		return;
	}
	const cached = paperCache.get(workId);
	if (cached) {
		onDone?.(cached);
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
	fetchOaJson<OaWorkJson>(oaUrl)
		.then((o) => {
			const paper = oaWorkToPaperResp(o);
			paperCache.set(workId, paper);
			persistCache();
			settle(workId, paper);
		})
		.catch(() => settle(workId))
		.finally(() => fetchingSet.delete(workId));
}
