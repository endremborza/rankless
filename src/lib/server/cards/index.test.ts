import { describe, expect, it } from 'vitest';
import { RAINBOW_SORTS } from '$lib/utils/paper-rainbow';
import { buildCardSvg } from './index';
import { CARD_SPEC } from './kind';
import { SORT_WORDS } from './timeline';

// A backend that answers every call, so a refusal is the route's own.
function backend() {
	let calls = 0;
	const fetchFn = (async () => {
		calls++;
		return new Response(JSON.stringify({ name: 'X' }));
	}) as typeof fetch;
	return { fetchFn, calls: () => calls };
}

const build = (kind: string, rootType: string, fetchFn: typeof fetch) =>
	buildCardSvg(kind, rootType, 'x', new URLSearchParams(), fetchFn);

describe('card kinds', () => {
	it('answers a kind the contract does not name with a 404', async () => {
		for (const kind of ['constructor', 'toString', 'nope'])
			await expect(build(kind, 'authors', backend().fetchFn)).rejects.toMatchObject({
				status: 404
			});
	});

	it('answers a kind the type does not have with a 404, before any backend call', async () => {
		const be = backend();
		await expect(build('papers', 'institutions', be.fetchFn)).rejects.toMatchObject({
			status: 404
		});
		expect(be.calls()).toBe(0);
	});

	it('offers the orderings the loaders know', () => {
		expect(CARD_SPEC.papers.params.sort.options).toEqual([...RAINBOW_SORTS]);
		expect(CARD_SPEC.timeline.params.sort.options).toEqual(Object.keys(SORT_WORDS));
	});
});
