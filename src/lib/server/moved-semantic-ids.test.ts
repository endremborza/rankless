import { describe, it, expect, vi } from 'vitest';
import { movedSemanticId } from './moved-semantic-ids';

const SCIENCE_OA_ID = 3880285;

function backend(current: Record<number, string>) {
	return vi.fn(async (input: RequestInfo | URL) => {
		const oaId = Number(String(input).split('/').pop());
		return new Response(JSON.stringify([current[oaId] ?? null]));
	});
}

describe('movedSemanticId', () => {
	it('finds the slug the served release gives the entity behind a past slug', async () => {
		const fetchFn = backend({ [SCIENCE_OA_ID]: 'science' });
		expect(await movedSemanticId('sources', 'science-online', fetchFn)).toBe('science');
		expect(fetchFn).toHaveBeenCalledWith(expect.stringContaining(`/sources/${SCIENCE_OA_ID}`));
	});

	it('asks nothing for a slug no past release served', async () => {
		const fetchFn = backend({});
		expect(await movedSemanticId('sources', 'no-such-journal', fetchFn)).toBeUndefined();
		expect(fetchFn).not.toHaveBeenCalled();
	});

	it('leaves an entity the served release dropped to the caller', async () => {
		expect(await movedSemanticId('sources', 'science-online', backend({}))).toBeUndefined();
	});
});
