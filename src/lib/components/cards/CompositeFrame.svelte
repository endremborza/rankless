<script lang="ts">
	import { APP_NAME } from '$lib/constants';
	import {
		ACCENT,
		CARD_MARGIN as M,
		CHAR_W,
		INK,
		INNER,
		MONO,
		MUTED,
		PAPER,
		SANS,
		SERIF,
		SPECTRUM,
		clipToWidth,
		fitSize
	} from '$lib/utils/cards';
	import { PANEL_HEAD, type CompositeLayout } from '$lib/utils/composite';

	// Several cards' pictures in a grid under one title. A panel's `body` is its kind's rendered
	// SVG, placed in the box its own card gives it; the title, strip and mark scale with the canvas.
	export let title: string;
	export let url: string;
	export let layout: CompositeLayout;
	export let panels: { heading: string; body: string }[];

	const TITLE_MAX = 76;
	const TITLE_MIN = 40;
	const HEADING_MAX = 24;
	const HEADING_MIN = 17;
	const STRIP_H = 8;

	$: ({ width, height, scale, slots } = layout);
	$: usable = width - 2 * M;
	$: titleSize = Math.max(
		TITLE_MIN * scale,
		fitSize(title, usable, TITLE_MAX * scale, CHAR_W.serif)
	);
	$: titleText = clipToWidth(title, usable, titleSize, CHAR_W.serif);
	$: urlText = clipToWidth(url, usable * 0.6, 20 * scale, CHAR_W.mono);
	$: headings = panels.map(({ heading }) => {
		const size = Math.max(HEADING_MIN, fitSize(heading, INNER.w, HEADING_MAX));
		return { size, text: clipToWidth(heading, INNER.w, size) };
	});
</script>

<svg {width} {height} viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
	<rect {width} {height} fill={PAPER} />
	{#each SPECTRUM as fill, i (i)}
		<rect
			x={(i * width) / SPECTRUM.length}
			y={0}
			width={width / SPECTRUM.length}
			height={STRIP_H * scale}
			{fill}
		/>
	{/each}
	<text x={M} y={100 * scale} font-family={SERIF} font-size={titleSize} fill={INK}>{titleText}</text
	>
	{#each panels as panel, i (i)}
		<text
			x={slots[i].x}
			y={slots[i].y + 28}
			font-family={SANS}
			font-size={headings[i].size}
			fill={MUTED}>{headings[i].text}</text
		>
		<svg x={slots[i].x} y={slots[i].y + PANEL_HEAD} width={INNER.w} height={INNER.h}>
			{@html panel.body}
		</svg>
	{/each}
	<text x={M} y={height - 34 * scale} font-family={SERIF} font-size={30 * scale} fill={INK}
		>{APP_NAME}</text
	>
	<text
		x={width - M}
		y={height - 36 * scale}
		text-anchor="end"
		font-family={MONO}
		font-size={20 * scale}
		fill={ACCENT}>{urlText}</text
	>
</svg>
