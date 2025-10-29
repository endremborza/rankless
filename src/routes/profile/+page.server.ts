import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	if (!locals.user) {
		throw new Response('Unauthorized', { status: 302, headers: { Location: '/' } });
	}
	return { user: locals.user };
};
