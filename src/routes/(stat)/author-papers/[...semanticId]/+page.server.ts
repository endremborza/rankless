import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import type { View, PaperProfileResp } from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { BE_URL } from '$lib/constants';
import { pluralize } from '$lib/text-format-util';

export const ssr = true;

export const load: PageServerLoad = async ({ params }) => {
	const semanticId = params.semanticId;
	const urlFriendlySemId = tf.urlFriendlify(semanticId);
	const [view, profile]: [View, PaperProfileResp | null] = await Promise.all([
		fetch(`${BE_URL}/views/authors/${urlFriendlySemId}`)
			.then((res) => res.json())
			.catch(() => error(404, 'Not found')),
		fetch(`${BE_URL}/paper-profile/${urlFriendlySemId}`)
			.then((res) => res.json())
			.catch(() => null),
	]);
	if (!view) error(404, 'Not found');

	return {
		name: view.name,
		profile,
		semanticId,
		paperText: pluralize('paper', view.papers),
		citeText: pluralize('indexed citation', view.citations)
	};
};
