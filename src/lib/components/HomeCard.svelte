<script lang="ts">
	import { APP_NAME, BRAND_STATS, BRAND_TAGLINE } from '$lib/constants';

	// Rendered server-side to a standalone SVG and rasterized to the homepage OG card, so everything
	// is inlined: no <style> (would emit scoped classes), no CSS vars. The brand fonts must be
	// installed on the rasterizer host (deploy.py vendors static/fonts/ into fontconfig); each
	// family lists a generic fallback so the card still renders if a face is missing. Julia can
	// restyle this single component.
	export let width = 1200;
	export let height = 630;
	// Live figures from /counts, formatted by the caller; falls back to brand constants.
	export let stats: string[] = BRAND_STATS;

	// Canonical brand spectrum (matches pyscripts/poster_figures.py SPECTRUM + the breakdown palette).
	const SPECTRUM = ['#0dc6f3', '#269ada', '#5842a8', '#7d0082', '#af5850', '#e1b01e', '#fadc05'];
	// Revamp typeface set: serif for the wordmark, sans for prose, mono for data/url.
	const FONT_DISPLAY = "'Hedvig Letters Serif', serif";
	const FONT_SANS = "'Hedvig Letters Sans', sans-serif";
	const FONT_MONO = "'Space Mono', monospace";
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
	<rect {width} {height} fill="#ffffff" />
	<text x={M} y="178" font-family={FONT_DISPLAY} font-size="104" fill="#21272a">{APP_NAME}</text>
	<text x={M + 2} y="262" font-family={FONT_SANS} font-size="46" fill="#4f4f4f"
		>{BRAND_TAGLINE}.</text
	>
	<text x={M + 2} y="350" font-family={FONT_MONO} font-size="33" font-weight="700" fill="#1f8fd0"
		>{statsLine}</text
	>
	{#each segments as s, i (i)}
		<rect x={s.x} y={BAR_Y} width={s.w} height={BAR_H} rx="6" fill={s.fill} />
	{/each}
	<text
		x={width - M}
		y="586"
		text-anchor="end"
		font-family={FONT_MONO}
		font-size="30"
		fill="#1f8fd0">rankless.org</text
	>
</svg>
