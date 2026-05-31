import { BE_URL } from '$lib/constants';
import type { RootType } from '$lib/tree-types';
import type { PageServerLoad } from './$types';
import { redirect } from '@sveltejs/kit';

const LETTER_MAP: Record<string, RootType> = {
	A: 'authors',
	I: 'institutions'
};

export const load: PageServerLoad = async ({ params }) => {
	let id: string = params.oaId;
	let rootType = LETTER_MAP[id[0]];
	if (rootType == undefined) {
		redirect(302, `https://openalex.org/${id}`);
	}
	let idNum = id.slice(1);
	let url = `${BE_URL}/sem-id-via-oa/${rootType}/${idNum}`;
	let semId = await fetch(url)
		.then((resp) => resp.json())
		.then((jsRes: [number | undefined]) => {
			let candidate = jsRes[0];
			if (candidate == undefined) {
				redirect(302, `https://openalex.org/${id}`);
			}
			return candidate;
		});
	redirect(302, `/${rootType}/${semId}`);
};
