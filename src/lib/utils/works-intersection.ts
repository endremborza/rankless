import { BE_REMOTE_URL } from '$lib/constants';
import type { PaginatedPaperSetResp } from '$lib/tree-types';
import type { WorkSetQuery } from '$lib/types/work-set';

// Encode a CNF query into the path: clauses joined by '/', a clause is `etype:id,id,...`.
function encodeSpec(query: WorkSetQuery): string {
	return query
		.filter((c) => c.ids.length > 0)
		.map((c) => `${c.etype}:${c.ids.map(encodeURIComponent).join(',')}`)
		.join('/');
}

// Fetch the intersection of entity work-sets, ranked by citations and capped at `n`. Returns
// null on any backend rejection (malformed/unknown etype → 4xx, or "too broad" → 422); the empty
// query short-circuits without a request.
export async function fetchWorkIntersection(
	query: WorkSetQuery,
	n = 200
): Promise<PaginatedPaperSetResp | null> {
	const spec = encodeSpec(query);
	if (spec === '') return null;
	const resp = await fetch(`${BE_REMOTE_URL}/works-intersect/${spec}?n=${n}`);
	if (!resp.ok) return null;
	return (await resp.json()) as PaginatedPaperSetResp;
}
