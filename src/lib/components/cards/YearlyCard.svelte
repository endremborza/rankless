<script lang="ts">
	import { getColor } from '$lib/style-util';
	import { FAINT, INK, INNER, MONO, MUTED, SANS, gutterWidth } from '$lib/utils/cards';
	import { compactCount, countGrid } from '$lib/utils/year-ticks';
	import GridLines from './GridLines.svelte';

	export let years: number[];
	export let cites: number[];
	export let papers: number[] | null;
	export let hl: number[];

	const TEXT = 15;
	const YEAR_SIZE = 17;
	const CAP = 46;
	const LANE = 36;
	const PAD_R = 6;
	const BAR_FRAC = 0.62;
	const MAX_BAR = 70;
	const CITE_SHARE = 0.6;
	const DIM = 0.35;
	const CITE_FILL = getColor(0.35);
	const PAPER_FILL = getColor(0.05);

	type Side = { values: number[]; max: number; base: number; h: number; dir: -1 | 1 };

	function side(values: number[], base: number, h: number, dir: -1 | 1): Side {
		return { values, max: Math.max(1, ...values), base, h, dir };
	}

	$: n = years.length;
	$: last = n - 1;
	$: barSpan = INNER.h - LANE - CAP * (papers ? 2 : 1);
	$: citeH = papers ? barSpan * CITE_SHARE : barSpan;
	$: citeBase = CAP + citeH;
	$: sides = [
		side(cites, citeBase, citeH, -1),
		...(papers ? [side(papers, citeBase + LANE, barSpan - citeH, 1)] : [])
	];
	$: grids = sides.flatMap((s) =>
		countGrid(s.max, s.h, TEXT).map(({ v, label }) => ({
			y: s.base + s.dir * (v / s.max) * s.h,
			label
		}))
	);
	$: gutter = gutterWidth(
		grids.map((g) => g.label),
		TEXT,
		14
	);
	$: pitch = (INNER.w - gutter - PAD_R) / n;
	$: barW = Math.min(MAX_BAR, pitch * BAR_FRAC);
	$: cx = (i: number) => gutter + pitch * (i + 0.5);
	$: marked = (i: number) => hl.includes(years[i]);
	$: shown = (i: number) => i === last || marked(i);
	$: opacity = (i: number) => (hl.length === 0 || marked(i) ? 1 : DIM);
	$: bars = sides.map((s) =>
		s.values.map((v) => {
			const len = (v / s.max) * s.h;
			const tip = s.base + s.dir * len;
			return { v, y: Math.min(s.base, tip), len, labelY: s.dir < 0 ? tip - 8 : tip + TEXT + 5 };
		})
	);
	$: seriesNames = [
		{ name: 'Citations', fill: CITE_FILL, y: 18 },
		...(papers ? [{ name: 'Papers', fill: PAPER_FILL, y: INNER.h - 8 }] : [])
	];
</script>

<svg viewBox="0 0 {INNER.w} {INNER.h}" xmlns="http://www.w3.org/2000/svg">
	<GridLines lines={grids} x1={gutter} x2={INNER.w - PAD_R} size={TEXT} gap={10} />
	{#each bars as side, si (si)}
		{#each side as b, i (i)}
			{#if b.len > 0}
				<rect
					x={cx(i) - barW / 2}
					y={b.y}
					width={barW}
					height={b.len}
					fill={si === 0 ? CITE_FILL : PAPER_FILL}
					opacity={opacity(i)}
				/>
			{/if}
		{/each}
		<line x1={gutter} x2={INNER.w - PAD_R} y1={sides[si].base} y2={sides[si].base} stroke={FAINT} />
	{/each}
	<g font-family={MONO} text-anchor="middle">
		{#each years as yr, i (i)}
			<text
				x={cx(i)}
				y={citeBase + LANE / 2 + YEAR_SIZE * 0.36}
				font-size={YEAR_SIZE}
				fill={marked(i) ? INK : MUTED}
				font-weight={marked(i) ? 700 : 400}>{yr}</text
			>
		{/each}
		{#each bars as side, si (si)}
			{#each side as b, i (i)}
				{#if shown(i)}
					<text x={cx(i)} y={b.labelY} font-size={TEXT} font-weight="700" fill={INK}
						>{compactCount(b.v)}</text
					>
				{/if}
			{/each}
		{/each}
	</g>
	<g font-family={SANS} font-size="17" fill={MUTED}>
		{#each seriesNames as s, i (i)}
			<rect x={gutter} y={s.y - 12} width="13" height="13" fill={s.fill} />
			<text x={gutter + 20} y={s.y}>{s.name}</text>
		{/each}
	</g>
</svg>
