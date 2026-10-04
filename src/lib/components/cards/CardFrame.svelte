<script lang="ts">
	import type { Component } from 'svelte';
	import { APP_NAME } from '$lib/constants';
	import {
		ACCENT,
		CARD_H,
		CARD_MARGIN as M,
		CARD_W,
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

	// The one frame around every card kind: the entity's name, a caption saying what the picture
	// shows, the visualization in INNER, and the site's mark. Pure SVG with literal colours and
	// inlined faces, as the rasterizer resolves neither CSS variables nor scoped styles.
	export let name: string;
	export let caption: string;
	export let url: string;
	export let inner: Component<Record<string, unknown>>;
	export let props: Record<string, unknown>;

	const TITLE_MAX = 44;
	const TITLE_MIN = 28;
	const CAPTION_MAX = 21;
	const CAPTION_MIN = 17;
	const STRIP_H = 5;
	const usable = CARD_W - 2 * M;

	$: titleSize = Math.max(TITLE_MIN, fitSize(name, usable, TITLE_MAX, CHAR_W.serif));
	$: title = clipToWidth(name, usable, titleSize, CHAR_W.serif);
	$: captionSize = Math.max(CAPTION_MIN, fitSize(caption, usable, CAPTION_MAX, CHAR_W.sans));
	$: captionText = clipToWidth(caption, usable, captionSize, CHAR_W.sans);
	$: urlText = clipToWidth(url, usable * 0.6, 19, CHAR_W.mono);
	const strips = SPECTRUM.map((fill, i) => ({
		fill,
		x: (i * CARD_W) / SPECTRUM.length,
		w: CARD_W / SPECTRUM.length
	}));
</script>

<svg
	width={CARD_W}
	height={CARD_H}
	viewBox="0 0 {CARD_W} {CARD_H}"
	xmlns="http://www.w3.org/2000/svg"
>
	<rect width={CARD_W} height={CARD_H} fill={PAPER} />
	{#each strips as s, i (i)}
		<rect x={s.x} y={0} width={s.w} height={STRIP_H} fill={s.fill} />
	{/each}
	<text x={M} y={72} font-family={SERIF} font-size={titleSize} fill={INK}>{title}</text>
	<text x={M} y={106} font-family={SANS} font-size={captionSize} fill={MUTED}>{captionText}</text>
	<svg x={INNER.x} y={INNER.y} width={INNER.w} height={INNER.h}>
		<svelte:component this={inner} {...props} />
	</svg>
	<text x={M} y={CARD_H - 30} font-family={SERIF} font-size="26" fill={INK}>{APP_NAME}</text>
	<text
		x={CARD_W - M}
		y={CARD_H - 32}
		text-anchor="end"
		font-family={MONO}
		font-size="19"
		fill={ACCENT}>{urlText}</text
	>
</svg>
