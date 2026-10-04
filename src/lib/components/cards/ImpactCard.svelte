<script lang="ts">
	import { ACCENT, HAIRLINE, INK, INNER, MONO, MUTED, PAPER, SANS } from '$lib/utils/cards';
	import { CHIP, ROWS, type Chip, type ImpactLayout } from '$lib/utils/impact-card';

	// Citing hit papers on top, the author's papers they cite (tinted, an accent bar) at the bottom,
	// a curve for every citation between the two rows.
	export let layout: ImpactLayout;
	export let summary: string;
	export let ownLabel: string;

	const OWN_FILL = '#f3f8fc';

	$: rows = [
		...layout.top.map((c) => ({ c, own: false })),
		...layout.bottom.map((c) => ({ c, own: true }))
	];
	const titleY = (c: Chip, i: number) => c.y + CHIP.pad + 13 + i * CHIP.line;
	const badgeY = (c: Chip) => c.y + CHIP.h - CHIP.pad - CHIP.badgeH;
</script>

<svg viewBox="0 0 {INNER.w} {INNER.h}" xmlns="http://www.w3.org/2000/svg">
	<text x={0} y={ROWS.summaryY} font-family={SANS} font-size="16" fill={MUTED}>{summary}</text>

	<g fill="none" stroke={MUTED} stroke-width="1.5" opacity="0.5">
		{#each layout.edges as d, i (i)}
			<path {d} />
		{/each}
	</g>

	{#each rows as { c, own }, i (i)}
		<g font-family={SANS}>
			<rect
				x={c.x}
				y={c.y}
				width={c.w}
				height={CHIP.h}
				rx="6"
				fill={own ? OWN_FILL : PAPER}
				stroke={own ? ACCENT : HAIRLINE}
				stroke-width="1.5"
			/>
			{#if own}
				<rect x={c.x} y={c.y} width="5" height={CHIP.h} rx="2" fill={ACCENT} />
			{/if}
			{#each c.lines as line, j (j)}
				<text x={c.x + CHIP.pad} y={titleY(c, j)} font-size={CHIP.titleSize} fill={INK}>{line}</text
				>
			{/each}
			<text
				x={c.x + CHIP.pad}
				y={badgeY(c) + 15}
				font-family={MONO}
				font-size={CHIP.metaSize}
				fill={MUTED}>{c.year}<tspan font-family={SANS} dx="10">{c.journal}</tspan></text
			>
			{#each c.badges as b, j (j)}
				<rect x={b.x} y={badgeY(c)} width={b.w} height={CHIP.badgeH} rx="4" fill={b.fill} />
				<text
					x={b.x + b.w / 2}
					y={badgeY(c) + 14.5}
					text-anchor="middle"
					font-size={CHIP.badgeSize}
					fill={b.ink}>{b.label}</text
				>
			{/each}
		</g>
	{/each}

	<text
		x={INNER.w / 2}
		y={ROWS.labelY}
		text-anchor="middle"
		font-family={SANS}
		font-size="15"
		fill={MUTED}>{ownLabel}</text
	>
</svg>
