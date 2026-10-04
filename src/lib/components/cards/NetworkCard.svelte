<script lang="ts">
	import { getColor, getColorArr } from '$lib/style-util';
	import { ACCENT, INK, INNER, MUTED, PAPER, SANS } from '$lib/utils/cards';
	import type { NetEdge, NetNode } from '$lib/server/cards/network';

	export let nodes: NetNode[];
	export let edges: NetEdge[];

	const { w: W, h: H } = INNER;
	const EDGE = getColor(0.4);
	const FILL = `rgba(${getColorArr(0.3).join(',')}, 0.32)`;
	const STROKE = getColor(0.2);
	const HALO = 6;

	$: dim = nodes.some((n) => n.on);
	$: order = [...nodes].sort((a, b) => Number(a.on) - Number(b.on));
</script>

<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
	{#each edges as e, i (i)}
		<line
			x1={e.x1}
			y1={e.y1}
			x2={e.x2}
			y2={e.y2}
			stroke={e.on ? ACCENT : EDGE}
			stroke-width={1 + 5 * e.rate}
			stroke-opacity={e.on ? 0.5 + 0.5 * e.rate : dim ? 0.08 + 0.15 * e.rate : 0.2 + 0.5 * e.rate}
		/>
	{/each}
	{#each order as n, i (i)}
		{#if n.on}
			<circle cx={n.x} cy={n.y} r={n.r + HALO} fill={ACCENT} fill-opacity="0.18" />
		{/if}
		<circle cx={n.x} cy={n.y} r={n.r} fill={PAPER} />
		<circle
			cx={n.x}
			cy={n.y}
			r={n.r}
			fill={FILL}
			stroke={n.on ? ACCENT : STROKE}
			stroke-width={n.on ? 3.5 : 1.8}
			opacity={dim && !n.on ? 0.4 : 1}
		/>
	{/each}
	<g font-family={SANS}>
		{#each order as n, i (i)}
			{#if n.label}
				{@const l = n.label}
				<rect
					x={l.box.x}
					y={l.box.y}
					width={l.box.w}
					height={l.box.h}
					rx="2"
					fill={PAPER}
					fill-opacity="0.85"
				/>
				<text
					x={l.x}
					y={l.y}
					text-anchor={l.anchor}
					font-size={l.size}
					font-weight={n.on ? 'bold' : 'normal'}
					fill={n.on || !dim ? INK : MUTED}>{l.text}</text
				>
			{/if}
		{/each}
	</g>
</svg>
