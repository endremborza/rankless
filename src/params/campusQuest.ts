import type { ParamMatcher } from '@sveltejs/kit';

import { SLUG } from '$lib/utils/game-countries';

export const match: ParamMatcher = (param) => param === SLUG;
