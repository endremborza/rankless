<script lang="ts">
	import { circleLayout, radialWeightedLayout, forceDirectedLayout } from '$lib/network-util';
	import BrokenFittedText from './BrokenFittedText.svelte';

	export let nodes: string[] = [];
	export let edgeWeights: number[] = [];

	$: n = nodes.length;

	function getIndex(i: number, j: number) {
		if (i === j) return -1;
		if (i > j) [i, j] = [j, i];
		return i * n + j - 1; // i < j
	}

	function getWeight(i: number, j: number) {
		const idx = getIndex(i, j);
		if (idx < 0 || idx >= edgeWeights.length) return 0;
		return edgeWeights[idx] || 0;
	}

	const size = 400;
	const r = 14;
	const marge = 0.12;

	// available layouts
	const possFuns = ['circle', 'radial', 'force'] as const;
	let actFun: (typeof possFuns)[number] = 'circle';

	// mapping from name → function
	const layoutMap = {
		circle: circleLayout,
		radial: radialWeightedLayout,
		force: forceDirectedLayout
	};

	// reactive positions
	$: posFun = layoutMap[actFun];
	$: positions = posFun(nodes, edgeWeights, size);
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

	<svg
		viewBox={`-${size * marge} -${size * marge} ${size * (1 + 2 * marge)} ${
			size * (1 + 2 * marge)
		}`}
		role="img"
		aria-label="Author Network"
	>
		<!-- edges -->
		{#each Array(n) as _, i}
			{#each Array(n) as _, j}
				{#if j > i && getWeight(i, j) > 0}
					<line
						x1={positions[i].x}
						y1={positions[i].y}
						x2={positions[j].x}
						y2={positions[j].y}
						stroke="black"
						stroke-width={Math.min(10, 1 + Math.sqrt(getWeight(i, j)))}
						stroke-opacity={Math.max(
							0.15,
							Math.min(0.95, 0.15 + 0.12 * Math.log1p(getWeight(i, j)))
						)}
					/>
				{/if}
			{/each}
		{/each}

		<!-- nodes -->
		{#each nodes as label, i}
			<g>
				<ellipse
					cx={positions[i].x}
					cy={positions[i].y}
					rx={r * 2.4}
					ry={r}
					fill-opacity="0.8"
					stroke="black"
					stroke-width="1.1"
				/>
				<BrokenFittedText
					text={label}
					height={r * 1.4}
					width={r * 3}
					x={positions[i].x}
					y={positions[i].y + r * 0.62}
					anchor="center"
					bottomAligned={false}
				/>
			</g>
		{/each}
	</svg>
{/if}

<style>
	svg {
		width: 100%;
		height: 100%;
		display: block;
	}
	select {
		margin: 0.5rem 0;
	}
	ellipse {
		fill: var(--text-bg-2);
	}
</style>
