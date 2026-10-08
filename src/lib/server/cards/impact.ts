import type { PaperOut, PaperProfileResp, PaperSetResp } from '$lib/wire/rankless_server/responses';
import { error } from '@sveltejs/kit';
import { BE_URL } from '$lib/constants';
import { pluralize } from '$lib/text-format-util';
import { encodeSemanticId } from '$lib/tree-functions';
import { computeSeen, type SeenMap } from '$lib/utils/dag-builder';
import { computeImpactSummary, nobelPhrase, prestigiousPhrase } from '$lib/utils/impact-summary';
import { ACCENT } from '$lib/utils/cards';
import { layoutImpact, type ChipPaper } from '$lib/utils/impact-card';
import {
	buildPaperMap,
	getPaperHighlights,
	hasNobelCoauthor,
	highlightLabel,
	htmlToText,
	isAuthored,
	resolveSourceName
} from '$lib/utils/paper-helpers';
import ImpactCard from '$lib/components/cards/ImpactCard.svelte';
import { beJson, CARD_SPEC, idsParam, type CardKind } from './kind';

const MAX_TOP = CARD_SPEC.impact.params.hits.max;
const MAX_BOTTOM = 4;

const BADGE_INKS: Record<string, { fill: string; ink: string }> = {
	hit: { fill: '#e8f4fb', ink: ACCENT },
	prestigious: { fill: '#fdf3e0', ink: '#b5731a' },
	nobel: { fill: '#f5e9fb', ink: '#7d0082' }
};

type Profile = PaperSetResp & { byWid: Record<number, PaperOut>; authorDmId: string };

// The hit papers that build on an author's work, as the page's impact DAG reads it: its roots are
// the citing hits, the author's papers under them the ones they cite. `hits` picks up to MAX_TOP
// citing hits by semantic id (default the top MAX_TOP by paper score); the author's papers they
// cite sit below, at most MAX_BOTTOM, each citing hit keeping at least one.
export const impact: CardKind = {
	component: ImpactCard,
	async load({ semanticId, params, view, fetch }) {
		if (!view) error(404, 'no such card');
		const ids = idsParam(params, 'hits', MAX_TOP);
		const resp = await beJson<PaperProfileResp>(
			fetch,
			`${BE_URL}/paper-profile/${encodeSemanticId(semanticId)}`
		);
		const profile: Profile = {
			...resp.papers,
			byWid: buildPaperMap(resp.papers.papers),
			authorDmId: String(view.dmId)
		};
		const seen = computeSeen(resp.dag);
		const own = (wid: number) =>
			!!profile.byWid[wid] && isAuthored(profile.byWid[wid], semanticId, profile.entityAtts);
		const wids = Object.keys(seen)
			.map(Number)
			.filter((w) => profile.byWid[w]);
		const rank = (a: number, b: number) => byRank(profile.byWid[a], profile.byWid[b]);
		const roots = wids
			.filter((w) => !own(w) && [...seen[w].parents].every((p) => p === 0))
			.sort(rank);
		if (roots.length === 0) error(404, 'card unavailable');
		const top = ids.length
			? [...new Set(ids)].map(
					(id) => roots.find((w) => profile.byWid[w].hitSemId === id) ?? error(404, 'bad hits')
				)
			: roots.slice(0, MAX_TOP);

		const citers = new Map<number, number[]>();
		top.forEach((t, ti) => {
			for (const w of citedOwn(seen, t, own)) citers.set(w, [...(citers.get(w) ?? []), ti]);
		});
		const bottom = pickCited(citers, top.length, rank);
		const links = bottom.flatMap((w, bi) => citers.get(w)!.map((ti): [number, number] => [ti, bi]));

		const name = htmlToText(view.name);
		const summary = computeImpactSummary(
			wids.filter((w) => !own(w)),
			profile.byWid,
			profile.entityAtts,
			profile.authorsMeta,
			profile.authorDmId
		);
		return {
			props: {
				layout: layoutImpact(
					top.map((w) => chipPaper(profile.byWid[w], profile)),
					bottom.map((w) => chipPaper(profile.byWid[w], profile)),
					links
				),
				summary: [
					`${pluralize('hit paper', summary.hitCount)} citing`,
					summary.nobelCount > 0 ? nobelPhrase(summary.nobelCount) : '',
					summary.prestigiousCount > 0 ? prestigiousPhrase(summary.prestigiousCount) : ''
				]
					.filter(Boolean)
					.join(', '),
				ownLabel: `${name}'s papers they cite`
			},
			caption: `The most-cited papers of their fields that build on ${name}'s work`
		};
	}
};

function byRank(a: PaperOut, b: PaperOut): number {
	return (b.score ?? 0) - (a.score ?? 0) || b.citations - a.citations || a.wid - b.wid;
}

// The author's papers under a citing paper, through any papers between them.
function citedOwn(seen: SeenMap, root: number, own: (wid: number) => boolean): Set<number> {
	const out = new Set<number>();
	const visited = new Set<number>();
	const stack = [...seen[root].children];
	while (stack.length) {
		const w = stack.pop()!;
		if (visited.has(w)) continue;
		visited.add(w);
		if (own(w)) out.add(w);
		else stack.push(...(seen[w]?.children ?? []));
	}
	return out;
}

// First the most shared cited paper of every citing chip that has none yet, then the most shared
// of the rest.
function pickCited(
	citers: Map<number, number[]>,
	nTop: number,
	rank: (a: number, b: number) => number
): number[] {
	const shared = (w: number) => citers.get(w)!.length;
	const candidates = [...citers.keys()].sort((a, b) => shared(b) - shared(a) || rank(a, b));
	const chosen: number[] = [];
	for (let ti = 0; ti < nTop; ti++) {
		if (chosen.some((w) => citers.get(w)!.includes(ti))) continue;
		const w = candidates.find((c) => citers.get(c)!.includes(ti));
		if (w !== undefined && chosen.length < MAX_BOTTOM) chosen.push(w);
	}
	for (const c of candidates) if (chosen.length < MAX_BOTTOM && !chosen.includes(c)) chosen.push(c);
	return chosen;
}

function chipPaper(p: PaperOut, profile: Profile): ChipPaper {
	const highlights = getPaperHighlights(p, undefined, profile.entityAtts);
	const prestigious = highlights.some((h) => h.key === 'prestigious');
	if (hasNobelCoauthor(p, profile.authorsMeta, profile.authorDmId))
		highlights.push({ key: 'nobel' });
	return {
		title: htmlToText(p.name),
		year: p.year,
		journal: prestigious ? '' : resolveSourceName(p.source, profile.entityAtts),
		badges: highlights.map((h) => ({ ...BADGE_INKS[h.key], label: highlightLabel(h) }))
	};
}
