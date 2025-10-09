import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

export const ssr = true;
export const load: PageServerLoad = async () => {
	redirect(301, '/path-to-person/src/target')
};

