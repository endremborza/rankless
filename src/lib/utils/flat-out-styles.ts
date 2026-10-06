import type { AttributeLabels } from '$lib/wire/rankless_trees/io';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { HIGH_OP, LOW_OP } from '$lib/constants';
import { getColor, getColorArr } from '$lib/style-util';
import { SPEC_BPS } from '$lib/text-format-util';
import { subfields, fields, domains } from '$lib/assets/data/field-hierarchy.json';

// How the flat-out views (the world map of countries, the concept map of fields) scale an
// entity's level-1 weights into colours and sizes, and how they word what they show. The entity
// page writes the styles as CSS; the share cards write them as literal attributes.

type Range = [number, number];

export type Shade = { fill: string; rgb: number[]; opacity: number };
export type CountryStyle = Shade & { w: number; bucket: number };
export type Bucket = { lo: number; hi: number; shade: Shade };
export type CountryStyles = {
	byName: Record<string, CountryStyle>;
	buckets: Bucket[];
};
export type SubfieldStyle = { w: number; r: number; sat: number };

const MAP_BREAKPOINTS = 3;
const MAP_PULLER = 0.12;
const MAP_OPACITY_PCT: Range = [LOW_OP * 0.65, HIGH_OP * 1.2];
const MAP_COLOR_RATE: Range = [0.32, 0.45];

// Node radii are in concept-map units; `sat` is the opacity of the paper-coloured disc laid over
// a node, so the weakest nodes wash out.
export const SUBFIELD_NULL_R = 0.8;
const SUBFIELD_BREAKPOINTS = 2;
const SUBFIELD_PULLER = 0.2;
const SUBFIELD_R: Range = [1, 2.3];
const SUBFIELD_SAT: Range = [0.95, 0.05];

export const ORDERED_DOMAINS = [
	'Physical Sciences',
	'Health Sciences',
	'Life Sciences',
	'Social Sciences'
];
// field-hierarchy.json's domain index → its 1-based rank in ORDERED_DOMAINS, which keeps the
// domain colours in their conventional order.
export const DOMAIN_ID_MAP: Record<number, number> = Object.fromEntries(
	domains.map((name, i) => [i, ORDERED_DOMAINS.indexOf(name) + 1])
);

export const COUNTRY_SEMANTICS: Record<tt.RootType, Record<string, string>> = {
	countries: {
		'countries-true': 'collaborating with authors based in',
		'countries-false': 'citing scholars based in'
	},
	institutions: {
		'countries-true': 'collaborating with scholars at',
		'countries-false': 'citing scholars working at'
	},
	authors: { 'countries-false': 'citing papers authored by' },
	sources: { 'countries-true': 'where authors publish in' },
	subfields: {
		'countries-true': 'where authors publish papers about',
		'countries-false': 'where authors cite papers about'
	},
	'hit-papers': { 'countries-false': 'where authors are citing' }
};

export const SUBFIELD_SEMANTICS: Record<tt.RootType, Record<string, string>> = {
	countries: {
		'subfields-true': 'of papers published by authors working in',
		'subfields-false': 'of papers citing works of authors working in'
	},
	institutions: {
		'subfields-true': 'of papers published by authors at',
		'subfields-false': 'of papers citing works of authors at'
	},
	authors: {
		'subfields-true': 'of papers published by',
		'subfields-false': 'of papers citing papers by'
	},
	sources: { 'subfields-true': 'of papers published in' },
	subfields: { 'subfields-false': 'of papers citing papers about' },
	'hit-papers': { 'subfields-false': 'of papers citing' }
};

const lerp = ([lo, hi]: Range, r: number) => r * (hi - lo) + lo;

export function mapWeightText(isSpec: boolean, isRefSide: boolean | undefined): string {
	if (isSpec) return 'Specialization';
	return isRefSide ? 'Total citations of papers' : 'Citations';
}

// The flat level keyed by country name, the key the map's paths carry.
export function countryLevels(flatOut: tt.LevelT, atts: AttributeLabels): tt.LevelT {
	const countryAtts = atts.countries || {};
	return Object.fromEntries(
		Object.entries(flatOut)
			.filter(([k]) => countryAtts[k] != undefined)
			.map(([k, { w }]) => [countryAtts[k].name, { w, id: Number(k) }])
	);
}

function mapShade(rate: number): Shade {
	const colorRate = lerp(MAP_COLOR_RATE, rate);
	return {
		fill: getColor(colorRate),
		rgb: getColorArr(colorRate),
		opacity: lerp(MAP_OPACITY_PCT, rate) / 100
	};
}

// Each country falls in a bucket between breakpoints and is shaded by the bucket's rank.
export function countryStyles(levels: tt.LevelT, ratio = false): CountryStyles {
	const { newBreakPoints, locMaxw } = tf.getFlatRescaler(levels, MAP_BREAKPOINTS, MAP_PULLER);
	const byName = Object.fromEntries(
		Object.entries(levels).map(([name, { w }]) => {
			const bucket = newBreakPoints.slice(1).filter((bp) => w >= bp).length;
			return [name, { ...mapShade(bucket / MAP_BREAKPOINTS), w, bucket }];
		})
	);
	const buckets =
		Object.keys(levels).length > 0
			? newBreakPoints.map((lo, i) => ({
					lo,
					hi: bucketEnd(newBreakPoints, i, locMaxw || 1, ratio),
					shade: mapShade(i / MAP_BREAKPOINTS)
				}))
			: [];
	return { byName, buckets };
}

// The upper end printed for bucket i: one under the next breakpoint for counts, the next
// breakpoint itself for a ratio such as specialization.
function bucketEnd(bps: number[], i: number, max: number, ratio: boolean): number {
	const next = bps[i + 1];
	if (next === undefined) return max;
	return ratio || next - 1 < bps[i] ? next : next - 1;
}

export function subfieldStyles(levels: tt.LevelT, isSpec: boolean): Record<string, SubfieldStyle> {
	const { linScaler, newBreakPoints } = tf.getFlatRescaler(
		levels,
		SUBFIELD_BREAKPOINTS,
		SUBFIELD_PULLER
	);
	const bps = isSpec ? SPEC_BPS : newBreakPoints;
	return Object.fromEntries(
		Object.entries(levels).map(([sfi, { w }]) => {
			const bucket = bps.filter((bp) => w >= bp).length;
			const r = lerp(SUBFIELD_R, Math.pow(linScaler(w), 0.65));
			const sat = lerp(SUBFIELD_SAT, Math.pow(bucket / bps.length, 0.35));
			return [sfi, { w, r, sat }];
		})
	);
}

export function domainRate(domainId: number): number {
	return (domainId - 1) / (domains.length - 2);
}

// The subfield's field and its domain, remapped into ORDERED_DOMAINS.
export function subfieldHier(sfi: number): [number, number] {
	const fieldId = subfields[sfi][1] as number;
	return [fieldId, DOMAIN_ID_MAP[fields[fieldId][1] as number]];
}

export function subfieldColor(sfi: number): string {
	return getColor(domainRate(subfieldHier(sfi)[1]));
}
