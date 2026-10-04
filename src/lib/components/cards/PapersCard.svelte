<script context="module" lang="ts">
	export type PaperRow = {
		year: number;
		journal: string;
		citations: number;
		rate: number;
		hl: boolean;
	};
</script>

<script lang="ts">
	import { getColor } from '$lib/style-util';
	import { formatNumber } from '$lib/text-format-util';
	import { htmlToText } from '$lib/utils/paper-helpers';
	import { wrapLines } from '$lib/utils/cards';
	import { CHAR_W, HAIRLINE, INK, INNER, MONO, MUTED, PAPER, SANS, clip } from '$lib/utils/cards';
	import { tipLabelPos, xBase, yBase, type FigureBasis } from '$lib/utils/paper-rainbow';

	// The page's rainbow in card pixels: the chart space scaled by SX × SY (line widths are in chart
	// units, so they vary within the ratio of the two), the highlighted paper's title in a band
	// above the plot, the y labels right of the plot as on the page, the top papers beyond them.
	// The value at the highlighted line's tip is drawn only where it has room right of the tip; the
	// band states it either way.
	export let basis: FigureBasis;
	export let hl: number;
	export let rows: PaperRow[];
	export let listTitle: string;
	export let yearRange: [number, number];

	const SX = 22;
	const SY = 23.5;
	const UNIT = Math.sqrt(SX * SY);
	const PLOT_X = 4;
	const PLOT_TOP = 80;
	const BASE_Y = PLOT_TOP + yBase * SY;
	const PLOT_R = PLOT_X + xBase * SX;
	const TITLE_SIZE = 18;
	const TITLE_LINE = 22;
	const TITLE_CHARS = Math.floor((xBase * SX) / (TITLE_SIZE * CHAR_W.sans));
	const LIST_X = PLOT_R + 80;
	const ROW_SIZE = 16;
	const ROW_H = 36;
	const ROW_TOP = 50;
	const SWATCH = 22;
	const ROW_CHARS = Math.floor((INNER.w - LIST_X - SWATCH - 10) / (ROW_SIZE * CHAR_W.sans));
	const LEGEND_W = 170;
	const LEGEND_STOPS = [0, 0.25, 0.5, 0.75, 1].map((r) => ({ offset: r, color: getColor(r) }));

	const px = (x: number) => PLOT_X + x * SX;
	const py = (y: number) => BASE_Y + y * SY;

	$: others = basis.figPapers.filter((p) => p.i !== hl);
	$: hp = basis.figPapers.find((p) => p.i === hl)!;
	$: tip = tipLabelPos(hp);
	$: titleLines = wrapLines(htmlToText(hp.name), TITLE_CHARS, 2);
	$: metaY = 18 + titleLines.length * TITLE_LINE;
	$: legendY = ROW_TOP + rows.length * ROW_H + 10;

	function rowText(r: PaperRow): string {
		const head = `${r.year} · `;
		const tail = ` · ${formatNumber(r.citations)} cites`;
		return `${head}${clip(r.journal, ROW_CHARS - head.length - tail.length)}${tail}`;
	}
</script>

