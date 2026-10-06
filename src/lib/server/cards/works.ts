import type { PaginatedPaperSetResp } from '$lib/wire/rankless_server/responses';
import { BE_URL } from '$lib/constants';
import { mergeWorks, WORKS_PAGE_SIZE, worksPageUrl, type Works } from '$lib/utils/works-loader';
import { beJson } from './kind';

// Every paper of an author, in the works table's order: the first page names the total, the rest
// are fetched concurrently and merged in slice order.
export async function loadAllWorks(fetchFn: typeof fetch, semanticId: string): Promise<Works> {
	const page = (from: number) =>
		beJson<PaginatedPaperSetResp>(fetchFn, worksPageUrl(BE_URL, semanticId, from, WORKS_PAGE_SIZE));
	const first = await page(0);
	const froms: number[] = [];
	for (let from = WORKS_PAGE_SIZE; from < first.totalPapers; from += WORKS_PAGE_SIZE)
		froms.push(from);
	return mergeWorks(...[first, ...(await Promise.all(froms.map(page)))].map((p) => p.resp));
}
