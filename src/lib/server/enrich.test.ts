import { describe, it, expect } from 'vitest';
import { pluckCrossref, pluckOpenAlex, pluckOrcid } from './enrich';

const crossrefJson = {
	message: {
		title: ['The Atlas of Economic Complexity'],
		'container-title': ['MIT Press'],
		issued: { 'date-parts': [[2014, 1, 3]] },
		author: [
			{ given: 'Ricardo', family: 'Hausmann', ORCID: 'http://orcid.org/0000-0002-1247-296X' },
			{ given: 'César A.', family: 'Hidalgo' }
		]
	}
};

const openAlexJson = {
	id: 'https://openalex.org/W2135023421',
	title: 'The Atlas of Economic Complexity',
	publication_year: 2014,
	primary_location: { source: { display_name: 'MIT Press' } },
	authorships: [
		{
			author: {
				display_name: 'Ricardo Hausmann',
				orcid: 'https://orcid.org/0000-0002-1247-296x'
			}
		},
		{ author: { display_name: 'César A. Hidalgo', orcid: null } }
	]
};

const orcidRecordJson = {
	person: {
		name: {
			'given-names': { value: 'César' },
			'family-name': { value: 'Hidalgo' },
			'credit-name': { value: 'César A. Hidalgo' }
		}
	}
};

const orcidWorksJson = {
	group: [
		{
			'external-ids': {
				'external-id': [
					{
						'external-id-type': 'doi',
						'external-id-value': 'https://doi.org/10.7551/MITPRESS/9647.001.0001'
					},
					{ 'external-id-type': 'eid', 'external-id-value': '2-s2.0-000' }
				]
			},
			'work-summary': [{ title: { title: { value: 'The Atlas of Economic Complexity' } } }]
		},
		{
			'external-ids': { 'external-id': [] },
			'work-summary': [{ title: { title: { value: 'Untracked preprint' } } }]
		}
	]
};

describe('pluckCrossref', () => {
	it('extracts title, year, venue and normalized author ORCIDs', () => {
		const rec = pluckCrossref(crossrefJson);
		expect(rec.title).toBe('The Atlas of Economic Complexity');
		expect(rec.year).toBe(2014);
		expect(rec.venue).toBe('MIT Press');
		expect(rec.oa_work_id).toBeNull();
		expect(rec.authors).toEqual([
			{ name: 'Ricardo Hausmann', orcid: '0000-0002-1247-296X', position: 0 },
			{ name: 'César A. Hidalgo', orcid: null, position: 1 }
		]);
	});

	it('tolerates an empty message', () => {
		const rec = pluckCrossref({ message: {} });
		expect(rec).toEqual({ title: null, year: null, venue: null, oa_work_id: null, authors: [] });
	});
});

describe('pluckOpenAlex', () => {
	it('extracts the bare work id and uppercases lower-x ORCIDs', () => {
		const rec = pluckOpenAlex(openAlexJson);
		expect(rec.oa_work_id).toBe('W2135023421');
		expect(rec.year).toBe(2014);
		expect(rec.authors[0].orcid).toBe('0000-0002-1247-296X');
		expect(rec.authors[1].orcid).toBeNull();
	});
});

describe('pluckOrcid', () => {
	it('prefers credit-name and canonicalizes work DOIs', () => {
		const rec = pluckOrcid(orcidRecordJson, orcidWorksJson);
		expect(rec.name).toBe('César A. Hidalgo');
		expect(rec.work_dois).toEqual(['10.7551/mitpress/9647.001.0001']);
		expect(rec.work_titles).toEqual(['The Atlas of Economic Complexity', 'Untracked preprint']);
		expect(rec.n_works).toBe(2);
	});

	it('falls back to given+family and handles empty works', () => {
		const noCredit = {
			person: { name: { 'given-names': { value: 'A' }, 'family-name': { value: 'B' } } }
		};
		const rec = pluckOrcid(noCredit, {});
		expect(rec.name).toBe('A B');
		expect(rec.work_dois).toEqual([]);
		expect(rec.n_works).toBe(0);
	});

	it('yields null name when the record has none', () => {
		expect(pluckOrcid({}, {}).name).toBeNull();
	});
});
