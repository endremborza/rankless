import { describe, expect, it } from 'vitest';

import { isDeepMeta, isDeepParams, sessionCommand } from './mcp-util';
import type { SessionMeta, SessionParams } from './types/mcp';

// A row left by a workflow that no longer exists: neither deep nor a known generator.
const retiredParams = {
	type: 'game-cards',
	backend: 'alpha',
	etype: 'institutions',
	count: 24
} as unknown as SessionParams;
const retiredMeta = {
	type: 'game-cards',
	backend: 'alpha',
	model: 'claude-sonnet-5',
	generated: '2026-08-24T13:13:16Z',
	counts: { accepted: 24, targets: 40, stored: 99 }
} as unknown as SessionMeta;

describe('sessions of retired workflows', () => {
	it('are neither deep nor generation', () => {
		expect(isDeepParams(retiredParams)).toBe(false);
		expect(isDeepMeta(retiredMeta)).toBe(false);
	});

	it('get no reproduce command instead of a crash', () => {
		expect(sessionCommand(retiredParams)).toBe('');
	});
});

describe('deep sessions', () => {
	it('are recognised with or without an explicit type', () => {
		const p = { backend: 'live', foci: ['query'], question: 'q' } as unknown as SessionParams;
		expect(isDeepParams(p)).toBe(true);
		expect(isDeepParams({ ...p, type: 'deep' } as SessionParams)).toBe(true);
		expect(sessionCommand(p)).toContain('--foci query');
	});
});
