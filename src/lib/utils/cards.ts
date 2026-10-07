import style from '../assets/data/card-style.json';

// Geometry, faces and text fitting shared by the share cards. A card is rendered server-side to a
// standalone SVG and rasterized, so nothing in it can be measured or styled through CSS: every
// colour is a literal attribute and every text width is estimated from its character count at the
// face's average advance. The brand faces must be installed on the rasterizer host (deploy.py
// vendors static/fonts/); each family lists a generic fallback.

// Social platforms take one fixed-size raster; every card is drawn at this size. The size and the
// brand colours are shared with pyscripts/sharecard_test.py and pyscripts/poster_figures.py through
// card-style.json.
export const CARD_W = style.width;
export const CARD_H = style.height;
export const CARD_MARGIN = 48;
// The box the frame gives a card's visualization.
export const INNER = { x: CARD_MARGIN, y: 132, w: CARD_W - 2 * CARD_MARGIN, h: 418 };

export const SERIF = "'Hedvig Letters Serif', serif";
export const SANS = "'Hedvig Letters Sans', sans-serif";
export const MONO = "'Space Mono', monospace";
// Average advance per em of each face, for width estimates.
export const CHAR_W = { serif: 0.5, sans: 0.53, mono: 0.62 } as const;

export const INK = '#21272a';
export const MUTED = '#4f4f4f';
export const FAINT = '#9aa0a6';
export const ACCENT = style.accent;
export const PAPER = '#ffffff';
export const HAIRLINE = '#d9dde1';
// Canonical brand spectrum (matches the breakdown palette).
export const SPECTRUM = style.spectrum;

// No label is drawn under this size at card width: the top items get labels, the rest none.
export const LABEL_FLOOR = 13;

export function textWidth(text: string, size: number, charW: number = CHAR_W.sans): number {
	return text.length * size * charW;
}

// The room right-aligned mono labels take left of a plot, `pad` included.
export function gutterWidth(labels: string[], size: number, pad: number): number {
	return Math.max(1, ...labels.map((l) => l.length)) * CHAR_W.mono * size + pad;
}

// The largest size up to `max` at which `text` fits `width`.
export function fitSize(text: string, width: number, max: number, charW: number = CHAR_W.sans) {
	if (text.length === 0) return max;
	return Math.min(max, width / (text.length * charW));
}

// `fitSize` under the floor gives no label at all.
export function labelSize(
	text: string,
	width: number,
	max: number,
	charW: number = CHAR_W.sans
): number | null {
	const size = fitSize(text, width, max, charW);
	return size >= LABEL_FLOOR ? size : null;
}

export function clip(text: string, maxChars: number): string {
	if (text.length <= maxChars) return text;
	return text.slice(0, Math.max(1, maxChars - 1)).trimEnd() + '…';
}

// `text` at `size`, clipped to what fits `width`.
export function clipToWidth(
	text: string,
	width: number,
	size: number,
	charW: number = CHAR_W.sans
): string {
	return clip(text, Math.floor(width / (size * charW)));
}

// Greedy word wrap into at most `maxLines` lines of `maxChars`: the last line takes the rest of
// the text, clipped with an ellipsis, and a word longer than a line is clipped where it stands.
export function wrapLines(text: string, maxChars: number, maxLines: number): string[] {
	const words = text.split(/\s+/).filter(Boolean);
	const lines: string[] = [];
	let k = 0;
	while (k < words.length && lines.length < maxLines - 1) {
		let line = words[k++];
		while (k < words.length && line.length + 1 + words[k].length <= maxChars) {
			line += ` ${words[k++]}`;
		}
		lines.push(clip(line, maxChars));
	}
	if (k < words.length) lines.push(clip(words.slice(k).join(' '), maxChars));
	return lines;
}
