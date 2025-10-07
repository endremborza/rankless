import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { BE_URL } from '$lib/constants';


export const ssr = true;

export const load: PageServerLoad = async ({ params, url }) => {
	let authorId: string = params.aId;
	let doi: string = params.workId;
	let urlFriendlySemId = tf.urlFriendlify(doi);
	let pathUrl = `${BE_URL}/path-to-paper/${authorId}/${urlFriendlySemId}`

	const resp = await fetch(pathUrl)
		.then((res) => res.json())
		.then((view) => view)
		.catch(() => error(404, 'Not found'));
	if (resp == undefined) {
		error(404, 'Not found');
	}
	return resp
};

