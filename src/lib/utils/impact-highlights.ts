import type { PaperAuthorMeta, PaperOut, PaperSetResp } from '$lib/wire/rankless_server/responses';
import { METHODOLOGY } from '$lib/wire/rankless_server/responses';
import type {
	Badge,
	HighlightKind,
	ImpactHighlightsResp
} from '$lib/wire/rankless_server/highlights';
import type { EntityAttsForLinks } from '$lib/wire/rankless_trees/io';
import type { RootType } from '$lib/tree-types';
import { BE_REMOTE_URL } from '$lib/constants';
import { encodeSemanticId, getEntityPath } from '$lib/tree-functions';
import { pluralize } from '$lib/text-format-util';
import { tierLabels } from '$lib/peers-utils';
import { buildPaperMap, resolveAuthors, resolveSourceName } from '$lib/utils/paper-helpers';

// A piece of a paper card; `kind` marks it as what makes the paper a highlight.
export type Mark = { label: string; href?: string; title?: string; kind?: HighlightKind };
// A paper as a card: its journal and citations, the people it names (the marked ones, else its
// first author) and how many more wrote it, and its marked institutions.
export type PaperCard = {
	paper: PaperOut;
	facts: Mark[];
	people: Mark[];
	others: number;
	institutions: Mark[];
};
export type PaperRow = PaperCard & { cites: PaperOut[] };
// The author's papers under the citing rows; `links` pairs a row's index with a paper's index.
export type CitedLayer = { papers: PaperOut[]; links: [number, number][] };

type BadgeOf<K extends Badge['kind']> = Extract<Badge, { kind: K }>;

const STAR_TIER = tierLabels(METHODOLOGY.ladderPctBands).at(-1);

// Citations over the bar of a paper's field and year, as the page words a multiple.
export function multipleLabel(m: number): string {
	return m >= 10 ? `${Math.round(m)}×` : `${m.toFixed(1)}×`;
}

// The author's impact highlights, null on a failed request. Pages call it from the
// browser only, so rendering a page never computes them.
export function fetchImpactHighlights(semanticId: string): Promise<ImpactHighlightsResp | null> {
	return fetch(`${BE_REMOTE_URL}/impact-highlights/${encodeSemanticId(semanticId)}`)
		.then((r) => (r.ok ? (r.json() as Promise<ImpactHighlightsResp>) : null))
		.catch(() => null);
}

// The citing papers in pick order, each a card marked by its badges.
export function highlightsView(resp: ImpactHighlightsResp): PaperRow[] {
	const byWid = buildPaperMap(resp.papers.papers);
	return resp.highlights.flatMap((h) => {
		const paper = byWid[h.wid];
		if (!paper) return [];
		const cites = h.cites.map((w) => byWid[w]).filter((p): p is PaperOut => !!p);
		return [{ ...citingCard(paper, h.badges, resp.papers), cites }];
	});
}

export function citingCard(paper: PaperOut, badges: Badge[], set: PaperSetResp): PaperCard {
	const atts = set.entityAtts;
	const of = <K extends Badge['kind']>(kind: K) =>
		badges.filter((b): b is BadgeOf<K> => b.kind === kind);
	const hit = of('hit')[0];
	const people = [
		...of('laureate').map((b) =>
			entity(
				'authors',
				b.author,
				atts,
				'laureate',
				laureateTitle(set.authorsMeta[String(b.author)])
			)
		),
		...of('star').map((b) =>
			entity(
				'authors',
				b.author,
				atts,
				'star',
				`${STAR_TIER} in ${name('subfields', b.field, atts)}`
			)
		)
	];
	const named = people.length > 0 ? people : firstAuthor(paper, set);
	return {
		paper,
		facts: [
			journal(paper, atts, of('apex').length > 0),
			citations(
				paper,
				!!hit,
				hit ? `${multipleLabel(hit.multiple)} the bar of its field and year` : undefined
			)
		],
		people: named,
		others: paper.authorCount - named.length,
		institutions: of('institution').map((b) =>
			entity(
				'institutions',
				b.institution,
				atts,
				'institution',
				pluralize('independent citing paper', b.papers)
			)
		)
	};
}

// The author's own paper: its journal marked when one of `resp`'s apex journals, its citations when
// a hit.
export function ownCard(paper: PaperOut, resp: ImpactHighlightsResp): PaperCard {
	const atts = resp.papers.entityAtts;
	return {
		paper,
		facts: [
			journal(paper, atts, resp.apexSources.includes(paper.source)),
			citations(paper, !!paper.isHit)
		],
		people: [],
		others: 0,
		institutions: []
	};
}

