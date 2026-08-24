// Shape of the baked MCP demo manifest (src/lib/assets/data/mcp-manifest.json),
// generated from the Python sources by pyscripts/build_mcp_manifest.py. Consumed
// by src/routes/(stat)/mcp/+page.svelte.

export type McpTool = {
	name: string;
	endpoint: string;
	summary: string;
	description: string;
};

export type McpFocus = { name: string; description: string };
export type McpOption = { flag: string; help: string };
export type McpResource = { uri: string; text: string };
export type McpPrompt = { name: string; description: string };
export type McpCommand = { label: string; cmd: string };
export type McpEndpointIdea = { name: string; rationale: string; unlocks: string };
export type McpConnect = { url: string; transport: string; snippets: McpCommand[] };

export type McpManifest = {
	generated: string;
	connect: McpConnect;
	tools: McpTool[];
	foci: McpFocus[];
	options: McpOption[];
	resources: McpResource[];
	prompts: McpPrompt[];
};

// --- Browsable exploration sessions (index row + on-disk findings.json) --- //

export type SessionStatus = 'queued' | 'running' | 'done' | 'failed';
export type SessionVisibility = 'public' | 'private';

// The object-store generator workflows (pyscripts/explore/runs.py WORKFLOWS,
// minus deep, which has its own param shape).
export type GenerationType = 'game-cards' | 'country-cards' | 'impact-stories';

// What an admin submits to enqueue a run, discriminated on `type`: absent (or
// 'deep') mirrors deep.py's scoping flags; generation workflows carry
// etype/count instead of foci.
export type DeepParams = {
	type?: 'deep';
	backend: string;
	foci: string[];
	subject?: string | null;
	question?: string | null;
	investigate?: string | null;
	model?: string | null;
	suggestEndpoints?: boolean;
};

export type GenerationParams = {
	type: GenerationType;
	backend: string;
	etype: string;
	count: number;
	model?: string | null;
};

export type SessionParams = DeepParams | GenerationParams;

// The `meta` block a run writes, discriminated the same way: deep.py's
// findings.json shape, or the leaner generation summary.
export type DeepMeta = {
	type?: 'deep';
	backend: string;
	backendUrl: string;
	model: string;
	foci: string[];
	subject: string | null;
	question: string | null;
	investigate: string | null;
	generated: string;
	seedCount: number;
	runtimeSeconds: { mine: number; reproduce: number; total: number };
	counts: {
		findings: number;
		byFocus: Record<string, number>;
		reproducedFindings: number;
		metrics: number;
		metricsReproduced: number;
		metricsMismatch: number;
		metricsError: number;
		endpointSuggestions: number;
	};
};

export type GenerationMeta = {
	type: GenerationType;
	backend: string;
	model: string;
	generated: string;
	counts: { accepted: number; targets: number; stored: number };
};

export type SessionMeta = DeepMeta | GenerationMeta;

export type McpSession = {
	name: string;
	orcid: string | null;
	status: SessionStatus;
	visibility: SessionVisibility;
	title: string | null;
	params: SessionParams;
	meta: SessionMeta | null;
	error: string | null;
	createdAt: string;
	updatedAt: string;
};

// One reproduced metric inside a finding (keys as deep.py emits them).
export type SessionMetric = {
	key: string;
	label: string;
	tool: string;
	args: Record<string, unknown>;
	path: string;
	claimed: number | string | null;
	reproduced: number | string | null;
	ok: boolean;
	error: string | null;
};

export type SessionFinding = {
	id: string;
	focus: string;
	title: string;
	description: string;
	share_kind: string | null;
	issue_kind: string | null;
	question: string | null;
	entities: string[];
	ledger_suggestion: { kind: string; note?: string } | null;
	metrics: SessionMetric[];
	_verified: boolean;
};

// The parsed findings.json read from a session directory (deep runs only).
export type SessionFindings = {
	meta: DeepMeta;
	findings: SessionFinding[];
	endpointSuggestions: McpEndpointIdea[];
};
