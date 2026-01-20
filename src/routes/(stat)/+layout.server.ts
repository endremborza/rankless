import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ locals, url }) => {
	return {
		user: locals.user,
		surveyShouldPrompt: locals.surveyShouldPrompt && !url.pathname.startsWith('/survey')
	};
};
