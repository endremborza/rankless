<script lang="ts">
	import { APP_NAME, BRAND_STATS, BRAND_TAGLINE } from '$lib/constants';
	import {
		ACCENT,
		CARD_H,
		CARD_W,
		INK,
		MUTED,
		PAPER,
		MONO as FONT_MONO,
		SANS as FONT_SANS,
		SERIF as FONT_DISPLAY,
		SPECTRUM
	} from '$lib/utils/cards';

	// The homepage OG card, rendered like every card (see `$lib/utils/cards`); Julia can restyle
	// this single component.
	export let width = CARD_W;
	export let height = CARD_H;
	// Live figures from /counts, formatted by the caller; falls back to brand constants.
	export let stats: string[] = BRAND_STATS;

	const M = 80;
	const BAR_Y = 432;
	const BAR_H = 92;
	const GAP = 6;
	const WEIGHTS = [0.3, 0.21, 0.16, 0.12, 0.09, 0.07, 0.05];

	const usable = width - 2 * M - GAP * (WEIGHTS.length - 1);
	let cursor = M;
	const segments = WEIGHTS.map((w, i) => {
		const segW = w * usable;
		const seg = { x: cursor, w: segW, fill: SPECTRUM[i] };
		cursor += segW + GAP;
		return seg;
	});
	const statsLine = stats.join('  ·  ');
</script>

<svg {width} {height} viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
	<rect {width} {height} fill={PAPER} />
	<text x={M} y="178" font-family={FONT_DISPLAY} font-size="104" fill={INK}>{APP_NAME}</text>
	<text x={M + 2} y="262" font-family={FONT_SANS} font-size="46" fill={MUTED}>{BRAND_TAGLINE}.</text
	>
	<text x={M + 2} y="350" font-family={FONT_MONO} font-size="33" font-weight="700" fill={ACCENT}
		>{statsLine}</text
	>
	{#each segments as s, i (i)}
		<rect x={s.x} y={BAR_Y} width={s.w} height={BAR_H} rx="6" fill={s.fill} />
	{/each}
	<text x={width - M} y="586" text-anchor="end" font-family={FONT_MONO} font-size="30" fill={ACCENT}
		>rankless.org</text
	>
</svg>
