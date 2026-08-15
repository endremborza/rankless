import { describe, it, expect } from 'vitest';
import { canonicalDoi, normalizeOrcid } from './identifiers';

describe('canonicalDoi', () => {
	it('strips every resolver prefix and lowercases', () => {
		expect(canonicalDoi('https://doi.org/10.1/Foo')).toBe('10.1/foo');
		expect(canonicalDoi('http://dx.doi.org/10.1/Bar')).toBe('10.1/bar');
		expect(canonicalDoi('  10.1/X  ')).toBe('10.1/x');
		expect(canonicalDoi('https://doi.org/10.7551/MITPRESS/9647.001.0001')).toBe(
			'10.7551/mitpress/9647.001.0001'
		);
		expect(canonicalDoi('10.1126/sciadv.abc0764')).toBe('10.1126/sciadv.abc0764');
	});
});

describe('normalizeOrcid', () => {
	it('strips the URL prefix and uppercases the checksum x', () => {
		expect(normalizeOrcid('https://orcid.org/0000-0002-1247-296x')).toBe('0000-0002-1247-296X');
		expect(normalizeOrcid(' 0000-0002-1247-296X ')).toBe('0000-0002-1247-296X');
	});
});
