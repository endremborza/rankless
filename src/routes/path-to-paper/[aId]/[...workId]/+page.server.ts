import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import * as tf from '$lib/tree-functions';
import { BE_URL } from '$lib/constants';

export const ssr = true;

export const load: PageServerLoad = async ({ params }) => {
	const urlFriendlySemId = tf.urlFriendlify(params.workId);
	const pathUrl = `${BE_URL}/path-to-paper/${params.aId}/${urlFriendlySemId}/false`;
	const resp = await fetch(pathUrl)
		.then((res) => res.json())
		.catch(() => error(404, 'Not found'));
	if (resp == undefined) {
		error(404, 'Not found');
	}
	return resp;
};
