import type { PaperProfileResp } from '$lib/wire/rankless_server/responses';
import { error } from '@sveltejs/kit';
import { BE_URL } from '$lib/constants';
import { encodeSemanticId } from '$lib/tree-functions';
import { htmlToText, isAuthored, resolveSourceName } from '$lib/utils/paper-helpers';
import { pluralize } from '$lib/text-format-util';
import {
	computeYearRates,
	getFigureBasis,
	getVisInds,
	rainbowPapers,
	type RainbowSort
} from '$lib/utils/paper-rainbow';
import PapersCard, { type PaperRow } from '$lib/components/cards/PapersCard.svelte';
import { beJson, CARD_SPEC, idsParam, intParam, oneOf, type CardKind } from './kind';

const P = CARD_SPEC.papers.params;
const LIST_N = 5;

const LIST_TITLE: Record<RainbowSort, string> = {
	citations: 'Most cited',
	score: 'Highest paper score',
	year: 'Newest'
};

// An author's hit papers as the page's rainbow draws them, trajectories aligned at publication:
// `n` of them in `sort` order, `hl` (a hit semantic id, default the first) drawn on top and always
// among the lines and the list.
export const papers: CardKind = {
	component: PapersCard,
	async load({ semanticId, params, fetch }) {
		const n = intParam(params, 'n', P.n.default, 1, P.n.max);
		const sorts = P.sort.options as RainbowSort[];
		const sort = oneOf(params, 'sort', sorts, P.sort.default as RainbowSort);
		const [hlId] = idsParam(params, 'hl', P.hl.max);
		const profile = await beJson<PaperProfileResp>(
			fetch,
			`${BE_URL}/paper-profile/${encodeSemanticId(semanticId)}`
		);
		const { entityAtts } = profile.papers;
		const hits = rainbowPapers(
			profile.papers.papers.filter((p) => isAuthored(p, semanticId, entityAtts)),
			sort
		);
		if (hits.length === 0) error(404, 'card unavailable');
		const hl = hlId ? hits.findIndex((p) => p.hitSemId === hlId) : 0;
		if (hl < 0) error(404, 'bad hl');

		const inds = withPinned(getVisInds(hits, 0, n), n, hl);
		const rates = computeYearRates(hits);
		const minYear = Math.min(...inds.map((i) => hits[i].year));
		const rows: PaperRow[] = withPinned(inds, LIST_N, hl).map((i) => ({
			year: hits[i].year,
			journal: resolveSourceName(hits[i].source, entityAtts) || htmlToText(hits[i].name),
			citations: hits[i].citations,
			rate: rates[i],
			hl: i === hl
		}));
		const years = hits.map((p) => p.year);
		return {
			props: {
				basis: getFigureBasis(hits, inds, minYear, true, rates, false),
				hl,
				rows,
				listTitle: LIST_TITLE[sort],
				yearRange: [Math.min(...years), Math.max(...years)]
			},
			caption: `${inds.length < hits.length ? `${inds.length} of ` : ''}${pluralize('hit paper', hits.length)} (the top of their field and year), cumulative citations since publication`
		};
	}
};

// The first `k` of `inds`, the last swapped for `pin` when it is not among them.
function withPinned(inds: number[], k: number, pin: number): number[] {
	const top = inds.slice(0, k);
	return top.includes(pin) ? top : [...top.slice(0, k - 1), pin];
}
