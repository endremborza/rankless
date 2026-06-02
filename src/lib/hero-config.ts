import type * as tt from '$lib/tree-types';
import { ROOT_TYPES } from '$lib/constants';
import { entToLink } from '$lib/tree-functions';
import { pluralize } from '$lib/text-format-util';
import {
	sfColorVar,
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

export type Chip = {
	name: string;
	href: string | null;
	colorVar: string;
	badge: string | null;
	badgeTitle: string | null;
};
export type LeaderItem = { text: string; href: string | null };
export type LeaderRow = { label: string; items: LeaderItem[] };

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
			{ label: 'Topics', relType: 'paper-topics', withCount: true, n: 3 },
			{ label: 'Cited by', relType: 'citing-fields', n: 3 },
			{ label: 'Journals', relType: 'paper-journals', n: 3 },
			{ label: 'Partner nations', relType: 'collab-nation', n: 3 }
		]
	},
	institutions: {
		statVariant: 'cites',
		showStandingBadge: true,
		leaders: [
			{ label: 'Top scholars', relType: 'paper-authors', n: PEOPLE_LEADER_N },
			{ label: 'Topics', relType: 'paper-topics', withCount: true, n: 3 },
			{ label: 'Journals', relType: 'paper-journals', n: 3 },
			{ label: 'Partner nations', relType: 'collab-nation', n: 3 }
		]
	},
	countries: {
		statVariant: 'cites',
		showStandingBadge: false,
		leaders: [
			{ label: 'Topics', relType: 'paper-topics', withCount: true, n: 3 },
			{ label: 'Partner nations', relType: 'collab-nation', n: 3 },
			{ label: 'Cited by', relType: 'citing-fields', n: 3 }
		]
	},
	sources: {
		statVariant: 'cites',
		sinceNote: 'startYear',
		showStandingBadge: true,
		leaders: [
			{ label: 'Fields', relType: 'paper-fields', withCount: true, n: 3 },
			{ label: 'Topics', relType: 'paper-topics', n: 3 },
			{ label: 'Top scholars', relType: 'paper-authors', n: PEOPLE_LEADER_N }
		]
	},
	subfields: {
		statVariant: 'cites',
		sinceNote: 'complete',
		showStandingBadge: false,
		leaders: [
			{ label: 'Topics', relType: 'paper-topics', n: 3 },
			{ label: 'Fields', relType: 'paper-fields', n: 3 },
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
		const rels = (grouped[spec.relType] ?? []).slice(0, spec.n);
		if (rels.length === 0) continue;
		rows.push({
			label: spec.label,
			items: rels.map((r) => ({
				text: spec.withCount ? `${r.name} (${pluralize('paper', r.score)})` : r.name,
				href: rootHref(r.etype, r.semanticId)
			}))
		});
	}
	return rows;
}

// Specialization chips: when peer data is present they carry the per-subfield standing badge
// (aligned with the Peers section by color + order); otherwise fall back to the raw paper-fields
// relations with no standing (no ladder for this root type). `minTier` suppresses the loosest
// bands so only showcase-worthy standings reach the header.
export function buildChips(
	cfg: HeroSpec,
	peersData: tt.EntityPeersResp | null,
	ladder: tt.LadderData | null,
	grouped: Partial<Record<tt.RelTypes, tt.RelatedEntity[]>>,
	rootType: tt.RootType,
	maxChips: number,
	minTier: number
): Chip[] {
	if (peersData) {
		const labels = ladder ? tierLabels(ladder.pctBands) : [];
		return peersData.topSubfields.slice(0, maxChips).map((sf, i): Chip => {
			const tier =
				cfg.showStandingBadge && ladder
					? citStandingTier(ladder.ladder[sf.dmId] ?? [], peersData.hero.subfieldCitations[i] ?? 0)
					: 0;
			const show = tier >= minTier;
			return {
				name: sf.name,
				href: entToLink({ rootType: 'subfields', semanticId: sf.semanticId }),
				colorVar: sfColorVar(i),
				badge: show ? standingLabel(tier, labels) : null,
				badgeTitle: show ? standingPhrase(tier, labels, rootType, sf.name) : null
			};
		});
	}
	return (grouped['paper-fields'] ?? []).slice(0, maxChips).map(
		(r, i): Chip => ({
			name: r.name,
			href: rootHref(r.etype, r.semanticId),
			colorVar: sfColorVar(i),
			badge: null,
			badgeTitle: null
		})
	);
}
