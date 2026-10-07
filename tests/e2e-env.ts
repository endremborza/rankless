import paths from '../src/lib/assets/data/paths.json' with { type: 'json' };

const E2E_DIR = '.e2e-data';

// Scratch user DB + object store for the preview server, so seeded fixtures never land in the
// real data/ files (which ride the cross-box handoff).
export const E2E_ENV = {
	RANKLESS_DB_PATH: `${E2E_DIR}/${paths.db}`,
	MCP_OBJECTS_ROOT: `${E2E_DIR}/${paths.mcpObjects}`
};
