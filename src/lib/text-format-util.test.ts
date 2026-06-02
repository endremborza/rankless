import { describe, it, expect } from 'vitest';
import type { RootType } from './tree-types';
import {
	TypeWriterWordChanger,
	isAsciiOnly,
	pluralize,
	formatNumber,
	prettifyRoot,
	getSpecDesc,
	semantify,
	singularize,
	SPEC_BPS
} from './text-format-util';

describe('isAsciiOnly', () => {
	it('returns true for ascii strings', () => {
		expect(isAsciiOnly('hello world')).toBe(true);
		expect(isAsciiOnly('abc123')).toBe(true);
	});
	it('returns false for non-ascii', () => {
		expect(isAsciiOnly('héllo')).toBe(false);
		expect(isAsciiOnly('日本語')).toBe(false);
	});
	it('returns false for empty string', () => {
		expect(isAsciiOnly('')).toBe(false);
	});
});

describe('pluralize', () => {
	it('singular for 1', () => {
		expect(pluralize('paper', 1)).toBe('1 paper');
	});
	it('plural for 0', () => {
		expect(pluralize('paper', 0)).toBe('0 papers');
	});
	it('plural for >1', () => {
		expect(pluralize('citation', 5)).toBe('5 citations');
	});
	it('formats large numbers', () => {
		expect(pluralize('paper', 1500)).toBe('1.5k papers');
	});
});

describe('singularize', () => {
	it('handles known words', () => {
		expect(singularize('countries')).toBe('country');
	});
	it('strips last char for unknown words', () => {
		expect(singularize('authors')).toBe('author');
		expect(singularize('institutions')).toBe('institution');
	});
});

describe('formatNumber', () => {
	it('formats zero', () => {
		expect(formatNumber(0)).toBe('0');
	});
	it('formats millions', () => {
		expect(formatNumber(2_500_000)).toBe('2.5M');
	});
	it('formats thousands', () => {
		expect(formatNumber(1500)).toBe('1.5k');
	});
	it('formats decimals < 1', () => {
		expect(formatNumber(0.75)).toBe('0.75');
	});
	it('formats small integers (no decimals for whole numbers)', () => {
		expect(formatNumber(5)).toBe('5');
		expect(formatNumber(5.5)).toBe('5.50');
	});
	it('formats double digits', () => {
		expect(formatNumber(42)).toBe('42');
	});
	it('respects maxFix', () => {
		expect(formatNumber(0.75, 0)).toBe('1');
		expect(formatNumber(5, 0)).toBe('5');
	});
});

describe('prettifyRoot', () => {
	it('maps sources to journals', () => {
		expect(prettifyRoot('sources')).toBe('journals');
	});
	it('maps subfields to fields', () => {
		expect(prettifyRoot('subfields')).toBe('fields');
	});
	it('passes through other types', () => {
		expect(prettifyRoot('authors')).toBe('authors');
		expect(prettifyRoot('countries')).toBe('countries');
		expect(prettifyRoot('institutions')).toBe('institutions');
	});
});

describe('getSpecDesc', () => {
	it('returns Very High for rates above top breakpoint', () => {
		expect(getSpecDesc(SPEC_BPS[2] + 1)).toBe('Very High');
	});
	it('returns High for rates above mid breakpoint', () => {
		expect(getSpecDesc(SPEC_BPS[1] + 0.1)).toBe('High');
	});
	it('returns Low for rates below low breakpoint', () => {
		expect(getSpecDesc(SPEC_BPS[0] - 0.1)).toBe('Low');
	});
	it('returns Average for middle rates', () => {
		expect(getSpecDesc(1.0)).toBe('Average');
	});
});

describe('TypeWriterWordChanger', () => {
	it('initializes with correct state', () => {
		const tw = new TypeWriterWordChanger(['hello', 'world']);
		expect(tw.texts).toEqual(['hello', 'world']);
		expect(tw.wordInd).toBe(0);
		expect(tw.direction).toBe(1);
		expect(tw.text).toBe('hello');
	});

	it('changeText progresses letter index', () => {
		const tw = new TypeWriterWordChanger(['ab']);
		tw.letterInd = 0;
		tw.direction = 1;
		tw.changeText();
		expect(tw.letterInd).toBe(1);
		expect(tw.text).toBe('');
	});

	it('wraps wordInd back to 0 when past end', () => {
		const tw = new TypeWriterWordChanger(['a', 'b']);
		tw.wordInd = 2;
		tw.letterInd = 0;
		tw.direction = 1;
		tw.changeText();
		expect(tw.wordInd).toBe(0);
		expect(tw.text).toBe('');
	});
});

describe('semantify', () => {
	it('returns semantic for known path', () => {
		expect(semantify('subfields-true', 'authors', [], 0)).toBe('about');
	});
	it('returns semantic for nested path', () => {
		expect(semantify('works-true', 'authors', ['subfields-true'], 1)).toBe('specifically');
	});
	it('returns original string for unknown rootType', () => {
		expect(semantify('anything', 'works' as unknown as RootType, [], 0)).toBe('anything');
	});
	it('returns original string for unknown key', () => {
		expect(semantify('nonexistent', 'authors', [], 0)).toBe('nonexistent');
	});
	it('returns original string when depth exceeds tree', () => {
		expect(semantify('x', 'authors', ['subfields-true', 'works-true', 'a', 'b'], 4)).toBe('x');
	});
});
