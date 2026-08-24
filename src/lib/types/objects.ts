// Unified MCP object store: payload-free index rows (mcp_objects) addressing
// immutable zstd bundles under data/mcp-objects/. Source of truth for writers:
// pyscripts/object_store.py; the frontend reads via $lib/server/objects.ts.

export type ObjectStatus = 'new' | 'approved' | 'rejected';

export type ObjectKind = 'game-card' | 'country-card' | 'finding' | 'impact-story';

export type McpObject = {
	id: number;
	kind: ObjectKind;
	objKey: string;
	bundle: string;
	line: number;
	genAt: string;
	etype: string | null;
	semId: string | null;
	title: string | null;
	status: ObjectStatus;
	// Reviewer's reason for the current status (required on rejection, kept for
	// later review against data improvements).
	statusNote: string | null;
	payload: unknown;
	createdAt: string;
	updatedAt: string;
};
