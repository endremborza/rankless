<script lang="ts">
	import type { ShowcaseCoauthors } from '$lib/types/showcase';

	export let data: ShowcaseCoauthors;

	const W = 360;
	const H = 196;
	const RX = W * 0.37;
	const RY = H * 0.33;
	const MIN_R = 8;
	const MAX_R = 15;

	$: n = data.nodes.length;
	// A ring layout reads clearly at this size and is deterministic (no force-layout lib on the
	// home bundle); the hero is omitted, matching the live graph where it would link everyone.
	$: positions = data.nodes.map((_, i) => {
		const a = (i / n) * Math.PI * 2 - Math.PI / 2;
		return { x: W / 2 + Math.cos(a) * RX, y: H / 2 + Math.sin(a) * RY };
	});
	$: scoreMax = Math.max(1, ...data.nodes.map((d) => d.score));
	$: radii = data.nodes.map((d) => MIN_R + (d.score / scoreMax) * (MAX_R - MIN_R));
	$: weightMax = Math.max(1, ...data.edges.map((e) => e[2]));

	function lastWord(name: string): string {
		const parts = name.split(' ');
		return parts[parts.length - 1];
	}
</script>

<svg viewBox="0 0 {W} {H}" role="img" aria-label="Co-author network preview">
	{#each data.edges as [i, j, w] (`${i}-${j}`)}
		<line
			class="edge"
			x1={positions[i].x}
			y1={positions[i].y}
			x2={positions[j].x}
			y2={positions[j].y}
			stroke-width={1 + 2.5 * (w / weightMax)}
			stroke-opacity={0.3 + 0.5 * (w / weightMax)}
		/>
	{/each}
	{#each data.nodes as node, i (node.semanticId)}
		{@const label = lastWord(node.name)}
		<g transform="translate({positions[i].x},{positions[i].y})">
			<circle class="node" r={radii[i]} />
			<rect
				class="label-bg"
				x={-(label.length * 3.4 + 4)}
				y={radii[i] + 1}
				width={label.length * 6.8 + 8}
				height={14}
				rx={2}
			/>
			<text class="label" text-anchor="middle" y={radii[i] + 11}>{label}</text>
		</g>
	{/each}
</svg>

<style>
	svg {
		width: 100%;
		height: auto;
		display: block;
	}

	.edge {
		stroke: rgba(var(--color-range-40), 1);
	}

	.node {
		fill: rgba(var(--color-range-30), 0.32);
		stroke: rgb(var(--color-range-20));
		stroke-width: 1.6;
	}

	.label-bg {
		fill: var(--text-bg, #fff);
		fill-opacity: 0.85;
	}

	.label {
		fill: var(--color-text);
		font-size: 11px;
		font-weight: 300;
	}
</style>
