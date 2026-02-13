import { writable } from 'svelte/store';
import type { OaPaperResp } from '$lib/tree-types';

export const resultsHidden = writable(true);

const paperCache = new Map<number, OaPaperResp>();

export function getCachedPaper(id: number) {
	return paperCache.get(id);
}

export function setCachedPaper(id: number, data: OaPaperResp) {
	paperCache.set(id, data);
}
