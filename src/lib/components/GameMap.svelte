<!-- Reveal map for the nearest cards: the prompt institution and its four
	options on the world-map asset, zoomed to the points, dashed ties from the
	prompt and the nearest option highlighted. Same projection the calibration
	fit (map-projection.json) gives WorldMapSvg's paths. Strokes, markers and
	type are sized against the frame, so a cluster of campuses and a continent
	read the same. -->
<script lang="ts">
	import countryPaths from '$lib/assets/data/country-svg-paths.json';
	import { latLonToMap, type LatLon } from '$lib/utils/geo';

	export let anchor: LatLon;
	export let anchorLabel: string;
	export let points: (LatLon & { label: string; answer: boolean })[];

	type Mark = { x: number; y: number; label: string; answer: boolean; anchor: boolean };
	type Placed = Mark & { tx: number; ty: number; end: boolean };

	// Frame padding around the points; the floor keeps a cluster of campuses
	// apart on screen even when it spans a few kilometres.
	const PAD = 0.3;
	const MIN_SPAN = 4;
	const ASPECT = 2;
	const MAX_LABEL = 28;
	// Sizes as fractions of the frame width.
	const FONT = 1 / 30;
	const RADIUS = 1 / 70;
	// Mean glyph width relative to the font size, for placing labels inside the frame.
	const GLYPH = 0.56;

	$: a = latLonToMap(anchor);
	$: marks = [
		{ ...a, label: anchorLabel, answer: false, anchor: true },
		...points.map((p) => ({ ...latLonToMap(p), label: p.label, answer: p.answer, anchor: false }))
	] satisfies Mark[];
	$: box = frame(marks);
	$: viewBox = `${box.x} ${box.y} ${box.w} ${box.h}`;
	$: font = box.w * FONT;
	$: r = box.w * RADIUS;
	$: placed = placeLabels(marks, box, font, r);

	function frame(xy: { x: number; y: number }[]): { x: number; y: number; w: number; h: number } {
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

	function short(label: string): string {
		return label.length > MAX_LABEL ? `${label.slice(0, MAX_LABEL - 1).trimEnd()}…` : label;
	}

	// Each label sits beside its marker on the side with room, and labels
	// that would print over each other step down in turn.
	function placeLabels(
		ms: Mark[],
		b: { x: number; y: number; w: number; h: number },
		fs: number,
		rad: number
	): Placed[] {
		const gap = rad * 1.8;
		const out = ms.map((m) => {
			const label = short(m.label);
			const width = label.length * GLYPH * fs;
			const fitsRight = m.x + gap + width <= b.x + b.w;
			const fitsLeft = m.x - gap - width >= b.x;
			const end =
				!fitsRight && fitsLeft ? true : fitsRight ? m.x > b.x + b.w * 0.6 && fitsLeft : false;
			const ty = Math.min(Math.max(m.y + fs * 0.35, b.y + fs), b.y + b.h - fs * 0.3);
			return { ...m, label, tx: end ? m.x - gap : m.x + gap, ty, end };
		});
		const step = fs * 1.15;
		for (const [i, p] of out.entries()) {
			for (let j = 0; j < i; j++) {
				const q = out[j];
				const pl = p.end ? p.tx - p.label.length * GLYPH * fs : p.tx;
				const ql = q.end ? q.tx - q.label.length * GLYPH * fs : q.tx;
				const overlapX =
					pl < ql + q.label.length * GLYPH * fs && ql < pl + p.label.length * GLYPH * fs;
				if (overlapX && Math.abs(p.ty - q.ty) < step) p.ty = q.ty + step;
			}
		}
		return out;
	}
</script>

<svg {viewBox} role="img" aria-label="map of the options around the prompt institution">
	{#each Object.values(countryPaths) as cpaths, i (i)}
		{#each cpaths as d, j (j)}
			<path {d} />
		{/each}
	{/each}
	{#each marks.slice(1) as p, i (i)}
		<line class="tie" class:answer={p.answer} x1={a.x} y1={a.y} x2={p.x} y2={p.y} />
	{/each}
	{#each placed as p, i (i)}
		{#if p.anchor}
			<circle class="anchor" cx={p.x} cy={p.y} r={r * 1.5} />
			<circle class="anchor-core" cx={p.x} cy={p.y} r={r * 0.6} />
		{:else}
			<circle class="option" class:answer={p.answer} cx={p.x} cy={p.y} {r} />
		{/if}
		<text
			class="label"
			class:anchor={p.anchor}
			class:answer={p.answer}
			x={p.tx}
			y={p.ty}
			font-size={font}
			text-anchor={p.end ? 'end' : 'start'}>{p.label}</text
		>
	{/each}
</svg>

<style>
	svg {
		width: 100%;
		aspect-ratio: 2 / 1;
		display: block;
		border: 1px solid var(--border-light);
		background: var(--text-bg);
	}

	path,
	.tie,
	.option,
	.anchor {
		vector-effect: non-scaling-stroke;
	}

	path {
		fill: var(--text-bg-2);
		stroke: var(--color-text-light);
		stroke-width: 0.8px;
	}

	.tie {
		stroke: var(--color-text-light);
		stroke-width: 1.5px;
		stroke-dasharray: 6 5;
	}

	.tie.answer {
		stroke: var(--color-ok);
		stroke-width: 2.5px;
		stroke-dasharray: none;
	}

	.option {
		fill: var(--text-bg);
		stroke: var(--color-text);
		stroke-width: 2px;
	}

	.option.answer {
		fill: var(--color-ok);
		stroke: var(--color-ok);
	}

	.anchor {
		fill: var(--text-bg);
		stroke: var(--color-text);
		stroke-width: 2.5px;
	}

	.anchor-core {
		fill: var(--color-text);
	}

	.label {
		fill: var(--color-text);
		paint-order: stroke;
		stroke: var(--text-bg);
		stroke-width: 0.25em;
		stroke-linejoin: round;
	}

	.label.anchor {
		font-weight: 700;
	}

	.label.answer {
		fill: var(--color-ok);
		font-weight: 700;
	}
</style>
