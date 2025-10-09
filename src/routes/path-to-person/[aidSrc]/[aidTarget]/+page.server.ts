import type { PageServerLoad } from './$types';


export const ssr = true;

export const load: PageServerLoad = async ({ params }) => {
	let srcAid: string = params.aidSrc ?? '';
	let targetAid: string = params.aidTarget ?? '';
	return { srcAid, targetAid }
};

