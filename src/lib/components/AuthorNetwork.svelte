<script lang="ts">
	import { circleLayout, cytoscapeLayout, getIndex } from '$lib/network-util';
	import { fade, slide } from 'svelte/transition';

	export let nodes: string[] = [];
	export let nodeIntensities: number[] = [];
	export let edgeWeights: number[] = [];
	export let rootName: string = 'Person';

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
	function scaledNodeScalars(weights: number[], nodes: string[]) {
		if (weights.length == 0) return [];
		let maxW = Math.max(...weights);
		return weights.map((e) => e / (maxW * 1.2) + 0.2);
	}

	function getFontSize(label: string, r: number) {
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
	const possFuns = Object.keys(layoutMap) as (keyof typeof layoutMap)[];
	let actFun: keyof typeof layoutMap = 'force';
	$: positions = layoutMap[actFun](nodes, edgeWeights, options);
	let showControls = false;
</script>

{#if n === 0}
	<div>No nodes</div>
{:else}
	<h3>
		Co-authorship network of co-authors of {rootName}
	</h3>
	<div bind:clientWidth={svgWidth} bind:clientHeight={svgHeight} class="nw-container">
		{#if svgWidth != undefined}
			<svg {viewBox} role="img" aria-label="Author Network" transition:fade>
				{#each Array(n) as _, i (i)}
					{#each Array(n) as _, j (j)}
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

				{#each nodes as label, i (i)}
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
	<div class="legend-wrapper">
		<button class="toggle-button" on:click={() => (showControls = !showControls)}>
			{showControls ? '✕ Close' : '⚙ Controls'}
		</button>
		{#if !showControls}
			<p class="vw-base">
				This figure shows the co-authorship network connecting the top 25 collaborators of {rootName}.
				A scholar is included among the top collaborators of {rootName} based on the total number of citations
				received by their joint publications. <b class="edgecolor">Widths of edges</b>
				represent the number of papers authors have co-authored together.
				<b class="nodecolor">Node borders</b>
				signify the number of papers an author published with {rootName}. {rootName} is excluded from
				the visualization to improve readability, since they are connected to all nodes in the network.
			</p>
		{:else}
			<div class="panel-inner">
				<div>
					<label>
						Layout:
						<select bind:value={actFun}>
							{#each possFuns as name, __i (__i)}
								<option value={name}>{name}</option>
							{/each}
						</select>
					</label>
				</div>
				{#if actFun == 'force'}
					<div class="sliders" transition:slide>
						<label>
							<span class="vw-base">Gravity: {gravity}</span>
							<input type="range" min="0" max="1" step="0.01" bind:value={gravity} />
						</label>
						<label>
							<span class="vw-base">Iterations: {numIter}</span>
							<input type="range" min="1" max="1000" step="1" bind:value={numIter} />
						</label>
						<label>
							<span class="vw-base">Initial Temp: {initialTemp}</span>
							<input type="range" min="10" max="2000" step="1" bind:value={initialTemp} />
						</label>
						<label>
							<span class="vw-base">Cooling: {coolingFactor}</span>
							<input type="range" min="0" max="1" step=".01" bind:value={coolingFactor} />
						</label>
						<label>
							<span class="vw-base">Min Temp: {minTemp}</span>
							<input type="range" min="1" max="1000" step="1" bind:value={minTemp} />
						</label>
					</div>
				{/if}
			</div>
		{/if}
	</div>
{/if}

<style>
	:root {
		--panel-bg: var(--text-bg, #fff);
		--panel-fg: var(--color-text, #000);
		--panel-border: var(--text-bg-2, #ccc);
		--button-bg: var(--text-bg-3, #0077ff);
		--button-fg: var(--highlight-text, #fff);
		--edge-color: rgb(var(--color-range-40));
	}

	@media (prefers-color-scheme: dark) {
		:root {
			--edge-color: rgb(var(--color-range-95));
		}
	}

	h3 {
		width: 100%;
	}

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
		stroke: var(--edge-color);
	}

	text {
		font-weight: 600;
		border: solid black 1px;
	}

	input[type='range'] {
		width: 100%;
		margin-top: 0.3rem;
	}

	.nw-container {
		flex: 10 1 700px;
		height: min(80svh, 105vw);
	}

	.legend-wrapper {
		flex: 2 1 300px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: space-between;
	}

	.toggle-button {
		width: 115px;
		background: var(--button-bg, #ccc);
		color: var(--button-fg, #000);
		border: none;
		padding: 0.5rem 1rem;
		cursor: pointer;
		transition: opacity 0.2s ease;
	}

	.toggle-button:hover {
		opacity: 0.8;
	}

	.panel-inner {
		padding: 0.3rem 0;
		background: var(--panel-bg, #fff);
		color: var(--panel-fg, #000);
		width: 100%;
	}

	.sliders {
		display: flex;
		gap: 1rem;
		margin-top: 1rem;
		flex-direction: row;
		flex-wrap: wrap;
		justify-content: space-evenly;
	}

	.sliders > label {
		display: flex;
		flex-direction: column;
	}

	@media (min-width: 600px) {
		.sliders > label {
			width: 240px;
		}
	}

	.nodecolor {
		color: rgb(var(--color-range-20));
	}

	.edgecolor {
		color: var(--edge-color);
	}
</style>
