import type { ParamMatcher } from '@sveltejs/kit';

import { SLUG } from '$lib/utils/game-geo';

export const match: ParamMatcher = (param) => param === SLUG;
