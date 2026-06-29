<script lang="ts">
	import { LATEST_YEAR, FONT_SIZE_PX } from '$lib/constants';
	import { getColor } from '$lib/style-util';
	import { formatNumber, shortYear } from '$lib/text-format-util';
	import TickBars from './TickBars.svelte';

	export let bottomStacks: number[];
	export let topStacks: number[];
	export let end: number = LATEST_YEAR;
	export let fullHeight: number; // container height in px
	export let fullWidth: number; // container width in px
	export let showBottom: boolean = true;

	const BAR_H = 2.4; // max bar height per side, in user units
	const CAP_EM = 1.5; // band above/below bars for series tag + hover value, in font-sizes
	const LANE_EM = 1.7; // central year-label lane, in font-sizes
	const RPAD_EM = 0.6; // right margin, in font-sizes
	const BAR_FRAC = 0.58; // bar width as a fraction of column pitch
	const TEXT_PX = FONT_SIZE_PX * 0.82; // target rendered text size
	const LABEL_EVERY = 2;

	// Round gridline values strictly inside (0, max) so bars can be gauged against them.
	function niceTicks(max: number, target = 3): number[] {
		if (max <= 0) return [];
		const raw = max / (target + 1);
		const mag = Math.pow(10, Math.floor(Math.log10(raw)));
		const norm = raw / mag;
		const step = (norm >= 5 ? 10 : norm >= 2.5 ? 5 : norm >= 2 ? 2.5 : norm >= 1 ? 2 : 1) * mag;
		const out: number[] = [];
		for (let v = step; v < max; v += step) out.push(v);
		return out;
	}

	let hover: number | null = null;

	$: n = topStacks.length || 1;
	$: years = Array.from({ length: n }, (_, i) => end - (n - 1) + i);
	$: topMax = Math.max(...topStacks, 1);
	$: botMax = Math.max(...bottomStacks, 1);

	// Keep text at a constant pixel size while the bars fill the (variable) container.
	// fullH(user) = fixedBars + bands*fontSize, and fontSize = (TEXT_PX/fullHeight)*fullH → closed form.
	$: s = fullHeight > 0 ? TEXT_PX / fullHeight : 0;
	$: bandEm = showBottom ? 2 * CAP_EM + LANE_EM : CAP_EM + LANE_EM;
	$: fullH = (showBottom ? 2 * BAR_H : BAR_H) / (1 - bandEm * s);
	$: fontSize = s * fullH;
	$: yearFont = fontSize * 0.9;
	$: tickFont = fontSize * 0.78;

	$: lane = LANE_EM * fontSize;
	$: cap = CAP_EM * fontSize;
	$: lineW = fontSize * 0.045;
	$: notch = fontSize * 0.3;
	$: gPad = fontSize * 0.45;
	$: dash = `${fontSize * 0.18} ${fontSize * 0.22}`;

	// Show only as many gridlines as fit without their labels colliding (one half's pixel height).
	$: halfPx = fullHeight > 0 && fullH > 0 ? BAR_H * (fullHeight / fullH) : 0;
	$: maxLabels = Math.min(3, Math.max(1, Math.floor(halfPx / (TEXT_PX * 1.7))));

	$: aspect = fullHeight > 0 ? fullWidth / fullHeight : 2.5;
	$: fullW = aspect * fullH;
	$: rpad = RPAD_EM * fontSize;
	// Size the left gutter to the widest gridline label so a big value (e.g. "1.5M") can't spill past
	// the viewBox's left edge and get clipped. Estimated from glyph count — SVG text isn't measurable.
	$: gridLabelChars = Math.max(
		0,
		...topGrid.map((g) => g.label.length),
		...(showBottom ? botGrid.map((g) => g.label.length) : [])
	);
	$: gutter = gPad + gridLabelChars * tickFont * 0.62 + tickFont * 0.3;
	$: plotW = fullW - gutter - rpad;
	// Inset bars so the first/last bar's edge (not centre) hits the plot edge — keeps fat bars from
	// overhanging into the left gutter where the axis numbers live.
	$: iMul = n > 1 ? plotW / (n - 1 + BAR_FRAC) : plotW;
	$: barW = iMul * BAR_FRAC;
	$: x0 = barW / 2;

	$: topBase = showBottom ? -lane / 2 : 0;
	$: botBase = lane / 2;
	$: yMin = topBase - BAR_H - cap;
	$: yearY = showBottom ? yearFont * 0.34 : lane * 0.62;

	$: topGrid = niceTicks(topMax, maxLabels).map((v) => ({
		y: topBase - (v / topMax) * BAR_H,
		label: formatNumber(v)
	}));
	$: botGrid = niceTicks(botMax, maxLabels).map((v) => ({
		y: botBase + (v / botMax) * BAR_H,
		label: formatNumber(v)
	}));

	$: hoverX = hover != null ? x0 + hover * iMul : 0;
	$: hoverTopTip = hover != null ? topBase - (topStacks[hover] / topMax) * BAR_H : 0;
	$: hoverBotTip = hover != null ? botBase + (bottomStacks[hover] / botMax) * BAR_H : 0;
	// Edge columns anchor inward so their hover values stay inside the plot (not over the gutter/edge).
	$: hoverAnchor = hover === 0 ? 'start' : hover === n - 1 ? 'end' : 'middle';
</script>

