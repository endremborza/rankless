<!-- Reveal map for the nearest cards: the prompt institution and its four
	options on the world-map asset, zoomed to the points, dashed ties from the
	prompt and the nearest option highlighted. Same projection the calibration
	fit (map-projection.json) gives WorldMapSvg's paths; frame and label layout
	in utils/game-map. -->
<script lang="ts">
	import countryPaths from '$lib/assets/data/country-svg-paths.json';
	import { latLonToMap, type LatLon } from '$lib/utils/geo';
	import { FONT, RADIUS, frame, placeLabels, type Mark } from '$lib/utils/game-map';

	export let anchor: LatLon;
	export let anchorLabel: string;
	export let points: (LatLon & { label: string; answer: boolean })[];

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
			text-anchor={p.side}>{p.label}</text
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
