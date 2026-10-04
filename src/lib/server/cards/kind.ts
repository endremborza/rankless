import { error } from '@sveltejs/kit';
import type { Component } from 'svelte';
import type * as tt from '$lib/tree-types';
import spec from '$lib/assets/data/card-kinds.json';

// The card contract, in the one file `mcp_server/cards.py` reads too: every kind with the entity
// types it exists for and its variant parameters, each with what it is, its default and its limit.
export const CARD_SPEC = spec;
export type CardKindName = keyof typeof spec;

// What a kind's loader gets: the entity (its profile already loaded, `null` for a cohort card
// with no entity), the variant parameters and the tree specs.
export type CardContext = {
	rootType: tt.RootType;
	semanticId: string;
	params: URLSearchParams;
	specs: tt.TreeSpecs;
	view: tt.View | null;
	fetch: typeof fetch;
};

// A loaded card: the visualization's props, the caption under the name, and the name itself when
// the card is not about one entity.
export type CardData = { props: Record<string, unknown>; caption: string; name?: string };

export type CardKind = {
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	component: Component<any>;
	load(ctx: CardContext): Promise<CardData>;
};

// An id as the data spells it (a hit paper's is its DOI): no whitespace, and no comma, which
// separates ids. What an id names is checked by the loader against the data it loads.
export const ID_CHARS = /^[^\s,]+$/;

// Variant parameters are ids, years, counts or fixed words; anything else is a 404, never free
// text, since a card URL is public and cached by its parameters.
export function intParam(
	params: URLSearchParams,
	key: string,
	fallback: number,
	lo: number,
	hi: number
): number {
	const raw = params.get(key);
	if (raw == null || raw === '') return fallback;
	const n = Number(raw);
	if (!Number.isInteger(n) || n < lo || n > hi) error(404, `${key} out of range`);
	return n;
}

export function flagParam(params: URLSearchParams, key: string, fallback: boolean): boolean {
	const raw = params.get(key);
	if (raw == null || raw === '') return fallback;
	if (raw !== '0' && raw !== '1') error(404, `${key} must be 0 or 1`);
	return raw === '1';
}

export function oneOf<T extends string>(
	params: URLSearchParams,
	key: string,
	options: readonly T[],
	fallback: T
): T {
	const raw = params.get(key);
	if (raw == null || raw === '') return fallback;
	if (!options.includes(raw as T)) error(404, `${key} must be one of ${options.join(', ')}`);
	return raw as T;
}

// A comma-separated list of ids, at most `max` of them.
export function idsParam(params: URLSearchParams, key: string, max: number): string[] {
	const raw = params.get(key);
	if (!raw) return [];
	const ids = raw.split(',').filter(Boolean);
	if (ids.length > max || ids.some((id) => !ID_CHARS.test(id))) error(404, `bad ${key}`);
	return ids;
}

// A backend response, or a 404: a card URL is what crawlers hit with stale or garbage ids, and a
// backend hiccup must never surface as a 500.
export async function beJson<T>(fetchFn: typeof fetch, url: string): Promise<T> {
	const res = await fetchFn(url).catch(() => null);
	if (!res?.ok) error(404, 'card unavailable');
	const body = await res.json().catch(() => null);
	if (body == null) error(404, 'card unavailable');
	return body as T;
}

// The UI word for each entity type in a caption ("Fields" is the subfields entity, deliberately).
export const LEVEL_WORD: Record<tt.EntityType, string> = {
	authors: 'author',
	institutions: 'institution',
	sources: 'journal',
	countries: 'country',
	subfields: 'field',
	'hit-papers': 'hit paper',
	works: 'paper',
	topics: 'topic',
	qs: 'journal quartile'
};
