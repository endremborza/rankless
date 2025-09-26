<script lang="ts">
	import {
		circleLayout,
		radialWeightedLayout,
		forceDirectedLayout,
		cytoscapeLayout,
		sigmaLayout,
		getIndex
	} from '$lib/network-util';
	import BrokenFittedText from './BrokenFittedText.svelte';

	export let nodes: string[] = [];
	export let nodeIntensities: number[] = [];
	export let edgeWeights: number[] = [];

	$: n = nodes.length;
	$: nodeScales = scaledNodeScalars(nodeIntensities, nodes);

	function getWeight(i: number, j: number) {
		const idx = getIndex(i, j, n);
		if (idx < 0 || idx >= edgeWeights.length) return 0;
		return edgeWeights[idx] || 0;
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

	let positions: {x: number; y: number}[] = [];

	let svgWidth: number;
	let svgHeight: number;

	const r = 14;
	const marge = 0.09;
	const height = 400;
	$: width = (height * svgWidth) / svgHeight;
	$: viewBox = `-${width * marge} -${height * marge} ${width * (1 + 2 * marge)} ${height * (1 + 2 * marge)
		}`;

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
		radial: radialWeightedLayout,
		force: forceDirectedLayout,
		cytoscape: cytoscapeLayout,
		sigma: sigmaLayout
	};
	const possFuns = Object.keys(layoutMap);
	let actFun: (typeof possFuns)[number] = 'cytoscape';
	$: posFun = layoutMap[actFun];
	$: positions = posFun(nodes, edgeWeights, options);
</script>

{#if n === 0}
<div>No nodes</div>
{:else}
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

<div class="sliders">
	<label>
		Ideal Edge Length: {idealEdgeLength}
		<input type="range" min="10" max="500" step="10" bind:value={idealEdgeLength} />
	</label>
	<label>
		Node Repulsion: {nodeRepulsion}
		<input type="range" min="100" max="20000" step="100" bind:value={nodeRepulsion} />
	</label>
	<label>
		Edge Elasticity: {edgeElasticity}
		<input type="range" min="1" max="500" step="1" bind:value={edgeElasticity} />
	</label>
	<label>
		Nesting Factor: {nestingFactor}
		<input type="range" min="0.5" max="5" step="0.1" bind:value={nestingFactor} />
	</label>
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

<div bind:clientWidth={svgWidth} bind:clientHeight={svgHeight} id="nw-container">
	<svg {viewBox} role="img" aria-label="Author Network">
		<!-- edges -->
		{#each Array(n) as _, i}
		{#each Array(n) as _, j}
		{#if j > i && getWeight(i, j) > 0}
		<line x1={positions[i].x} y1={positions[i].y} x2={positions[j].x} y2={positions[j].y}
			stroke-width={Math.min(10, 1 + Math.sqrt(getWeight(i, j)))} stroke-opacity={Math.max( 0.15,
			Math.min(0.95, 0.15 + 0.12 * Math.log1p(getWeight(i, j))) )} />
		{/if}
		{/each}
		{/each}

		{#each nodes as label, i}
		<g transform="translate({positions[i].x},{positions[i].y})">
			<ellipse rx={r} ry={r} stroke-width={(nodeScales[i] || 1) * 1.8} stroke-opacity={nodeScales[i]
				|| 1} />
			<text text-anchor="middle" font-size={r} y={r * 0.2}> {lastWord(label)}</text>
		</g>
		{/each}
	</svg>
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

	label {
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
