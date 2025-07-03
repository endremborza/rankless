import type { EntityType, RootType } from './tree-types';
import { PUBLIC_ORIGIN, PUBLIC_BACKEND_URL } from '$env/static/public';

export const APP_NAME = 'Rankless';

export const FULL_HOST = PUBLIC_ORIGIN;
export const SITEMAP_STEP_SIZE = 1000;
export const ENTITY_SITEMAP_STEP_SIZE = 40000;

export const BE_URL = 'http://127.0.0.1:3038/v1';
export const BE_REMOTE_URL = `${PUBLIC_BACKEND_URL}/v1`;

export const ROOT_TYPES: RootType[] = [
	'authors',
	'institutions',
	'sources',
	'countries',
	'subfields'
];

export const ENTITY_TYPES: EntityType[] = ['topics', 'works', 'qs', ...ROOT_TYPES];

export const HIGH_OP = 80;
export const LOW_OP = 25;
export const FONT_SIZE_PX = 16;

export const DEFAULT_LIMIT_N = 10;
export const MAX_LEVEL_COUNT = 4;
export const COMPLETE_YEAR = 1950;
export const LATEST_YEAR = new Date().getFullYear();
