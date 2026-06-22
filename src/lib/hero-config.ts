import type * as tt from '$lib/tree-types';
import { ROOT_TYPES } from '$lib/constants';
import { entToLink } from '$lib/tree-functions';
import { pluralize } from '$lib/text-format-util';
import {
	impactColorVar,
	productionColorVar,
	tierLabels,
	citStandingTier,
	standingLabel,
	standingPhrase
} from '$lib/peers-utils';

// Per-root-type recipe for the entity hero header. Each entity surfaces a different mix of
// stat, specialization chips, and "leader" rows — mirroring the per-type narrative in
// `+page.server.ts` getSemantifyers, so the header is meaningful for that entity kind rather
// than a one-size-fits-all layout.

export type StatVariant = 'paper' | 'cites';

export type LeaderSpec = {
	label: string;
	relType: tt.RelTypes;
	withCount?: boolean;
	n: number;
};

export type HeroSpec = {
	statVariant: StatVariant;
	// Authors: headline the total (raw) citations, with indexed/hit-paper/h-index in the sub-line.
	useRawCites?: boolean;
	showHitPapers?: boolean;
	showHIndex?: boolean;
	// Trailing sub-line note: subfields are dated to the indexed era, journals to first activity.
	sinceNote?: 'complete' | 'startYear';
	// "top X%" standing badge on the subfield chips. Off for cohorts where percentile rank is
	// uninformative (countries: the largest are top-fraction in nearly everything).
	showStandingBadge: boolean;
	leaders: LeaderSpec[];
};

export type LeaderItem = { text: string; href: string | null };
export type LeaderRow = { label: string; items: LeaderItem[] };
// A topic inside a tile. `count` is shown inline (production = papers authored); impact leaves it
// null and relies on `hover` ("X citations" / "X papers authored") for the on-hover figure.
export type HeroTopic = { name: string; count: number | null; hover: string };
// One subfield tile heading its top topics — the explicit topic↔field hierarchy. The impact side
// fills `badge` ("top X%" standing); the production side fills `count` (papers authored). A tile
// shows only the one its block uses.
export type HeroTile = {
	name: string;
	href: string | null;
	colorVar: string;
	badge: string | null;
	badgeTitle: string | null;
	count: number | null;
	topics: HeroTopic[];
};
type TopicScore = { name: string; score: number };

// Co-author / top-scholar rows share one list size: generous enough to read as a community of
// contributors rather than an elite few. The server precomputes up to 25 paper-authors per entity.
const PEOPLE_LEADER_N = 8;

export const HERO_CONFIG: Record<tt.RootType, HeroSpec> = {
	authors: {
		statVariant: 'cites',
		useRawCites: true,
		showHitPapers: true,
		showHIndex: true,
		showStandingBadge: true,
		leaders: [
			{ label: 'Co-authors', relType: 'paper-authors', n: PEOPLE_LEADER_N },
			{ label: 'Journals', relType: 'paper-journals', withCount: true, n: 5 },
			{ label: 'Partner nations', relType: 'collab-nation', n: 3 }
		]
	},
	institutions: {
		statVariant: 'cites',
		showStandingBadge: true,
		leaders: [
			{ label: 'Top scholars', relType: 'paper-authors', n: PEOPLE_LEADER_N },
			{ label: 'Journals', relType: 'paper-journals', withCount: true, n: 5 },
			{ label: 'Partner nations', relType: 'collab-nation', n: 3 }
		]
	},
	countries: {
		statVariant: 'cites',
		showStandingBadge: false,
		leaders: [
			{ label: 'Partner nations', relType: 'collab-nation', n: 3 },
			{ label: 'Cited by', relType: 'citing-fields', n: 3 }
		]
	},
	sources: {
		statVariant: 'cites',
		sinceNote: 'startYear',
		showStandingBadge: true,
		leaders: [{ label: 'Top scholars', relType: 'paper-authors', n: PEOPLE_LEADER_N }]
	},
	subfields: {
		statVariant: 'cites',
		sinceNote: 'complete',
		showStandingBadge: false,
		leaders: [
			{ label: 'Cited by', relType: 'citing-fields', n: 3 },
			{ label: 'Top scholars', relType: 'paper-authors', n: PEOPLE_LEADER_N }
		]
	},
	'hit-papers': {
		statVariant: 'paper',
		showStandingBadge: false,
		leaders: [
			{ label: 'Authors', relType: 'paper-authors', n: 5 },
			{ label: 'Journal', relType: 'paper-journals', n: 1 }
		]
	}
};

function rootHref(etype: tt.EntityType, sid: string): string | null {
	return ROOT_TYPES.includes(etype as tt.RootType) && sid
		? entToLink({ rootType: etype as tt.RootType, semanticId: sid })
		: null;
}

