<script lang="ts">
	import { circleLayout, radialWeightedLayout, cytoscapeLayout, getIndex } from '$lib/network-util';
	import { fade, scale } from 'svelte/transition';

	export let nodes: string[] = [];
	export let nodeIntensities: number[] = [];
	export let edgeWeights: number[] = [];

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

	let idealEdgeLength = 100;
	let nodeRepulsion = 4000;
	let edgeElasticity = 100;
	let nestingFactor = 1.2;
	let gravity = 0.05;
	let numIter = 10;
	let initialTemp = 1000;
	let coolingFactor = 0.99;
	let minTemp = 1;

	let positions: { x: number; y: number }[] = [];

	let svgWidth: number;
	let svgHeight: number;

	const r = 14;
	const marge = 0.09;
	const height = 400;
	const margify = (x: number) => x * (1 + 2 * marge);
	$: width = (height * svgWidth) / svgHeight;
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
	let showControls = true;
</script>

{#if n === 0}
	<div>No nodes</div>
{:else}
	{#if showControls}
		<div class="nw-layout-control" transition:scale>
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
				<div class="sliders">
					<label>
						Gravity: {gravity}
						<input type="range" min="0" max="1" step="0.01" bind:value={gravity} />
					</label>
					<label>
						Iterations: {numIter}
						<input type="range" min="1" max="1000" step="1" bind:value={numIter} />
					</label>
					<label>
						Initial Temperature: {initialTemp}
						<input type="range" min="10" max="2000" step="1" bind:value={initialTemp} />
					</label>
					<label>
						Cooling: {coolingFactor}
						<input type="range" min="0" max="1" step=".01" bind:value={coolingFactor} />
					</label>
					<label>
						Minimum Temperature: {minTemp}
						<input type="range" min="1" max="1000" step="1" bind:value={minTemp} />
					</label>
				</div>
			{/if}
		</div>
		<button class="close-button" on:click={() => (showControls = false)}>&#10006;</button>
	{:else}
		<button
			on:click={() => {
				showControls = true;
			}}
		>
			Controls</button
		>
	{/if}

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
								stroke-width={Math.min(10, 1 + Math.sqrt(getWeight(i, j, n, edgeWeights)))}
								stroke-opacity={Math.max(
									0.15,
									Math.min(0.95, 0.15 + 0.12 * Math.log1p(getWeight(i, j, n, edgeWeights)))
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
						<text text-anchor="middle" font-size={r} y={r * 0.2}> {lastWord(label)}</text>
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

	select {
		margin: 0.5rem 0;
	}

	ellipse {
		fill: var(--text-bg-2);
		stroke: rgb(var(--color-range-20));
		fill-opacity: 0.75;
	}

	line {
		stroke: rgb(var(--color-range-40));
	}

	text {
		font-weight: 600;
	}

	.sliders > label {
		display: flex;
		justify-content: space-between;
		width: 520px;
	}

	.sliders {
		display: flex;
		gap: 20px;
		flex-wrap: wrap;
	}

	#nw-container {
		width: 100%;
		height: 75svh;
	}
</style>
