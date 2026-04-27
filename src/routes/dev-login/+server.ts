import type { RequestHandler } from '@sveltejs/kit';
import { error } from '@sveltejs/kit';
import { dev } from '$app/environment';
import { setSession } from '$lib/server/session';
import { LedgerDb } from '$lib/server/db';

/**
 * Dev-only: set a session directly without going through ORCID OAuth.
 * Only available when NODE_ENV=development (SvelteKit dev mode).
 *
 * Usage:
 *   /dev-login?orcid=0000-0002-8804-4520&name=Test&returnTo=/
 *
 *
 * To test owner features on a large author profile:
 *   /dev-login?orcid=0000-0002-8804-4520&name=Test&semanticId=<target-semid>&returnTo=/authors/<target-semid>
 *
 * The semanticId param overrides the ORCID → profile lookup, so you can point
 * your session at any profile without needing a real ORCID match in the pipeline.
 */
const TEST_ORCID = '0000-0003-4255-0492'
export const GET: RequestHandler = (event) => {
	if (!dev) error(404, 'Not found');
	const p = event.url.searchParams;
	let orcid = p.get('orcid') ?? TEST_ORCID;
	LedgerDb.pinOwner(orcid, 'login');
	return setSession(
		event,
		{
			orcid,
			name: p.get('name') ?? 'Robert Langer',
			semanticId: p.get('semanticId') ?? 'robert-langer'
		},
		p.get('returnTo') ?? '/'
	);
};
