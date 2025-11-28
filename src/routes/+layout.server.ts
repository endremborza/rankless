import type { LayoutServerLoad } from './$types';
export const trailingSlash = 'never';

export const load: LayoutServerLoad = async ({ locals, url }) => {
	console.log("LAYOUT SERVER LOAD RUNNING", url);
	return {
		user: locals.user,
		surveyShouldPrompt: locals.surveyShouldPrompt && !url.pathname.startsWith('/survey')
	};
};
