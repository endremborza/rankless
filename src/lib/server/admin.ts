import { env } from '$env/dynamic/private';

// Admins are configured out-of-band via the ADMIN_ORCIDS env var (comma-separated bare
// ORCIDs). Kept server-side only — never trust a client-supplied admin claim.
function normalize(orcid: string): string {
	return orcid.trim().replace(/^https?:\/\/orcid\.org\//, '');
}

let cached: Set<string> | null = null;

function adminOrcids(): Set<string> {
	if (!cached) {
		cached = new Set(
			(env.ADMIN_ORCIDS ?? '')
				.split(',')
				.map(normalize)
				.filter((o) => o.length > 0)
		);
	}
	return cached;
}

export function isAdmin(orcid: string | null | undefined): boolean {
	return !!orcid && adminOrcids().has(normalize(orcid));
}
