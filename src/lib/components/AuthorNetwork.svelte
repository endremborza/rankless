<script lang="ts">
	import { circleLayout, cytoscapeLayout, getIndex } from '$lib/network-util';
	import { fade, slide } from 'svelte/transition';
	import HoverI from './HoverI.svelte';
	import HoverBlock from './HoverBlock.svelte';

	export let nodes: string[] = [];
	export let nodeIntensities: number[] = [];
	export let edgeWeights: number[] = [];
	export let rootName: strin = 'Person';

	$: n = nodes.length;
	$: nodeScales = scaledNodeScalars(nodeIntensities, nodes);

	function getWeight(i: number, j: number, n: number, weights: number[]) {
		const idx = getIndex(i, j, n);
		if (idx < 0 || idx >= weights.length) return 0;
		return weights[idx] || 0;
	}

	function lastWord(word: string) {
		let words = word.split(' ');
		return words[words.length - 1];
	}
	function scaledNodeScalars(weights: number[], nodes) {
		if (weights.length == 0) return [];
		let maxW = Math.max(...weights);
		return weights.map((e) => e / (maxW * 1.2) + 0.2);
	}

	function getFontSize(label: string, r) {
		if (lastWord(label).length > 10) return 0.6 * r;
		if (lastWord(label).length > 6) return 0.8 * r;
		return r;
	}

	let idealEdgeLength = 100;
	let nodeRepulsion = 4000;
	let edgeElasticity = 100;
	let nestingFactor = 1.2;
	let gravity = 0.05;
	let numIter = 100;
	let initialTemp = 1000;
	let coolingFactor = 0.99;
	let minTemp = 1;

	let positions: { x: number; y: number }[] = [];

	let svgWidth: number;
	let svgHeight: number;

	const marge = 0.09;
	const height = 400;
	const margify = (x: number) => x * (1 + 2 * marge);
	$: width = (height * svgWidth) / svgHeight;
	$: r = Math.min(14, width / 20);
	$: viewBox = `-${width * marge} -${height * marge} ${margify(width)} ${margify(height)}`;

	$: options = {
		height,
		width,
		idealEdgeLength,
		nodeRepulsion,
		edgeElasticity,
		nestingFactor,
		gravity,
		numIter,
		initialTemp,
		coolingFactor,
		minTemp
	};

	const layoutMap = {
		circle: circleLayout,
		// radial: radialWeightedLayout,
		force: cytoscapeLayout
	};
	const possFuns = Object.keys(layoutMap);
	let actFun: (typeof possFuns)[number] = 'force';
	$: positions = layoutMap[actFun](nodes, edgeWeights, options);
	let showControls = false;
	let showInfo = false;
</script>

