// Layout of the nearest-card reveal map: the frame around the marks and the
// label beside each mark. Everything is in map units, sized against the
// frame width, so the same layout serves a campus cluster and a continent.

export type Mark = { x: number; y: number; label: string; answer: boolean; anchor: boolean };
export type Frame = { x: number; y: number; w: number; h: number };
export type Side = 'start' | 'end' | 'middle';
export type Placed = Mark & { tx: number; ty: number; side: Side; down: boolean };

// Frame padding around the points; the floor keeps a cluster of campuses
// apart on screen even when it spans a few kilometres.
const PAD = 0.3;
const MIN_SPAN = 4;
const ASPECT = 2;
const MAX_LABEL = 28;
// Sizes as fractions of the frame width.
export const FONT = 1 / 30;
export const RADIUS = 1 / 70;
// Glyph advance relative to the font size (the labels set in the monospace
// face, whose advance is 0.6 em), for placing labels inside the frame.
export const GLYPH = 0.62;

export function frame(xy: { x: number; y: number }[]): Frame {
	const xs = xy.map((p) => p.x);
	const ys = xy.map((p) => p.y);
	const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
	const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
	let w = Math.max(MIN_SPAN, (Math.max(...xs) - Math.min(...xs)) * (1 + 2 * PAD));
	let h = Math.max(MIN_SPAN / ASPECT, (Math.max(...ys) - Math.min(...ys)) * (1 + 2 * PAD));
	if (w / h > ASPECT) h = w / ASPECT;
	else w = h * ASPECT;
	return { x: cx - w / 2, y: cy - h / 2, w, h };
}

export function shortLabel(label: string): string {
	return label.length > MAX_LABEL ? `${label.slice(0, MAX_LABEL - 1).trimEnd()}…` : label;
}

// Each label sits beside its marker on the side with room, or centred
// under (upper half) or over (lower half) it when neither side has room,
// clamped into the frame; labels that would print over each other step away
// from the nearer frame edge.
export function placeLabels(ms: Mark[], b: Frame, fs: number, rad: number): Placed[] {
	const gap = rad * 1.8;
	const width = (label: string) => label.length * GLYPH * fs;
	const out = ms.map((m) => {
		const label = shortLabel(m.label);
		const w = width(label);
		const right = m.x + gap + w <= b.x + b.w;
		const left = m.x - gap - w >= b.x;
		const side: Side =
			right && !(left && m.x > b.x + b.w * 0.6) ? 'start' : left ? 'end' : 'middle';
		const tx =
			side === 'start'
				? m.x + gap
				: side === 'end'
					? m.x - gap
					: Math.min(Math.max(m.x, b.x + w / 2), b.x + b.w - w / 2);
		const down = m.y <= b.y + b.h / 2;
		const ty = side !== 'middle' ? m.y + fs * 0.35 : down ? m.y + gap + fs : m.y - gap;
		return { ...m, label, tx, ty, side, down };
	});
	const step = fs * 1.15;
	for (const [i, p] of out.entries()) {
		const { down } = p;
		for (let j = 0; j < i; j++) {
			const q = out[j];
			const [pl, pr] = extent(p, fs);
			const [ql, qr] = extent(q, fs);
			if (pl < qr && ql < pr && Math.abs(p.ty - q.ty) < step)
				p.ty = down ? Math.max(p.ty, q.ty + step) : Math.min(p.ty, q.ty - step);
		}
	}
	for (const p of out) p.ty = Math.min(Math.max(p.ty, b.y + fs), b.y + b.h - fs * 0.3);
	return out;
}

// The horizontal span a placed label prints over.
export function extent(p: Placed, fs: number): [number, number] {
	const w = p.label.length * GLYPH * fs;
	if (p.side === 'start') return [p.tx, p.tx + w];
	if (p.side === 'end') return [p.tx - w, p.tx];
	return [p.tx - w / 2, p.tx + w / 2];
}
