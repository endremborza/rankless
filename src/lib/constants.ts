import type { EntityType, RelTypes, RootType } from './tree-types';
import { PUBLIC_ORIGIN, PUBLIC_BACKEND_URL } from '$env/static/public';
import { dev } from '$app/environment';
import { MAX_SLICE, PORT } from '$lib/wire/rankless_server/consts';

export const APP_NAME = 'Rankless';

// Feature switches: `dev` keeps a feature dev-only, `true` releases it. A switched-off
// feature stays reachable at its URLs but is linked from nowhere; email also closes its
// consent API and preferences page.
export const EMAIL_FEATURE_ON = dev;
export const GAME_FEATURE_ON = dev;
export const MCP_FEATURE_ON = dev;

// Brand proof-points that need no data: the home card shows them after its live /counts figures,
// and alone when that fetch fails.
export const BRAND_TAGLINE = 'Explore academic impact beyond rankings';
export const BRAND_STATS = ['every field'];

export const FULL_HOST = PUBLIC_ORIGIN;
export const SITEMAP_STEP_SIZE = 8192;
export const ENTITY_SITEMAP_STEP_SIZE = MAX_SLICE;

export const BE_URL = `http://127.0.0.1:${PORT}/v1`;
export const BE_REMOTE_URL = `${PUBLIC_BACKEND_URL}/v1`;

export const ROOT_TYPES: RootType[] = [
	'authors',
	'institutions',
	'sources',
	'countries',
	'subfields',
	'hit-papers'
];

// Root types whose entities form a ranked cohort (top lists, browse tables); hit-papers are a paper set.
export const COHORT_ROOT_TYPES: RootType[] = ROOT_TYPES.filter((rt) => rt !== 'hit-papers');

export const REL_TYPES: RelTypes[] = [
	'paper-fields',
	'citing-fields',
	'paper-topics',
	'collab-nation',
	'paper-journals',
	'paper-authors'
];

export const ENTITY_TYPES: EntityType[] = ['topics', 'works', 'qs', ...ROOT_TYPES];

// The backend names entity types with plain strings; these narrow one to the site's vocabulary.
export const isRootType = (s: string): s is RootType => (ROOT_TYPES as string[]).includes(s);
export const isEntityType = (s: string): s is EntityType => (ENTITY_TYPES as string[]).includes(s);

export const HIGH_OP = 80;
export const LOW_OP = 25;
export const FONT_SIZE_PX = 16;

export const WIDE_LAYOUT_PX = 900; // mirrors @media (min-width: 900px) in styles.css

export const DEFAULT_LIMIT_N = 10;
export const MAX_LEVEL_COUNT = 4;
export const COMPLETE_YEAR = 1950;
export const LATEST_YEAR = new Date().getFullYear(); // == backend FINAL_YEAR: last year in EraRec yearly records

export const ORCID_REDIRECT_URI = `${PUBLIC_ORIGIN}/callback`;
export const ORCID_AUTH_URL = 'https://orcid.org/oauth/authorize';
export const ORCID_TOKEN_URL = 'https://orcid.org/oauth/token';
