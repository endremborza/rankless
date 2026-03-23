import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import type { View, PaperProfileResp, SearchResult, AuthorPeersResp } from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { BE_URL } from '$lib/constants';
import { pluralize } from '$lib/text-format-util';
import { PaperDb } from '$lib/server/db';
import type { AuthorMergeRequest } from '$lib/tree-types';

export const ssr = true;

export const load: PageServerLoad = async ({ params, locals }) => {
	const semanticId = params.semanticId;
	const urlFriendlySemId = tf.urlFriendlify(semanticId);
	const [view, profile, peersData]: [View, PaperProfileResp | null, AuthorPeersResp | null] =
		await Promise.all([
			fetch(`${BE_URL}/views/authors/${urlFriendlySemId}`)
				.then((res) => res.json())
				.catch(() => error(404, 'Not found')),
			fetch(`${BE_URL}/paper-profile/${urlFriendlySemId}`)
				.then((res) => res.json())
				.catch(() => null),
			fetch(`${BE_URL}/author-peers/${urlFriendlySemId}`)
				.then((res) => (res.ok ? res.json() : null))
				.catch(() => null)
		]);
	if (!view) error(404, 'Not found');

	let isOwner = false;
	let disownedWids: number[] = [];
	let claimedDois: string[] = [];
	let mergedPairs: [number, number][] = [];
	let authorMergeRequests: AuthorMergeRequest[] = [];

	if (locals.user) {
		// Use cached semanticId when available; fall back to live ORCID lookup
		// TODO: why would it not be available?
		if (locals.user.semanticId) {
			isOwner = locals.user.semanticId === semanticId;
		} else {
			try {
				const orcidResp: SearchResult = await fetch(
					`${BE_URL}/orcid/${locals.user.orcid}`
				).then((r) => r.json());
				isOwner = orcidResp.semanticId === semanticId;
			} catch {
				// ORCID lookup failed — not an owner
			}
		}

		if (isOwner) {
			disownedWids = PaperDb.getDisownedWids(locals.user.orcid);
			claimedDois = PaperDb.getClaimedDois(locals.user.orcid);
			mergedPairs = PaperDb.getMergedPairs(locals.user.orcid);
			authorMergeRequests = PaperDb.getAuthorMergeRequests(locals.user.orcid);
		}
	}

	const hasOrcid = view.meta?.hasOrcid === '1';

	return {
		name: view.name,
		profile,
		peersData,
		semanticId,
		paperText: pluralize('paper', view.papers),
		citeText: pluralize('indexed citation', view.citations),
		isOwner,
		hasOrcid,
		disownedWids,
		claimedDois,
		mergedPairs,
		authorMergeRequests
	};
};