<svg viewBox="0 0 {INNER.w} {INNER.h}" xmlns="http://www.w3.org/2000/svg">
	<defs>
		<linearGradient id="papers-card-years">
			{#each LEGEND_STOPS as s, i (i)}
				<stop offset={s.offset} stop-color={s.color} />
			{/each}
		</linearGradient>
	</defs>

	<g font-family={SANS} fill={INK}>
		{#each titleLines as line, i (i)}
			<text x={PLOT_X} y={18 + i * TITLE_LINE} font-size={TITLE_SIZE}>{line}</text>
		{/each}
		<line
			x1={PLOT_X + 2}
			y1={metaY - 5}
			x2={PLOT_X + 2 + SWATCH}
			y2={metaY - 5}
			stroke={getColor(hp.rate)}
			stroke-width="5"
			stroke-linecap="round"
		/>
		<text x={PLOT_X + SWATCH + 10} y={metaY} font-family={MONO} font-size="15" fill={MUTED}
			>{hp.year} · {formatNumber(hp.citations)} citations</text
		>
	</g>

	<g stroke={HAIRLINE} stroke-width="1">
		{#each basis.yTicks as t, i (i)}
			<line x1={PLOT_X} y1={py(t.y)} x2={PLOT_R} y2={py(t.y)} />
		{/each}
	</g>

	<g
		transform="translate({PLOT_X} {BASE_Y}) scale({SX} {SY})"
		fill="none"
		stroke-linecap="round"
		stroke-linejoin="round"
	>
		{#each others as p, i (i)}
			<path d={p.path} stroke={getColor(p.rate)} stroke-width={2.2 / UNIT} opacity="0.45" />
		{/each}
		<path d={hp.path} stroke={getColor(hp.rate)} stroke-width={5 / UNIT} />
	</g>

	<g font-family={MONO} font-size="14" fill={MUTED}>
		<line x1={PLOT_X} y1={BASE_Y} x2={PLOT_R} y2={BASE_Y} stroke={INK} stroke-width="1.5" />
		{#each basis.yearTicks as t, i (i)}
			<line
				x1={px(t.x)}
				y1={BASE_Y}
				x2={px(t.x)}
				y2={BASE_Y + (t.name === undefined ? 4 : 8)}
				stroke={INK}
				stroke-width="1.2"
			/>
			{#if t.name !== undefined}
				<text x={px(t.x)} y={BASE_Y + 24} text-anchor="middle">{t.name}</text>
			{/if}
		{/each}
		{#each basis.yTicks as t, i (i)}
			<line x1={PLOT_R} y1={py(t.y)} x2={PLOT_R + 7} y2={py(t.y)} stroke={INK} stroke-width="1.2" />
			<text x={PLOT_R + 12} y={py(t.y) + 5}>{t.label}</text>
		{/each}
		<text x={PLOT_R + 12} y={PLOT_TOP - 14} font-family={SANS} font-size="15">citations</text>
		<text
			x={(PLOT_X + PLOT_R) / 2}
			y={BASE_Y + 46}
			text-anchor="middle"
			font-family={SANS}
			font-size="15">years since publication</text
		>
		{#if tip.anchor === 'start'}
			<text
				x={px(tip.x) + 4}
				y={py(tip.y)}
				font-size="15"
				fill={INK}
				stroke={PAPER}
				stroke-width="4"
				paint-order="stroke">{formatNumber(hp.citations)}</text
			>
		{/if}
	</g>

	<g font-family={SANS} font-size={ROW_SIZE}>
		<text x={LIST_X} y={18} font-size="15" fill={MUTED}>{listTitle}</text>
		{#each rows as r, i (i)}
			<line
				x1={LIST_X}
				y1={ROW_TOP - 6 + i * ROW_H}
				x2={LIST_X + SWATCH}
				y2={ROW_TOP - 6 + i * ROW_H}
				stroke={getColor(r.rate)}
				stroke-width={r.hl ? 6 : 4}
				stroke-linecap="round"
				opacity={r.hl ? 1 : 0.6}
			/>
			<text
				x={LIST_X + SWATCH + 10}
				y={ROW_TOP + i * ROW_H}
				fill={r.hl ? INK : MUTED}
				font-weight={r.hl ? 'bold' : 'normal'}>{rowText(r)}</text
			>
		{/each}
	</g>

	<g font-size="14" fill={MUTED}>
		<text x={LIST_X} y={legendY + 20} font-family={SANS} font-size="15">publication year</text>
		<rect x={LIST_X} y={legendY + 32} width={LEGEND_W} height="10" fill="url(#papers-card-years)" />
		<text x={LIST_X} y={legendY + 62} font-family={MONO}>{yearRange[0]}</text>
		<text x={LIST_X + LEGEND_W} y={legendY + 62} font-family={MONO} text-anchor="end"
			>{yearRange[1]}</text
		>
	</g>
</svg>
