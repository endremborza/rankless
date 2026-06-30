import type { EntityType, RelTypes, RootType } from './tree-types';
import { PUBLIC_ORIGIN, PUBLIC_BACKEND_URL } from '$env/static/public';

export const APP_NAME = 'Rankless';

// Brand proof-points. The home card pulls live figures from the backend /counts endpoint; this is
// the fallback shown only if that fetch fails, so it stays roughly current but approximate.
export const BRAND_TAGLINE = 'Explore academic impact beyond rankings';
export const BRAND_STATS = ['~90M papers', '1.9B citations', 'every field'];

export const FULL_HOST = PUBLIC_ORIGIN;
export const SITEMAP_STEP_SIZE = 8192;
export const ENTITY_SITEMAP_STEP_SIZE = 40000;

export const BE_URL = 'http://127.0.0.1:3038/v1';
export const BE_REMOTE_URL = `${PUBLIC_BACKEND_URL}/v1`;

export const SURVEY_LOG_PATH = '/tmp/survey-logs.jsonl';

export const ROOT_TYPES: RootType[] = [
	'authors',
	'institutions',
	'sources',
	'countries',
	'subfields',
	'hit-papers'
];

export const REL_TYPES: RelTypes[] = [
	'paper-fields',
	'citing-fields',
	'paper-topics',
	'collab-nation',
	'paper-journals',
	'paper-authors'
];

export const ENTITY_TYPES: EntityType[] = ['topics', 'works', 'qs', ...ROOT_TYPES];

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
