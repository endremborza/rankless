// Client-safe helpers for the MCP pages (no server imports).

import type {
	DeepMeta,
	DeepParams,
	GenerationMeta,
	GenerationParams,
	GenerationType,
	SessionMeta,
	SessionParams
} from '$lib/types/mcp';

// Backend labels a queued run may name; mirrors mcp_server.BACKENDS.
export const BACKENDS = ['local', 'alpha', 'live'] as const;

// The queueable generator workflows: label + allowed entity types per workflow.
// Mirrors pyscripts/explore/runs.py WORKFLOWS (minus deep).
export const GENERATIONS: Record<GenerationType, { label: string; etypes: string[] }> = {
	'rankless-game-card-mining': { label: 'Game cards', etypes: ['institutions'] },
	'impact-stories': { label: 'Impact stories', etypes: ['institutions', 'authors', 'countries'] }
};

export function isGenerationType(t: string): t is GenerationType {
	return t in GENERATIONS;
}

export function isGenerationParams(p: SessionParams): p is GenerationParams {
	return isGenerationType(p.type);
}

export function isGenerationMeta(m: SessionMeta): m is GenerationMeta {
	return isGenerationType(m.type);
}

// Rows outlive workflows: a session written by a retired generator matches
// neither guard, and the pages show it as such (so an admin can delete it)
// instead of reading deep fields off it. A params row without a type is deep.
export function isDeepParams(p: SessionParams): p is DeepParams {
	const t = (p as { type?: string }).type;
	return t === undefined || t === 'deep';
}

export function isDeepMeta(m: SessionMeta): m is DeepMeta {
	return m.type === 'deep';
}

export function workflowOf(x: SessionParams | SessionMeta): string {
	return x.type;
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
	if (!isDeepParams(p)) return '';
	const args = [`--backend ${p.backend}`, `--foci ${p.foci.join(',')}`];
	if (p.subject) args.push(`--subject ${JSON.stringify(p.subject)}`);
	if (p.question) args.push(`--question ${JSON.stringify(p.question)}`);
	if (p.investigate) args.push(`--investigate ${p.investigate}`);
	if (p.model) args.push(`--model ${p.model}`);
	if (p.suggestEndpoints === false) args.push('--no-suggest-endpoints');
	return `make deep-explore ARGS='${args.join(' ')}'`;
}
