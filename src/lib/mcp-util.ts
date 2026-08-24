// Client-safe helpers for the MCP pages (no server imports).

import type {
	GenerationMeta,
	GenerationParams,
	GenerationType,
	SessionMeta,
	SessionParams
} from '$lib/types/mcp';

// The queueable generator workflows: label + allowed entity types per workflow.
// Mirrors pyscripts/explore/runs.py WORKFLOWS (minus deep).
export const GENERATIONS: Record<GenerationType, { label: string; etypes: string[] }> = {
	'game-cards': { label: 'Game cards', etypes: ['institutions', 'countries'] },
	'impact-stories': { label: 'Impact stories', etypes: ['institutions', 'authors', 'countries'] }
};

export function isGenerationType(t: string): t is GenerationType {
	return t in GENERATIONS;
}

export function isGenerationParams(p: SessionParams): p is GenerationParams {
	return p.type !== undefined && p.type !== 'deep';
}

export function isGenerationMeta(m: SessionMeta): m is GenerationMeta {
	return m.type !== undefined && m.type !== 'deep';
}

// Mirrors pyscripts/explore/runs.py run_stamp/run_name: every agent run is
// named `<workflow>-<scope>-<UTC yyyymmddThhmmss>`.
export function runStamp(): string {
	return new Date().toISOString().replace(/[-:]/g, '').slice(0, 15);
}

export function runName(workflow: string, scope: string): string {
	return `${workflow}-${scope}-${runStamp()}`;
}

// Entity URLs are stored absolute (rankless.org); render them same-site.
export function entPath(url: string): string {
	try {
		return new URL(url).pathname;
	} catch {
		return url;
	}
}

// Reconstruct the CLI command that produced (or would produce) a session.
export function sessionCommand(p: SessionParams): string {
	if (isGenerationParams(p)) {
		const args = [`--backend ${p.backend}`, `--etype ${p.etype}`, `--count ${p.count}`];
		if (p.model) args.push(`--model ${p.model}`);
		return `uv run -m pyscripts ${p.type} ${args.join(' ')}`;
	}
	const args = [`--backend ${p.backend}`, `--foci ${p.foci.join(',')}`];
	if (p.subject) args.push(`--subject ${JSON.stringify(p.subject)}`);
	if (p.question) args.push(`--question ${JSON.stringify(p.question)}`);
	if (p.investigate) args.push(`--investigate ${p.investigate}`);
	if (p.model) args.push(`--model ${p.model}`);
	if (p.suggestEndpoints === false) args.push('--no-suggest-endpoints');
	return `make deep-explore ARGS='${args.join(' ')}'`;
}
