import type { RootType } from './tree-types';
import { PUBLIC_ORIGIN } from '$env/static/public';

export const APP_NAME = 'Rankless';

export const FULL_HOST = PUBLIC_ORIGIN || 'http://127.0.0.1';
export const LAST_MOD = '2025-03-21';
export const SITEMAP_STEP_SIZE = 1000;

const IS_DEV = import.meta.env.MODE == 'development';

export const BE_URL = 'http://127.0.0.1:3038/v1';
export const BE_REMOTE_URL = IS_DEV ? BE_URL : `${FULL_HOST}:3039/v1`;

export const ROOT_TYPES: RootType[] = [
	'authors',
	'institutions',
	'sources',
	'countries',
	'subfields'
];

export const HIGH_OP = 80;
export const LOW_OP = 25;
export const FONT_SIZE_PX = 16;

export const DEFAULT_LIMIT_N = 10;
export const MAX_LEVEL_COUNT = 4;
export const COMPLETE_YEAR = 1950;
export const LATEST_YEAR = new Date().getFullYear();
