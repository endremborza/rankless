// Shape of the baked MCP demo manifest (src/lib/assets/data/mcp-manifest.json),
// generated from the Python sources by pyscripts/build_mcp_manifest.py. Consumed
// by src/routes/(stat)/mcp/+page.svelte.

export type McpTool = {
	name: string;
	endpoint: string;
	summary: string;
	description: string;
};

export type McpResource = { uri: string; text: string };
export type McpPrompt = { name: string; description: string };
export type McpCommand = { label: string; cmd: string };
export type McpConnect = { url: string; transport: string; snippets: McpCommand[] };

export type McpManifest = {
	generated: string;
	connect: McpConnect;
	tools: McpTool[];
	resources: McpResource[];
	prompts: McpPrompt[];
};

// One backend read replayed by mcp_server/verify.py: the call, the dotted
// path into its response, what the model claimed and what the replay found.
export type VerifiedFact<V = unknown> = {
	tool: string;
	args: Record<string, unknown>;
	path: string;
	claimed: V;
	reproduced: V;
	ok: boolean;
	error: string | null;
};