{#if n === 0}
	<div>No nodes</div>
{:else}
	<div class="controls-wrapper">
		<div class="nw-title">
			<h3>
				Co-authorship network of co-authors of {rootName}
				<HoverI bind:hoverToggle={showInfo} />
			</h3>
			<button class="toggle-button" on:click={() => (showControls = !showControls)}>
				{showControls ? '✕ Close' : '⚙ Controls'}
			</button>
			<HoverBlock show={showInfo} style="width: 600px; max-width: 90%; top: 80px; left: 5%">
				This figure shows the co-authorship network connecting the top 25 collaborators of {rootName}.
				A scholar is included among the top collaborators of {rootName} based on the total number of
				citations received by their joint publications. Edges between collaborators represent the number
				of papers they have co-authored together. {rootName} is excluded from the visualization to improve
				readability, since they are connected to all nodes in the network.
			</HoverBlock>
		</div>
		<div class="panel {showControls ? 'open' : ''}">
			<div class="panel-inner">
				<div>
					<label>
						Layout:
						<select bind:value={actFun}>
							{#each possFuns as name}
								<option value={name}>{name}</option>
							{/each}
						</select>
					</label>
				</div>
				{#if actFun == 'force'}
					<div class="sliders" transition:slide>
						<label>
							<span>Gravity: {gravity}</span>
							<input type="range" min="0" max="1" step="0.01" bind:value={gravity} />
						</label>
						<label>
							<span>Iterations: {numIter}</span>
							<input type="range" min="1" max="1000" step="1" bind:value={numIter} />
						</label>
						<label>
							<span>Initial Temp: {initialTemp}</span>
							<input type="range" min="10" max="2000" step="1" bind:value={initialTemp} />
						</label>
						<label>
							<span>Cooling: {coolingFactor}</span>
							<input type="range" min="0" max="1" step=".01" bind:value={coolingFactor} />
						</label>
						<label>
							<span>Min Temp: {minTemp}</span>
							<input type="range" min="1" max="1000" step="1" bind:value={minTemp} />
						</label>
					</div>
				{/if}
			</div>
		</div>
	</div>

	<div bind:clientWidth={svgWidth} bind:clientHeight={svgHeight} id="nw-container">
		{#if svgWidth != undefined}
			<svg {viewBox} role="img" aria-label="Author Network" transition:fade>
				<!-- edges -->
				{#each Array(n) as _, i}
					{#each Array(n) as _, j}
						{#if j > i && getWeight(i, j, n, edgeWeights) > 0}
							<line
								x1={positions[i].x}
								y1={positions[i].y}
								x2={positions[j].x}
								y2={positions[j].y}
								stroke-width={Math.min(r / 2, 1 + Math.sqrt(getWeight(i, j, n, edgeWeights)))}
								stroke-opacity={Math.max(
									0.25,
									Math.min(0.95, 0.25 + 0.15 * Math.log1p(getWeight(i, j, n, edgeWeights)))
								)}
							/>
						{/if}
					{/each}
				{/each}

				{#each nodes as label, i}
					<g transform="translate({positions[i].x},{positions[i].y})">
						<ellipse
							rx={r}
							ry={r}
							stroke-width={(nodeScales[i] || 1) * 1.8}
							stroke-opacity={nodeScales[i] || 1}
						/>
						<text text-anchor="middle" font-size={getFontSize(label, r)} y={r * 0.2}>
							{lastWord(label)}</text
						>
					</g>
				{/each}
			</svg>
		{/if}
	</div>
{/if}

<style>
	svg {
		width: 100%;
		height: 100%;
	}

	ellipse {
		fill: var(--text-bg-2);
		stroke: rgb(var(--color-range-20));
		fill-opacity: 0.75;
	}

	line {
		stroke: rgb(var(--color-range-40));
	}

	@media (prefers-color-scheme: dark) {
		line {
			stroke: rgb(var(--color-range-95));
		}
	}

	text {
		font-weight: 600;
		border: solid black 1px;
	}

	#nw-container {
		width: 100%;
		height: 75svh;
	}

	:root {
		--panel-bg: var(--text-bg, #fff);
		--panel-fg: var(--color-text, #000);
		--panel-border: var(--text-bg-2, #ccc);
		--button-bg: var(--text-bg-3, #0077ff);
		--button-fg: var(--highlight-text, #fff);
	}

	input[type='range'] {
		width: 100%;
		margin-top: 0.3rem;
	}

	.nw-title {
		position: relative;
		display: flex;
		gap: 12px;
		flex-wrap: wrap;
		justify-content: space-around;
		margin-bottom: var(--unified-margin);
	}

	.nw-title > h3 {
		flex: 1 1 11;
		text-align: center;
		vertical-align: middle;
		margin: auto;
	}

	.nw-title > button {
		flex: 0 1 1;
		width: 115px;
	}

	.sliders > label {
		display: flex;
		flex-direction: column;
		font-size: 0.9rem;
	}

	.toggle-button {
		background: var(--button-bg, #ccc);
		color: var(--button-fg, #000);
		border: none;
		border-radius: var(--borad);
		padding: 0.5rem 1rem;
		cursor: pointer;
		transition: opacity 0.2s ease;
	}
	.toggle-button:hover {
		opacity: 0.8;
	}

	.panel {
		overflow: hidden;
		max-height: 0;
		opacity: 0;
		transition: max-height 0.35s ease, opacity 0.25s ease;
	}

	.panel.open {
		max-height: 800px; /* big enough to fit contents */
		opacity: 1;
	}

	.panel-inner {
		padding: 1rem 0;
		background: var(--panel-bg, #fff);
		color: var(--panel-fg, #000);
		border: 1px solid var(--panel-border, #ccc);
		border-radius: 0.75rem;
		padding: 1rem;
	}

	.sliders {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		margin-top: 1rem;
	}
	@media (min-width: 600px) {
		.sliders {
			flex-direction: row;
			flex-wrap: wrap;
			justify-content: space-evenly;
		}
		.sliders > label {
			width: 240px;
		}
	}
</style>
