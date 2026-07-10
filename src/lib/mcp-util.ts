// Client-safe helpers for the MCP pages (no server imports).

import type { SessionParams } from '$lib/types/mcp';

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
	const args = [`--backend ${p.backend}`, `--foci ${p.foci.join(',')}`];
	if (p.subject) args.push(`--subject ${JSON.stringify(p.subject)}`);
	if (p.question) args.push(`--question ${JSON.stringify(p.question)}`);
	if (p.investigate) args.push(`--investigate ${p.investigate}`);
	if (p.model) args.push(`--model ${p.model}`);
	if (p.suggestEndpoints === false) args.push('--no-suggest-endpoints');
	return `make deep-explore ARGS='${args.join(' ')}'`;
}