// A paper's own page when it is a hit paper, else its DOI.
export function paperHref(paper: PaperOut): string | undefined {
	if (paper.hitSemId) return entityHref('hit-papers', paper.hitSemId);
	return paper.doi ? `https://doi.org/${paper.doi}` : undefined;
}

// The marked pieces of a card.
export function marks(card: PaperCard): Mark[] {
	return [...card.facts, ...card.people, ...card.institutions].filter((m) => m.kind);
}

// At most `max` of the papers the rows cite: first, for each row none of the chosen covers, its
// most shared paper, then the most shared of the rest; ties go to the higher paper score.
export function citedLayer(rows: { cites: PaperOut[] }[], max: number): CitedLayer {
	const byWid = new Map(rows.flatMap((r) => r.cites).map((p) => [p.wid, p]));
	const citers = new Map<number, number[]>();
	rows.forEach((r, ri) => {
		for (const p of r.cites) citers.set(p.wid, [...(citers.get(p.wid) ?? []), ri]);
	});
	const shared = (w: number) => citers.get(w)!.length;
	const candidates = [...citers.keys()].sort(
		(a, b) => shared(b) - shared(a) || byRank(byWid.get(a)!, byWid.get(b)!)
	);
	const chosen: number[] = [];
	rows.forEach((_, ri) => {
		if (chosen.length >= max || chosen.some((w) => citers.get(w)!.includes(ri))) return;
		const w = candidates.find((c) => citers.get(c)!.includes(ri));
		if (w !== undefined) chosen.push(w);
	});
	for (const c of candidates) if (chosen.length < max && !chosen.includes(c)) chosen.push(c);
	return {
		papers: chosen.map((w) => byWid.get(w)!),
		links: chosen.flatMap((w, pi) => citers.get(w)!.map((ri): [number, number] => [ri, pi]))
	};
}

// The layer's papers ordered by the mean index of the rows citing them, so its curves cross
// little under rows kept in their own order.
export function byCiterOrder(layer: CitedLayer): CitedLayer {
	const mean = layer.papers.map((_, pi) => {
		const at = layer.links.filter(([, p]) => p === pi).map(([r]) => r);
		return at.reduce((a, b) => a + b, 0) / at.length;
	});
	const order = layer.papers.map((_, pi) => pi).sort((a, b) => mean[a] - mean[b] || a - b);
	const moved = order.map((_, i) => order.indexOf(i));
	return {
		papers: order.map((pi) => layer.papers[pi]),
		links: layer.links.map(([r, p]): [number, number] => [r, moved[p]])
	};
}

function journal(paper: PaperOut, atts: EntityAttsForLinks, marked: boolean): Mark {
	const att = atts.sources?.[String(paper.source)];
	return {
		label: resolveSourceName(paper.source, atts) || 'Unknown venue',
		href: entityHref('sources', att?.semantic_id),
		kind: marked ? 'apex' : undefined
	};
}

function citations(paper: PaperOut, hit: boolean, title?: string): Mark {
	return { label: pluralize('citation', paper.citations), title, kind: hit ? 'hit' : undefined };
}

function entity(
	rootType: RootType,
	id: number,
	atts: EntityAttsForLinks,
	kind: HighlightKind,
	title: string
): Mark {
	const att = atts[rootType]?.[String(id)];
	return { label: att?.name ?? '', href: entityHref(rootType, att?.semantic_id), kind, title };
}

function name(etype: string, id: number, atts: EntityAttsForLinks): string {
	return atts[etype]?.[String(id)]?.name ?? '';
}

function firstAuthor(paper: PaperOut, set: PaperSetResp): Mark[] {
	return resolveAuthors(paper, set.entityAtts, set.discAuthorNames)
		.slice(0, 1)
		.map((a) => ({ label: a.name, href: a.url }));
}

function laureateTitle(meta?: PaperAuthorMeta): string {
	return meta?.year ? `Nobel laureate, ${meta.year}` : 'Nobel laureate';
}

function byRank(a: PaperOut, b: PaperOut): number {
	return (b.score ?? 0) - (a.score ?? 0) || b.citations - a.citations || a.wid - b.wid;
}

function entityHref(rootType: RootType, semanticId?: string): string | undefined {
	return semanticId ? getEntityPath(rootType, semanticId) : undefined;
}
