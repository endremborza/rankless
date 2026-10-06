import { error } from '@sveltejs/kit';
import { FULL_HOST } from '$lib/constants';
import { renderSvgComponent } from '$lib/server/render';
import { rasterizeSvg } from '$lib/server/card-raster';
import CompositeFrame from '$lib/components/cards/CompositeFrame.svelte';
import {
	MAX_PANELS,
	compositeLayout,
	defaultCols,
	namespaceIds,
	parsePanelRef,
	type CompositeLayout
} from '$lib/utils/composite';
import { intParam } from './kind';
import { loadCard } from './index';

const RASTER_W = 2400;

// Several cards merged into one picture, `/card/composite.png?p=<panel>&p=<panel>&cols=2`: each
// `p` is a card's own path and variant, loaded and validated as that card is, and drawn in a grid
// under the names of the entities shown. Rendered per request, with no disk cache: a post bundles
// the file once, and the variants are the product of the panels'.
export async function buildComposite(
	params: URLSearchParams,
	fetchFn: typeof fetch
): Promise<{ svg: string; layout: CompositeLayout }> {
	const refs = params.getAll('p').map((p) => parsePanelRef(p) ?? error(404, 'bad panel'));
	if (refs.length < 2 || refs.length > MAX_PANELS) error(404, `2 to ${MAX_PANELS} panels`);
	const cols = intParam(params, 'cols', defaultCols(refs.length), 1, 2);
	const cards = await Promise.all(
		refs.map((ref) => loadCard(ref.kind, ref.rootType, ref.semanticId, ref.params, fetchFn))
	);
	const shown = new Set(cards.map((c) => c.name));
	// A paper is named over its own panel; the title is whose papers they are, when anyone's.
	const subjects = cards.filter((_, i) => refs[i].rootType !== 'hit-papers');
	const names = [...new Set((subjects.length ? subjects : cards).map((c) => c.name))];
	const layout = compositeLayout(cards.length, cols);
	const svg = renderSvgComponent(CompositeFrame, {
		title: names.join(' · '),
		url:
			names.length === 1
				? cards.find((c) => c.name === names[0])!.url
				: FULL_HOST.replace(/^https?:\/\//, ''),
		layout,
		panels: cards.map((card, i) => ({
			heading:
				shown.size === 1 || card.caption.includes(card.name)
					? card.caption
					: `${card.name}: ${card.caption}`,
			body: namespaceIds(renderSvgComponent(card.inner, card.props), `p${i}-`)
		}))
	});
	return { svg, layout };
}

export async function compositePng(params: URLSearchParams, fetchFn: typeof fetch) {
	const { svg, layout } = await buildComposite(params, fetchFn);
	return rasterizeSvg(svg, RASTER_W, Math.round((RASTER_W * layout.height) / layout.width));
}
