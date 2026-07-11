import { describe, it, expect } from 'vitest';
import {
	canonicalDoi,
	conclusiveClaimIds,
	evaluateDoiAuthorship,
	isAutoModerated,
	normalizeOrcid,
	pairKey,
	pickLatestVerdicts,
	summarize,
	type EnrichmentMap
} from './review';
import type { LedgerEvent } from './db';
import type { ReviewVerdict, WorkRecord } from '$lib/types/review';

const work = (orcids: (string | null)[]): WorkRecord => ({
	title: 't',
	year: 2025,
	venue: null,
	oa_work_id: null,
	authors: orcids.map((orcid, i) => ({ name: `a${i}`, orcid, position: i }))
});

const verdict = (created_at: string, model = 'sonnet'): ReviewVerdict => ({
	orcid: '0000-0002-1247-296X',
	kind: 'claim_paper',
	subject_hash: 'abc',
	model,
	verdict: 'approve',
	confidence: 0.9,
	reasoning: 'r',
	checks: null,
	created_at
});

describe('normalizeOrcid / canonicalDoi', () => {
	it('strips URL prefixes and uppercases the checksum x', () => {
		expect(normalizeOrcid('https://orcid.org/0000-0002-1247-296x')).toBe('0000-0002-1247-296X');
		expect(normalizeOrcid(' 0000-0002-1247-296X ')).toBe('0000-0002-1247-296X');
	});
	it('canonicalizes DOIs to bare lowercase', () => {
		expect(canonicalDoi('https://doi.org/10.7551/MITPRESS/9647.001.0001')).toBe(
			'10.7551/mitpress/9647.001.0001'
		);
		expect(canonicalDoi('10.1126/sciadv.abc0764')).toBe('10.1126/sciadv.abc0764');
	});
});

describe('evaluateDoiAuthorship', () => {
	it('is conclusive when either source lists the claimant', () => {
		const rec = work(['0000-0002-1247-296X']);
		expect(evaluateDoiAuthorship('0000-0002-1247-296x', rec, null)).toEqual({
			conclusive: true,
			sources: ['crossref']
		});
		expect(evaluateDoiAuthorship('0000-0002-1247-296X', null, rec).sources).toEqual(['openalex']);
	});

	it('reports both sources when both list the claimant', () => {
		const rec = work([null, '0000-0002-1247-296X']);
		expect(evaluateDoiAuthorship('0000-0002-1247-296X', rec, rec).sources).toEqual([
			'crossref',
			'openalex'
		]);
	});

	it('is inconclusive without a listed ORCID or without records', () => {
		expect(evaluateDoiAuthorship('0000-0002-1247-296X', work([null]), null).conclusive).toBe(false);
		expect(evaluateDoiAuthorship('0000-0002-1247-296X', null, null).conclusive).toBe(false);
	});
});

describe('pickLatestVerdicts', () => {
	it('keeps the newest verdict per subject across models', () => {
		const old = verdict('2026-07-01T10:00:00Z');
		const newer = verdict('2026-07-02T10:00:00Z', 'opus');
		const map = pickLatestVerdicts([old, newer]);
		expect(map.size).toBe(1);
		expect([...map.values()][0].model).toBe('opus');
	});
});

describe('isAutoModerated', () => {
	it('detects the auto: moderator convention', () => {
		expect(isAutoModerated('auto:doi-authorship')).toBe(true);
		expect(isAutoModerated('0000-0002-1247-296X')).toBe(false);
		expect(isAutoModerated(null)).toBe(false);
	});
});

describe('conclusiveClaimIds', () => {
	const claim = (event_id: number, doi: string, orcid: string): LedgerEvent => ({
		event_id,
		orcid,
		kind: 'claim_paper',
		payload: {
			kind: 'claim_paper',
			work: {
				oa_id: null,
				doi,
				dm_id_at_creation: null,
				semantic_id_at_creation: null,
				run_id_at_creation: null,
				display_snapshot: { title: '', year: null }
			}
		},
		subject_hash: `h${event_id}`,
		created_at: '2026-07-01 00:00:00',
		revoked_at: null,
		moderation: 'pending_review',
		moderated_by: null,
		moderated_at: null
	});

	it('flags only claims whose enrichment lists the claimant', () => {
		const orcid = '0000-0002-1247-296X';
		const enrichment: EnrichmentMap = new Map([
			[
				pairKey('crossref', '10.1/proven'),
				{
					source: 'crossref',
					key: '10.1/proven',
					status: 'ok',
					data: work([orcid]),
					fetched_at: ''
				}
			],
			[
				pairKey('crossref', '10.1/other'),
				{
					source: 'crossref',
					key: '10.1/other',
					status: 'ok',
					data: work(['0000-0001-0000-0000']),
					fetched_at: ''
				}
			]
		]);
		const events = [
			claim(1, '10.1/proven', orcid),
			claim(2, '10.1/other', orcid),
			claim(3, '10.1/unfetched', orcid),
			{ ...claim(4, '10.1/proven', orcid), moderation: 'accepted' as const }
		];
		expect(conclusiveClaimIds(events, enrichment)).toEqual([1]);
	});
});

describe('summarize', () => {
	it('falls back from title to doi for bare claims', () => {
		const s = summarize({
			kind: 'claim_paper',
			work: {
				oa_id: null,
				doi: '10.1126/sciadv.abc0764',
				dm_id_at_creation: null,
				semantic_id_at_creation: null,
				run_id_at_creation: null,
				display_snapshot: { title: '', year: null }
			}
		});
		expect(s).toBe('claim “10.1126/sciadv.abc0764”');
	});
});
