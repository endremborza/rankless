import FieldsCard from '$lib/components/cards/FieldsCard.svelte';
import { subfields } from '$lib/assets/data/field-hierarchy.json';
import * as tf from '$lib/tree-functions';
import { htmlToText } from '$lib/utils/paper-helpers';
import { fieldsCardLayout } from '$lib/utils/flat-out-cards';
import { SUBFIELD_SEMANTICS, subfieldStyles } from '$lib/utils/flat-out-styles';
import type { CardKind } from './kind';
import { loadFlatOut } from './flat-out';

// The entity page's concept map of fields: each field's circle sized and shaded by its citations
// (or specialization) and coloured by its domain, the heaviest and the `hl` fields (node ids)
// named with their values.
export const fields: CardKind = {
	component: FieldsCard,
	async load(ctx) {
		const { levels, atts, treeSpec, hl, subject, since } = await loadFlatOut(
			ctx,
			'fields',
			(inds) => (inds.includes(9) ? 9 : inds[0]),
			tf.getDefaultYear(ctx.rootType)
		);
		const isSpec = treeSpec.defaultIsSpec;
		const sourceSide = treeSpec.breakdowns[0].sourceSide;
		const names = Object.fromEntries(
			[...Object.keys(levels), ...hl].map((sfi) => [
				sfi,
				htmlToText(atts.subfields?.[sfi]?.name ?? String(subfields[Number(sfi)]?.[0] ?? ''))
			])
		);
		const weight = isSpec ? 'specialization' : 'citations';
		const phrase = SUBFIELD_SEMANTICS[ctx.rootType][`subfields-${sourceSide}`];
		const sizeText = isSpec ? 'higher specialization' : 'more citations';
		return {
			props: fieldsCardLayout(subfieldStyles(levels, isSpec), hl, names, sizeText),
			caption: `Fields ${phrase} ${subject}${since}, by ${weight}`
		};
	}
};
