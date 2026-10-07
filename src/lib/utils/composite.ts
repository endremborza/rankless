// Geometry and panel addressing of a composite: several cards' pictures in one grid. A panel keeps
// the box its card draws it in (INNER), so one column is a card's width and two columns double the
// canvas rather than shrink the pictures.

import { CARD_MARGIN as M, CARD_W, INNER } from '$lib/utils/cards';

export const MIN_PANELS = 2;
export const MAX_PANELS = 6;
export const MAX_COLS = 2;
// The heading line above a panel's picture.
export const PANEL_HEAD = 46;
const ROW_GAP = 40;
// At one column; both scale with the canvas width.
const HEADER = 150;
const FOOTER = 96;

export type PanelRef = {
	rootType: string;
	semanticId: string;
	kind: string;
	params: URLSearchParams;
};
export type CompositeLayout = {
	width: number;
	height: number;
	scale: number;
	slots: { x: number; y: number }[];
};

// The smallest composite stacks in one column; any larger one fills the widest grid.
export function defaultCols(n: number): number {
	return n > MIN_PANELS ? MAX_COLS : 1;
}

// `n` panels in rows of `cols`, a short last row centred.
export function compositeLayout(n: number, cols: number): CompositeLayout {
	const width = cols * INNER.w + (cols + 1) * M;
	const scale = width / CARD_W;
	const top = HEADER * scale;
	const pitch = PANEL_HEAD + INNER.h + ROW_GAP;
	const slots = Array.from({ length: n }, (_, i) => {
		const row = Math.floor(i / cols);
		const inRow = Math.min(cols, n - row * cols);
		const x0 = (width - inRow * INNER.w - (inRow - 1) * M) / 2;
		return { x: x0 + (i % cols) * (INNER.w + M), y: top + row * pitch };
	});
	return { width, height: top + Math.ceil(n / cols) * pitch + FOOTER * scale, scale, slots };
}

// A panel is a card's own path and variant, `<type>/<semantic id>/<kind>?<query>`, the semantic
// id percent-encoded per segment as in the card's URL.
export function parsePanelRef(ref: string): PanelRef | null {
	const cut = ref.indexOf('?');
	const segments = (cut < 0 ? ref : ref.slice(0, cut)).split('/');
	if (segments.length < 2) return null;
	const kind = segments.pop()!;
	const rootType = segments.shift()!;
	try {
		return {
			rootType,
			semanticId: segments.map(decodeURIComponent).join('/'),
			kind,
			params: new URLSearchParams(cut < 0 ? '' : ref.slice(cut + 1))
		};
	} catch {
		return null;
	}
}

// Every id of a rendered SVG fragment and every reference to it under `prefix`: ids are global
// to the document, and two panels of one kind define the same ones.
export function namespaceIds(svg: string, prefix: string): string {
	return svg
		.replace(/\bid="([^"]+)"/g, `id="${prefix}$1"`)
		.replace(/url\((['"]?)#([^)'"]+)\1\)/g, `url($1#${prefix}$2$1)`)
		.replace(/\bhref="#([^"]+)"/g, `href="#${prefix}$1"`);
}
