// SQL for the MCP object store index, shared by the app reader (objects.ts) and
// the e2e seeder (tests/seed-game.ts), which runs under plain bun — keep this
// module free of $app/$env imports. The Python side mirrors it in
// pyscripts/object_store.py; the two must stay identical.

export const OBJECTS_SCHEMA = `
CREATE TABLE IF NOT EXISTS mcp_objects (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	kind TEXT NOT NULL,
	obj_key TEXT NOT NULL,
	bundle TEXT NOT NULL,
	line INTEGER NOT NULL,
	gen_at TEXT NOT NULL,
	etype TEXT,
	sem_id TEXT,
	title TEXT,
	status TEXT NOT NULL DEFAULT 'new',
	status_note TEXT,
	created_at TEXT NOT NULL DEFAULT (datetime('now')),
	updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_obj_version ON mcp_objects(kind, obj_key, bundle);
CREATE INDEX IF NOT EXISTS idx_obj_kind_status ON mcp_objects(kind, status);
`;

// Latest non-rejected version per logical key — what consumers play/present.
export const OBJECTS_CURRENT_SQL = `
SELECT * FROM (
	SELECT *, ROW_NUMBER() OVER (
		PARTITION BY kind, obj_key ORDER BY gen_at DESC, bundle DESC
	) AS rn FROM mcp_objects WHERE kind = ? AND status != 'rejected'
) WHERE rn = 1 ORDER BY obj_key
`;
