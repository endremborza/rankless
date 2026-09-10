<!-- Reveal map for the nearest cards: the prompt institution and its four
	options on the world-map asset, zoomed to the points, dashed lines from the
	prompt and the nearest option highlighted. Same projection the calibration
	fit (map-projection.json) gives WorldMapSvg's paths. -->
<script lang="ts">
	import countryPaths from '$lib/assets/data/country-svg-paths.json';
	import { latLonToMap, type LatLon } from '$lib/utils/geo';

	export let anchor: LatLon;
	export let points: (LatLon & { label: string; answer: boolean })[];

	// Map units around the points: enough for the labels, and a floor so a
	// tight cluster still shows some coastline.
	const PAD = 0.25;
	const MIN_SPAN = 240;
	const ASPECT = 2;

	$: a = latLonToMap(anchor);
	$: pts = points.map((p) => ({ ...p, ...latLonToMap(p) }));
	$: viewBox = frame([a, ...pts]);

	function frame(xy: { x: number; y: number }[]): string {
		const xs = xy.map((p) => p.x);
		const ys = xy.map((p) => p.y);
		const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
		const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
		let w = Math.max(MIN_SPAN, (Math.max(...xs) - Math.min(...xs)) * (1 + 2 * PAD));
		let h = Math.max(MIN_SPAN / ASPECT, (Math.max(...ys) - Math.min(...ys)) * (1 + 2 * PAD));
		if (w / h > ASPECT) h = w / ASPECT;
		else w = h * ASPECT;
		return `${cx - w / 2} ${cy - h / 2} ${w} ${h}`;
	}
</script>

<svg {viewBox} role="img" aria-label="map of the options around the prompt institution">
	{#each Object.values(countryPaths) as cpaths, i (i)}
		{#each cpaths as d, j (j)}
			<path {d} />
		{/each}
	{/each}
	{#each pts as p, i (i)}
		<line class="tie" class:answer={p.answer} x1={a.x} y1={a.y} x2={p.x} y2={p.y} />
	{/each}
	{#each pts as p, i (i)}
		<circle class="option" class:answer={p.answer} cx={p.x} cy={p.y} r="6" />
		<text class="label" x={p.x + 9} y={p.y + 4}>{p.label}</text>
	{/each}
	<circle class="anchor" cx={a.x} cy={a.y} r="8" />
</svg>

<style>
	svg {
		width: 100%;
		aspect-ratio: 2 / 1;
		display: block;
		border: 1px solid var(--border-light);
		background: var(--text-bg);
	}

	path {
		fill: var(--text-bg-2);
		stroke: var(--color-text-light);
		stroke-width: 0.6;
	}

	.tie {
		stroke: var(--color-text-light);
		stroke-width: 1.5;
		stroke-dasharray: 6 5;
	}

	.tie.answer {
		stroke: var(--color-ok);
		stroke-width: 2.5;
		stroke-dasharray: none;
	}

	.option {
		fill: var(--text-bg-2);
		stroke: var(--color-text);
		stroke-width: 2;
	}

	.option.answer {
		fill: var(--color-ok);
		stroke: var(--color-ok);
	}

	.anchor {
		fill: var(--color-text);
		stroke: var(--text-bg);
		stroke-width: 2;
	}

	.label {
		font-size: 13px;
		fill: var(--color-text);
		paint-order: stroke;
		stroke: var(--text-bg);
		stroke-width: 3px;
	}
</style>
