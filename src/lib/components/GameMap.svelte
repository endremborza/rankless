<script lang="ts">
	import countryPaths from '$lib/assets/data/country-svg-paths.json';
	import { haversineKm, latLonToMap, mapToLatLon, type LatLon } from '$lib/utils/game-clues';

	export let pin: LatLon | null = null;
	export let target: LatLon | null = null;
	export let disabled = false;

	const xMin = 0;
	const yMin = -20;
	const mapWidth = 2000;
	const mapHeight = 950;

	let svgEl: SVGSVGElement;

	$: pinXY = pin ? latLonToMap(pin) : null;
	$: targetXY = target ? latLonToMap(target) : null;
	$: distanceKm = pin && target ? haversineKm(pin, target) : null;

	function placePin(ev: MouseEvent) {
		if (disabled || !svgEl) return;
		const ctm = svgEl.getScreenCTM();
		if (!ctm) return;
		const pt = new DOMPoint(ev.clientX, ev.clientY).matrixTransform(ctm.inverse());
		pin = mapToLatLon(pt.x, pt.y);
	}
</script>

<div class="guess-map" class:disabled>
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<svg
		bind:this={svgEl}
		viewBox="{xMin} {yMin} {mapWidth} {mapHeight}"
		role="region"
		aria-label="world map for placing a guess"
		on:click={placePin}
	>
		{#each Object.values(countryPaths) as cpaths, i (i)}
			{#each cpaths as d, j (j)}
				<path {d} />
			{/each}
		{/each}
		{#if pinXY && targetXY}
			<line class="reveal-line" x1={pinXY.x} y1={pinXY.y} x2={targetXY.x} y2={targetXY.y} />
		{/if}
		{#if targetXY}
			<circle class="target-mark" cx={targetXY.x} cy={targetXY.y} r="9" />
			<circle class="target-dot" cx={targetXY.x} cy={targetXY.y} r="3" />
		{/if}
		{#if pinXY}
			<circle class="pin-mark" cx={pinXY.x} cy={pinXY.y} r="7" />
		{/if}
	</svg>
	{#if distanceKm != null}
		<div class="distance-label">{Math.round(distanceKm)} km off</div>
	{/if}
</div>

<style>
	.guess-map {
		position: relative;
		width: 100%;
	}

	svg {
		width: 100%;
		display: block;
		outline: none;
	}

	.guess-map:not(.disabled) svg {
		cursor: crosshair;
	}

	path {
		fill: var(--text-bg-2);
		stroke: var(--color-text);
		stroke-width: 0.6;
		outline: none;
	}

	.pin-mark {
		fill: rgba(var(--color-range-50), 0.85);
		stroke: var(--color-text);
		stroke-width: 2;
	}

	.target-mark {
		fill: none;
		stroke: var(--color-ok);
		stroke-width: 3;
	}

	.target-dot {
		fill: var(--color-ok);
	}

	.reveal-line {
		stroke: var(--color-text);
		stroke-width: 2;
		stroke-dasharray: 8 6;
	}

	.distance-label {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
		padding: 0.2rem 0.6rem;
		background: var(--text-bg-2);
		border: 1px solid var(--border-light);
		font-weight: 600;
	}
</style>
