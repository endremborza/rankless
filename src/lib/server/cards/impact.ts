import type { ImpactHighlightsResp } from '$lib/wire/rankless_server/highlights';
import { error } from '@sveltejs/kit';
import { BE_URL } from '$lib/constants';
import { pluralize } from '$lib/text-format-util';
import { encodeSemanticId } from '$lib/tree-functions';
import { ACCENT } from '$lib/utils/cards';
import { layoutImpact, type ChipPaper } from '$lib/utils/impact-card';
import {
	citedLayer,
	highlightsView,
	marks,
	ownCard,
	type Mark,
	type PaperCard
} from '$lib/utils/impact-highlights';
import { htmlToText } from '$lib/utils/paper-helpers';
import ImpactCard from '$lib/components/cards/ImpactCard.svelte';
import { beJson, CARD_SPEC, idsParam, type CardKind } from './kind';

const MAX_TOP = CARD_SPEC.impact.params.hits.max;
const MAX_BOTTOM = 4;

const PRESTIGIOUS = { fill: '#fdf3e0', ink: '#b5731a' };
const AWARD = { fill: '#f5e9fb', ink: '#7d0082' };
const INKS: Record<NonNullable<Mark['kind']>, { fill: string; ink: string }> = {
	hit: { fill: '#e8f4fb', ink: ACCENT },
	apex: PRESTIGIOUS,
	institution: PRESTIGIOUS,
	laureate: AWARD,
	star: AWARD
};

// The author's impact highlights, in the order they were picked: `hits` picks up
// to MAX_TOP of them by semantic id (default the first MAX_TOP); the author's papers they cite sit
// below, at most MAX_BOTTOM, each top chip keeping at least one.
export const impact: CardKind = {
	component: ImpactCard,
	async load({ semanticId, params, view, fetch }) {
		if (!view) error(404, 'no such card');
		const ids = idsParam(params, 'hits', MAX_TOP);
		const resp = await beJson<ImpactHighlightsResp>(
			fetch,
			`${BE_URL}/impact-highlights/${encodeSemanticId(semanticId)}`
		);
		const rows = highlightsView(resp);
		if (rows.length === 0) error(404, 'card unavailable');
		const top = ids.length
			? [...new Set(ids)].map(
					(id) => rows.find((r) => r.paper.hitSemId === id) ?? error(404, 'bad hits')
				)
			: rows.slice(0, MAX_TOP);

		const bottom = citedLayer(top, MAX_BOTTOM);

		const name = htmlToText(view.name);
		return {
			props: {
				layout: layoutImpact(
					top.map(chip),
					bottom.papers.map((p) => chip(ownCard(p, resp))),
					bottom.links
				),
				summary: `Picked from ${pluralize('independent citing paper', resp.totals.independent)}`,
				ownLabel: `${name}'s papers they cite`
			},
			caption: `Highlights of the independent papers building on ${name}'s work`
		};
	}
};

// A chip's badges are its card's marks; a marked journal shows no journal line.
function chip(card: PaperCard): ChipPaper {
	const [journal] = card.facts;
	return {
		title: htmlToText(card.paper.name),
		year: card.paper.year,
		journal: journal.kind ? '' : journal.label,
		badges: marks(card).map((m) => ({ ...INKS[m.kind!], label: m.label }))
	};
}
