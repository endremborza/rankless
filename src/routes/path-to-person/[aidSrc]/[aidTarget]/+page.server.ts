import type { PageServerLoad } from './$types';

export const ssr = true;

export const load: PageServerLoad = async ({ params }) => {
	return {
		srcAid: params.aidSrc,
		targetAid: params.aidTarget
	};
};