export function buildLeaderRows(
	grouped: Partial<Record<tt.RelTypes, tt.RelatedEntity[]>>,
	specs: LeaderSpec[]
): LeaderRow[] {
	const rows: LeaderRow[] = [];
	for (const spec of specs) {
		// Dedupe by display text: OpenAlex sometimes splits one scholar across author IDs, so the
		// relation list can repeat a name (e.g. "Don L. Anderson" on /subfields/geophysics). Take the
		// first n distinct entries so the keyed {#each} stays collision-free and the list reads clean.
		const seen = new Set<string>();
		const items: LeaderItem[] = [];
		for (const r of grouped[spec.relType] ?? []) {
			const text = spec.withCount ? `${r.name} (${pluralize('paper', r.score)})` : r.name;
			if (seen.has(text)) continue;
			seen.add(text);
			items.push({ text, href: rootHref(r.etype, r.semanticId) });
			if (items.length >= spec.n) break;
		}
		if (items.length === 0) continue;
		rows.push({ label: spec.label, items });
	}
	return rows;
}

// Top topics grouped by parent field name, so each tile can pull the topics that roll up to it.
// `maxTopics` caps the total distinct topics across all fields (the backend returns them ordered by
// score). Dedupes by topic name — OpenAlex occasionally repeats one across the relation list.
function groupTopicsByField(
	rels: tt.RelatedEntity[] | undefined,
	maxTopics: number
): Map<string, TopicScore[]> {
	const byField = new Map<string, TopicScore[]>();
	const seen = new Set<string>();
	for (const t of rels ?? []) {
		const field = t.parentName ?? '';
		if (!field || seen.has(t.name)) continue;
		seen.add(t.name);
		let arr = byField.get(field);
		if (!arr) {
			arr = [];
			byField.set(field, arr);
		}
		arr.push({ name: t.name, score: t.score });
		if (seen.size >= maxTopics) break;
	}
	return byField;
}

// Production tiles: the entity's top subfields by papers authored, each heading its top topics (also
// by papers). The count shows inline; the hover spells out "X papers authored".
export function buildProductionTiles(
	grouped: Partial<Record<tt.RelTypes, tt.RelatedEntity[]>>,
	maxChips: number,
	maxTopics: number
): HeroTile[] {
	const topicsByField = groupTopicsByField(grouped['paper-topics'], maxTopics);
	return (grouped['paper-fields'] ?? []).slice(0, maxChips).map(
		(r, i): HeroTile => ({
			name: r.name,
			href: rootHref(r.etype, r.semanticId),
			colorVar: productionColorVar(i),
			badge: null,
			badgeTitle: null,
			count: r.score,
			topics: (topicsByField.get(r.name) ?? []).map((t) => ({
				name: t.name,
				count: t.score,
				hover: `${pluralize('paper', t.score)} authored`
			}))
		})
	);
}

// Impact tiles: the entity's specialization subfields with the per-subfield "top X%" standing badge
// (aligned with the Peers section by order; `minTier` suppresses the loosest bands), each heading
// the topics whose citing works roll up to it. Topics carry no inline number — the hover gives "X
// citations". Without peer data (no ladder for this root type) it falls back to citing-fields counts.
export function buildImpactTiles(
	cfg: HeroSpec,
	peersData: tt.EntityPeersResp | null,
	ladder: tt.LadderData | null,
	grouped: Partial<Record<tt.RelTypes, tt.RelatedEntity[]>>,
	rootType: tt.RootType,
	maxChips: number,
	minTier: number,
	maxTopics: number
): HeroTile[] {
	const topicsByField = groupTopicsByField(grouped['citing-topics'], maxTopics);
	const topicsFor = (field: string): HeroTopic[] =>
		(topicsByField.get(field) ?? []).map((t) => ({
			name: t.name,
			count: null,
			hover: pluralize('citation', t.score)
		}));
	if (peersData) {
		const labels = ladder ? tierLabels(ladder.pctBands) : [];
		return peersData.topSubfields.slice(0, maxChips).map((sf, i): HeroTile => {
			const tier =
				cfg.showStandingBadge && ladder
					? citStandingTier(ladder.ladder[sf.dmId] ?? [], peersData.hero.subfieldCitations[i] ?? 0)
					: 0;
			const show = tier >= minTier;
			return {
				name: sf.name,
				href: entToLink({ rootType: 'subfields', semanticId: sf.semanticId }),
				colorVar: impactColorVar(i),
				badge: show ? standingLabel(tier, labels) : null,
				badgeTitle: show ? standingPhrase(tier, labels, rootType, sf.name) : null,
				count: null,
				topics: topicsFor(sf.name)
			};
		});
	}
	return (grouped['citing-fields'] ?? []).slice(0, maxChips).map(
		(r, i): HeroTile => ({
			name: r.name,
			href: rootHref(r.etype, r.semanticId),
			colorVar: impactColorVar(i),
			badge: null,
			badgeTitle: null,
			count: r.score,
			topics: topicsFor(r.name)
		})
	);
}
