import type { CountsResponse } from '$lib/wire/rankless_server/responses';
import { BE_URL, BRAND_STATS } from '$lib/constants';
import { formatNumber } from '$lib/text-format-util';
import { renderSvgComponent } from '$lib/server/render';
import { rasterizeSvg } from '$lib/server/card-raster';
import HomeCard from '$lib/components/HomeCard.svelte';

// The homepage card carries live figures from /counts, so it renders fresh per request (a render is
// cheap and crawler hits are rare, which also keeps the numbers current with no cache to invalidate).
export async function getHomeCardPng(fetchFn: typeof fetch): Promise<Buffer> {
	const stats = await fetchHomeStats(fetchFn);
	const svg = renderSvgComponent(HomeCard, { stats });
	return rasterizeSvg(svg);
}

// Live proof-points from the backend; any failure falls back to the brand constants so the card,
// being an OG endpoint, never breaks. "every field" stays qualitative (252 subfields = all of science).
async function fetchHomeStats(fetchFn: typeof fetch): Promise<string[]> {
	try {
		const res = await fetchFn(`${BE_URL}/counts`);
		if (!res.ok) return BRAND_STATS;
		const counts: CountsResponse = await res.json();
		if (!counts?.total_works || !counts?.total_citations) return BRAND_STATS;
		return [
			`${formatNumber(counts.total_works)} papers`,
			`${formatNumber(counts.total_citations)} citations`,
			'every field'
		];
	} catch {
		return BRAND_STATS;
	}
}
