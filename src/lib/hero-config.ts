import type * as tt from '$lib/tree-types';
import { ROOT_TYPES } from '$lib/constants';
import { entToLink } from '$lib/tree-functions';
import { pluralize } from '$lib/text-format-util';
import {
	impactColor,
	productionColor,
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
	// Field-tile block headers. The production side defaults to "Papers in"; entities whose tiles
	// aren't "papers this entity authored" relabel it (a single paper is "Classified as" its fields,
	// a subfield's papers are "Also classified as" sibling fields).
	productionLabel?: string;
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
	// "r, g, b" triple driving the tile's hue (impact = cool, production = warm); see peers-utils.
	tileColor: string;
	badge: string | null;
	badgeTitle: string | null;
	count: number | null;
	topics: HeroTopic[];
};
// A field on its way to becoming a tile, before topics and color are attached. The production side
// fills `count` (papers); the impact side fills `badge` (standing). Extra tiles surfaced from a top
// topic's parent field carry neither.
type FieldBase = {
	name: string;
	href: string | null;
	badge: string | null;
	badgeTitle: string | null;
	count: number | null;
};
// Top topics under one parent field, plus that field's own link and semantic id (from the topic's
// parent ref) so the field can stand up its own tile — and resolve its badge/count — even when it
// isn't among the base fields.
type FieldTopics = { href: string | null; semanticId: string | null; topics: HeroTopic[] };

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
		productionLabel: 'Also classified as',
		leaders: [
			{ label: 'Cited by', relType: 'citing-fields', n: 3 },
			{ label: 'Top scholars', relType: 'paper-authors', n: PEOPLE_LEADER_N }
		]
	},
	'hit-papers': {
		statVariant: 'paper',
		showStandingBadge: false,
		productionLabel: 'Classified as',
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

// Top topics grouped by parent field, each carrying that field's link so an orphan field (one heading
// a top topic but absent from the base fields) can still become a tile. `maxTopics` caps the total
// distinct topics across all fields (backend returns them ordered by score); dedupes by topic name —
// OpenAlex occasionally repeats one. `toTopic` shapes each topic, since count/hover differ per block.
function groupTopicsByField(
	rels: tt.RelatedEntity[] | undefined,
	maxTopics: number,
	toTopic: (t: tt.RelatedEntity) => HeroTopic
): Map<string, FieldTopics> {
	const byField = new Map<string, FieldTopics>();
	const seen = new Set<string>();
	for (const t of rels ?? []) {
		const field = t.parentName ?? '';
		if (!field || seen.has(t.name)) continue;
		seen.add(t.name);
		let grp = byField.get(field);
		if (!grp) {
			grp = {
				href: t.parentSemanticId
					? entToLink({ rootType: 'subfields', semanticId: t.parentSemanticId })
					: null,
				semanticId: t.parentSemanticId ?? null,
				topics: []
			};
			byField.set(field, grp);
		}
		grp.topics.push(toTopic(t));
		if (seen.size >= maxTopics) break;
	}
	return byField;
}

// Final tile list for one block: each base field heads the topics that roll up to it, then any top
// topic whose parent field isn't already a base tile pulls that field in as an extra tile — so no top
// topic is dropped. That union is why a block can hold more tiles than its base fields. `enrichExtra`
// resolves the extra tile's badge/count from the per-subfield profile (the same standing/paper data
// the base tiles use), keyed by the field's semantic id — so an extra tile keeps its "top X%" banner
// or paper count instead of going blank. Colors span the band by final position (open-ended count).
function assembleTiles(
	base: FieldBase[],
	topicsByField: Map<string, FieldTopics>,
	colorFn: (idx: number, total: number) => string,
	enrichExtra?: (semanticId: string | null) => Partial<FieldBase>
): HeroTile[] {
	const order: FieldBase[] = [];
	const seen = new Set<string>();
	for (const f of base) {
		if (seen.has(f.name)) continue;
		seen.add(f.name);
		order.push(f);
	}
	for (const [name, grp] of topicsByField) {
		if (seen.has(name)) continue;
		seen.add(name);
		order.push({
			name,
			href: grp.href,
			badge: null,
			badgeTitle: null,
			count: null,
			...enrichExtra?.(grp.semanticId)
		});
	}
	return order.map(
		(f, i): HeroTile => ({
			...f,
			tileColor: colorFn(i, order.length),
			topics: topicsByField.get(f.name)?.topics ?? []
		})
	);
}

// Production tiles: the entity's top subfields by papers authored, each heading its top topics (also
// by papers). The count shows inline; the hover spells out "X papers authored". `withCounts` is off
// for a single paper (hit-papers), where every field/topic count is just 1 and reads as noise.
// `refPapers` maps subfield semantic id → papers authored, covering fields beyond the top few that
// the `paper-fields` relation carries, so a topic-surfaced extra tile still shows its count.
export function buildProductionTiles(
	grouped: Partial<Record<tt.RelTypes, tt.RelatedEntity[]>>,
	refPapers: Map<string, number>,
	maxChips: number,
	maxTopics: number,
	withCounts = true
): HeroTile[] {
	const topicsByField = groupTopicsByField(grouped['paper-topics'], maxTopics, (t) => ({
		name: t.name,
		count: withCounts ? t.score : null,
		hover: withCounts ? `${pluralize('paper', t.score)} authored` : ''
	}));
	const base = (grouped['paper-fields'] ?? []).slice(0, maxChips).map(
		(r): FieldBase => ({
			name: r.name,
			href: rootHref(r.etype, r.semanticId),
			badge: null,
			badgeTitle: null,
			count: withCounts ? r.score : null
		})
	);
	return assembleTiles(base, topicsByField, productionColor, (sid) => {
		const papers = withCounts && sid ? refPapers.get(sid) : undefined;
		return papers != null ? { count: papers } : {};
	});
}

// Impact tiles: the entity's specialization subfields with the per-subfield "top X%" standing badge
// (`minTier` suppresses the loosest bands), each heading the topics whose citing works roll up to it.
// Topics carry no inline number — the hover gives "X citations". The standing is computed over the
// full topSubfields list (not just the top few) and keyed by semantic id, so a subfield a top topic
// pulls in as an extra tile keeps its banner. Without peer data it falls back to citing-fields counts.
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
	const topicsByField = groupTopicsByField(grouped['citing-topics'], maxTopics, (t) => ({
		name: t.name,
		count: null,
		hover: pluralize('citation', t.score)
	}));
	let base: FieldBase[];
	let enrichExtra: ((semanticId: string | null) => Partial<FieldBase>) | undefined;
	if (peersData) {
		const labels = ladder ? tierLabels(ladder.pctBands) : [];
		const standing = new Map<string, Partial<FieldBase>>();
		peersData.topSubfields.forEach((sf, i) => {
			const tier =
				cfg.showStandingBadge && ladder
					? citStandingTier(ladder.ladder[sf.dmId] ?? [], peersData.hero.subfieldCitations[i] ?? 0)
					: 0;
			if (tier >= minTier) {
				standing.set(sf.semanticId, {
					badge: standingLabel(tier, labels),
					badgeTitle: standingPhrase(tier, labels, rootType, sf.name)
				});
			}
		});
		base = peersData.topSubfields.slice(0, maxChips).map(
			(sf): FieldBase => ({
				name: sf.name,
				href: entToLink({ rootType: 'subfields', semanticId: sf.semanticId }),
				badge: null,
				badgeTitle: null,
				count: null,
				...standing.get(sf.semanticId)
			})
		);
		enrichExtra = (sid) => (sid ? (standing.get(sid) ?? {}) : {});
	} else {
		base = (grouped['citing-fields'] ?? []).slice(0, maxChips).map(
			(r): FieldBase => ({
				name: r.name,
				href: rootHref(r.etype, r.semanticId),
				badge: null,
				badgeTitle: null,
				count: r.score
			})
		);
	}
	return assembleTiles(base, topicsByField, impactColor, enrichExtra);
}
