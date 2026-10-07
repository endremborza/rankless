// Where the user data, the share-card cache and the survey log live, read from
// the same JSON as pyscripts/paths.py. No SvelteKit virtual modules, so bun
// scripts import it too.
import paths from './assets/data/paths.json';

export const DB_REL = `${paths.dataDir}/${paths.db}`;
export const MCP_OBJECTS_REL = `${paths.dataDir}/${paths.mcpObjects}`;
export const USER_LEDGER_DIR = paths.userLedger;
export const CARD_CACHE_NAME = paths.cardCache;
export const SURVEY_LOG_PATH = paths.surveyLog;