<!-- `fullHeight`/`fullWidth` ride bind:clientWidth/Height that read 0 mid-layout; let a 0 through and
	 fontSize cascades to NaN/Infinity SVG attrs. Require real dimensions. -->
{#if fullHeight > 0 && fullWidth > 0 && Number.isFinite(fullW) && fullW > 0}
	<svg viewBox="{-gutter} {yMin} {fullW} {fullH}" fill="currentColor">
		{#each [...topGrid, ...(showBottom ? botGrid : [])] as g, i (i)}
			<line
				class="grid"
				x1="0"
				x2={plotW}
				y1={g.y}
				y2={g.y}
				stroke-width={lineW}
				stroke-dasharray={dash}
			/>
			<text
				class="grid-label"
				x={-gPad}
				y={g.y - tickFont * 0.3}
				font-size={tickFont}
				text-anchor="end">{g.label}</text
			>
		{/each}

		{#if hover != null}
			<line
				class="crosshair"
				x1={hoverX}
				x2={hoverX}
				y1={topBase - BAR_H}
				y2={showBottom ? botBase + BAR_H : topBase}
				stroke-width={lineW}
			/>
		{/if}

		<g transform="translate({x0}, {topBase})">
			<TickBars
				nums={topStacks}
				color={getColor(0.35)}
				h={BAR_H}
				scaleMax={topMax}
				{iMul}
				{barW}
				hovered={hover}
				flip
			/>
		</g>
		{#if showBottom}
			<g transform="translate({x0}, {botBase})">
				<TickBars
					nums={bottomStacks}
					color={getColor(0.05)}
					h={BAR_H}
					scaleMax={botMax}
					{iMul}
					{barW}
					hovered={hover}
				/>
			</g>
		{/if}

		<line class="axis" x1="0" x2={plotW} y1={topBase} y2={topBase} stroke-width={lineW} />
		{#if showBottom}
			<line class="axis" x1="0" x2={plotW} y1={botBase} y2={botBase} stroke-width={lineW} />
		{/if}
		{#each years as yr, i (i)}
			<line
				class="axis"
				x1={x0 + i * iMul}
				x2={x0 + i * iMul}
				y1={topBase}
				y2={topBase + notch}
				stroke-width={lineW}
			/>
			{#if showBottom}
				<line
					class="axis"
					x1={x0 + i * iMul}
					x2={x0 + i * iMul}
					y1={botBase}
					y2={botBase - notch}
					stroke-width={lineW}
				/>
			{/if}
			{#if i % LABEL_EVERY === 0 && hover !== i}
				<text class="year" x={x0 + i * iMul} y={yearY} font-size={yearFont} text-anchor="middle"
					>{shortYear(yr)}</text
				>
			{/if}
		{/each}

		<!-- A hovered column's value lands anywhere across the cap band, so no static spot there is safe:
			 hide the series tags on hover (the bold value + year identify the column instead). -->
		{#if hover == null}
			<text class="series" x="0" y={yMin + cap * 0.62} font-size={fontSize}>citations</text>
			{#if showBottom}
				<text class="series" x="0" y={botBase + BAR_H + cap * 0.82} font-size={fontSize}
					>papers</text
				>
			{/if}
		{/if}

		{#if hover != null}
			<text
				class="hover-val"
				x={hoverX}
				y={hoverTopTip - fontSize * 0.45}
				font-size={fontSize}
				text-anchor={hoverAnchor}>{formatNumber(topStacks[hover])}</text
			>
			{#if showBottom}
				<text
					class="hover-val"
					x={hoverX}
					y={hoverBotTip + fontSize * 0.95}
					font-size={fontSize}
					text-anchor={hoverAnchor}>{formatNumber(bottomStacks[hover])}</text
				>
			{/if}
			<text class="hover-year" x={hoverX} y={yearY} font-size={yearFont} text-anchor="middle"
				>{shortYear(years[hover])}</text
			>
		{/if}

		{#each years as _, i (i)}
			<rect
				class="hit"
				x={x0 + i * iMul - iMul / 2}
				y={yMin}
				width={iMul}
				height={fullH}
				role="none"
				on:mouseover={() => (hover = i)}
				on:focus={() => (hover = i)}
				on:mouseleave={() => (hover = null)}
				on:focusout={() => (hover = null)}
			/>
		{/each}
	</svg>
{/if}

<style>
	/* Absolutely fill the container so the SVG never contributes to its parent's intrinsic height.
	   In flow, `height:100%` + the container's `aspect-ratio` + the `bind:clientHeight` ResizeObserver
	   form a measure→resize→measure loop in Chrome (figure grows vertically forever). */
	svg {
		position: absolute;
		inset: 0;
		display: block;
		height: 100%;
		width: 100%;
		color: var(--color-text);
	}

	text {
		pointer-events: none;
	}

	.grid {
		stroke: currentColor;
		opacity: 0.18;
	}

	.grid-label {
		opacity: 0.5;
	}

	.axis {
		stroke: currentColor;
		opacity: 0.4;
	}

	.crosshair {
		stroke: currentColor;
		opacity: 0.3;
	}

	.year {
		opacity: 0.6;
	}

	.hover-year {
		font-weight: 700;
	}

	.hover-val {
		font-weight: 700;
	}

	.series {
		opacity: 0.5;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.hit {
		fill: transparent;
		pointer-events: all;
	}
</style>
