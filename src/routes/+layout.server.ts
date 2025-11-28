import type { LayoutServerLoad } from './$types';
export const trailingSlash = 'never';

export const load: LayoutServerLoad = async ({ locals }) => {
	return {
		user: locals.user,
		surveyShouldPrompt: locals.surveyShouldPrompt
	};
};
