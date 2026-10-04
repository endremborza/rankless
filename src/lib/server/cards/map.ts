import MapCard from '$lib/components/cards/MapCard.svelte';
import { mapCardLayout } from '$lib/utils/flat-out-cards';
import {
	COUNTRY_SEMANTICS,
	countryLevels,
	countryStyles,
	mapWeightText
} from '$lib/utils/flat-out-styles';
import type { CardKind } from './kind';
import { loadFlatOut } from './flat-out';

// The entity page's world map: each country shaded by the bucket of its citations (or
// specialization), the heaviest and the `hl` countries (node ids) named with their values.
export const map: CardKind = {
	component: MapCard,
	async load(ctx) {
		const { levels, atts, treeSpec, hl, subject, since } = await loadFlatOut(
			ctx,
			'map',
			(inds) => inds[0],
			ctx.specs.yearBreaks[0]
		);
		const isSpec = treeSpec.defaultIsSpec;
		const sourceSide = treeSpec.breakdowns[0].sourceSide;
		const styles = countryStyles(countryLevels(levels, atts), isSpec);
		const hlNames = hl.flatMap((id) => atts.countries?.[id]?.name ?? []);
		const weight = mapWeightText(isSpec, sourceSide);
		const title = isSpec ? `${weight}, 1 = as expected` : weight;
		const phrase = COUNTRY_SEMANTICS[ctx.rootType][`countries-${sourceSide}`];
		return {
			props: mapCardLayout(styles, hlNames, title),
			caption: `Countries ${phrase} ${subject}${since}, by ${weight.toLowerCase()}`
		};
	}
};
