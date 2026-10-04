import { describe, expect, it } from 'vitest';
import { wrapLines } from './cards';

describe('wrapLines', () => {
	it('fills lines greedily and clips the rest into the last one', () => {
		expect(wrapLines('one two three four five six', 9, 2)).toEqual(['one two', 'three fo…']);
	});

	it('returns fewer lines when the text is short', () => {
		expect(wrapLines('short title', 20, 2)).toEqual(['short title']);
	});
});
