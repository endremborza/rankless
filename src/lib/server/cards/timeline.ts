import { error } from '@sveltejs/kit';
import type * as tt from '$lib/tree-types';
import {
	buildCoauthors,
	sortCoauthors,
	type CoAuthor,
	type SortMode
} from '$lib/utils/author-timeline';
import TimelineCard from '$lib/components/cards/TimelineCard.svelte';
import { CARD_SPEC, idsParam, intParam, oneOf, type CardKind } from './kind';
import { loadAllWorks } from './works';

export const SORT_WORDS: Record<SortMode, string> = {
	first: 'first collaboration',
	recent: 'latest collaboration',
	count: 'most shared papers'
};
const P = CARD_SPEC.timeline.params;

// The author's co-authors placed by the years of their shared papers, the page's timeline view:
// `min` shared papers, `sort` first/recent/count, the top `n` rows, and `with` co-authors always
// shown and highlighted.
export const timeline: CardKind = {
	component: TimelineCard,
	async load({ semanticId, params, fetch }) {
		const withIds = idsParam(params, 'with', P.with.max);
		const min = intParam(params, 'min', P.min.default, 1, 10000);
		const sort = oneOf(params, 'sort', P.sort.options as SortMode[], P.sort.default as SortMode);
		const n = intParam(params, 'n', P.n.default, 1, P.n.max);
		if (withIds.length > n) error(404, 'more `with` than rows');

		const works = await loadAllWorks(fetch, semanticId);
		const all = buildCoauthors(works.papers, works.entityAtts, works.discAuthorNames, semanticId);
		const semId = (c: CoAuthor) => coauthorSemId(c, works.entityAtts);
		const highlight = all.filter((c) => withIds.includes(semId(c))).map((c) => c.key);
		if (highlight.length < withIds.length) error(404, 'unknown co-author');

		const rows = pickRows(sortCoauthors(all, sort), new Set(highlight), min, n);
		if (rows.length === 0) error(404, 'card unavailable');
		return {
			props: { rows, highlight },
			caption: `Co-authors by year of shared papers · at least ${min} shared paper${min === 1 ? '' : 's'} · sorted by ${SORT_WORDS[sort]}`
		};
	}
};

function coauthorSemId(c: CoAuthor, entityAtts: tt.EntityAttsForLinks): string {
	return c.key[0] === 'F' ? (entityAtts.authors?.[c.key.slice(1)]?.semantic_id ?? '') : '';
}

// The first `n` sorted rows that clear `min`, with every highlighted row kept in its sorted place.
function pickRows(sorted: CoAuthor[], highlight: Set<string>, min: number, n: number) {
	let free = n - highlight.size;
	return sorted.filter((c) => {
		if (highlight.has(c.key)) return true;
		if (c.count < min || free === 0) return false;
		free--;
		return true;
	});
}
