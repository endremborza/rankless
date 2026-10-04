<script lang="ts">
	import { getColor, getColorArr } from '$lib/style-util';
	import { coauthorYearDomain, makeTicks, type CoAuthor } from '$lib/utils/author-timeline';
	import { htmlToText } from '$lib/utils/paper-helpers';
	import {
		ACCENT,
		CHAR_W,
		HAIRLINE,
		INK,
		INNER,
		MONO,
		MUTED,
		SANS,
		clipToWidth,
		textWidth
	} from '$lib/utils/cards';

	export let rows: CoAuthor[];
	export let highlight: string[];

	const { w: W, h: H } = INNER;
	const AXIS_H = 30;
	const LEGEND_H = 34;
	const NAME_W = 230;
	const GAP = 18;
	const COUNT_W = 40;
	const TICK_SPACING = 96;
	const AXIS_SIZE = 14;
	const COUNT_HEAD = 'papers';
	const COUNT_HEAD_X = W - textWidth(COUNT_HEAD, AXIS_SIZE, CHAR_W.mono) - 12;
	const LEGEND_SIZE = 15;
	const BOLD_W = CHAR_W.sans * 1.1;
	const MARK = getColor(0.35);
	const BAR = `rgba(${getColorArr(0.4).join(',')}, 0.45)`;
	const HIT_RING = `rgba(${getColorArr(0.4).join(',')}, 0.3)`;

	$: rowH = Math.min(34, (H - LEGEND_H - AXIS_H) / rows.length);
	$: nameSize = Math.max(14, Math.min(18, rowH * 0.6));
	$: countSize = Math.min(nameSize, 16);
	$: rMax = Math.min(10, rowH * 0.36);
	$: x0 = NAME_W + GAP + rMax;
	$: x1 = W - COUNT_W - GAP - rMax;
	$: domain = coauthorYearDomain(rows);
	$: xOf = (year: number) => x0 + ((year - domain.lo) / domain.span) * (x1 - x0);
	$: ticks = makeTicks(domain, Math.max(2, Math.floor((x1 - x0) / TICK_SPACING))).filter(
		(t) => xOf(t) + textWidth(String(t), AXIS_SIZE, CHAR_W.mono) / 2 < COUNT_HEAD_X
	);
	$: markR = (n: number) => Math.min(rMax, 4 + (n - 1) * 1.5);
	$: hl = new Set(highlight);
	$: dim = hl.size > 0;
	$: bottom = AXIS_H + rowH * rows.length;
	$: legend = legendItems(bottom + LEGEND_H * 0.62);

	function nameText(row: CoAuthor, size: number, bold: boolean): string {
		return clipToWidth(htmlToText(row.name), NAME_W, size, bold ? BOLD_W : CHAR_W.sans);
	}

	function legendItems(y: number) {
		const labels = ['Shared papers', 'Includes a hit paper', 'Collaboration span'];
		let x = NAME_W + GAP;
		return labels.map((label, i) => {
			const item = { label, x, y, kind: i };
			x += 30 + textWidth(label, LEGEND_SIZE) + 36;
			return item;
		});
	}
</script>

<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
	<g font-family={MONO} font-size={AXIS_SIZE} fill={MUTED}>
		{#each ticks as t (t)}
			<text x={xOf(t)} y={AXIS_H - 12} text-anchor="middle">{t}</text>
			<line x1={xOf(t)} x2={xOf(t)} y1={AXIS_H - 6} y2={bottom} stroke={HAIRLINE} />
		{/each}
		<text x={W} y={AXIS_H - 12} text-anchor="end">{COUNT_HEAD}</text>
	</g>
	<line x1={0} x2={W} y1={AXIS_H} y2={AXIS_H} stroke={HAIRLINE} />

	{#each rows as row, i (row.key)}
		{@const on = hl.has(row.key)}
		{@const cy = AXIS_H + (i + 0.5) * rowH}
		<g opacity={dim && !on ? 0.5 : 1}>
			{#if on}
				<rect x={0} y={cy - rowH / 2} width={W} height={rowH} fill={ACCENT} fill-opacity="0.07" />
			{/if}
			<line
				x1={xOf(row.firstYear)}
				x2={Math.max(xOf(row.lastYear), xOf(row.firstYear) + 2)}
				y1={cy}
				y2={cy}
				stroke={BAR}
				stroke-width="4"
				stroke-linecap="round"
			/>
			{#each row.groups as g (g.year)}
				{@const r = markR(g.papers.length)}
				{#if g.hasHit}
					<circle
						cx={xOf(g.year)}
						{cy}
						r={r + 2.5}
						fill="none"
						stroke={HIT_RING}
						stroke-width="3"
					/>
				{/if}
				<circle cx={xOf(g.year)} {cy} {r} fill={g.hasHit ? ACCENT : MARK} />
			{/each}
		</g>
		<text
			x={NAME_W}
			y={cy + nameSize * 0.35}
			text-anchor="end"
			font-family={SANS}
			font-size={nameSize}
			font-weight={on ? 'bold' : 'normal'}
			fill={on || !dim ? INK : MUTED}>{nameText(row, nameSize, on)}</text
		>
		<text
			x={W}
			y={cy + countSize * 0.35}
			text-anchor="end"
			font-family={MONO}
			font-size={countSize}
			font-weight={on ? 'bold' : 'normal'}
			fill={on ? INK : MUTED}>{row.count}</text
		>
		<line x1={0} x2={W} y1={cy + rowH / 2} y2={cy + rowH / 2} stroke={HAIRLINE} />
	{/each}

	<g font-family={SANS} font-size={LEGEND_SIZE} fill={MUTED}>
		{#each legend as item (item.kind)}
			{#if item.kind === 0}
				<circle cx={item.x + 12} cy={item.y - 5} r="6" fill={MARK} />
			{:else if item.kind === 1}
				<circle
					cx={item.x + 12}
					cy={item.y - 5}
					r="8.5"
					fill="none"
					stroke={HIT_RING}
					stroke-width="3"
				/>
				<circle cx={item.x + 12} cy={item.y - 5} r="6" fill={ACCENT} />
			{:else}
				<line
					x1={item.x}
					x2={item.x + 24}
					y1={item.y - 5}
					y2={item.y - 5}
					stroke={BAR}
					stroke-width="4"
					stroke-linecap="round"
				/>
			{/if}
			<text x={item.x + 30} y={item.y}>{item.label}</text>
		{/each}
	</g>
</svg>
