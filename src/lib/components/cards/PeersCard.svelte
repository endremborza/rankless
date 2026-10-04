<script lang="ts">
	import type { ShowcasePeers } from '$lib/types/showcase';
	import { abbrSfName } from '$lib/peers-utils';
	import { getColor } from '$lib/style-util';
	import {
		FAINT,
		INK,
		INNER,
		MONO,
		MUTED,
		SANS,
		clipToWidth,
		gutterWidth,
		textWidth
	} from '$lib/utils/cards';
	import { countGrid, seriesYears } from '$lib/utils/year-ticks';
	import GridLines from './GridLines.svelte';

	export let heroName: ShowcasePeers['heroName'];
	export let peerName: ShowcasePeers['peerName'];
	export let peerCountry: ShowcasePeers['peerCountry'];
	export let subfields: ShowcasePeers['subfields'];
	export let yearFrom: ShowcasePeers['yearFrom'];
	export let heroYearly: ShowcasePeers['heroYearly'];
	export let peerYearly: ShowcasePeers['peerYearly'];

	const HERO_FILL = getColor(0.4);
	const PEER_FILL = getColor(0.15);
	const LEGEND_SIZE = 20;
	const TITLE_SIZE = 17;
	const TEXT = 15;
	const PLOT_TOP = 92;
	const BASE = INNER.h - 46;
	const PLOT_H = BASE - PLOT_TOP;
	const PANEL_GAP = 48;
	const FIELD_W = (INNER.w - PANEL_GAP) * 0.54;
	const NAME_W = INNER.w * 0.36;
	const PAIR_FRAC = 0.74;
	const MAX_BAR = 64;
	const FULL_NAMES = 3;
	const YEAR_EVERY = 2;

	type Panel = {
		title: string;
		x: number;
		w: number;
		groups: { hero: number; peer: number }[];
		labels: (i: number, width: number) => string[];
		face: string;
	};

	// A field's full name where it fits its group (on two lines for the top fields), else its
	// abbreviation.
	function fieldLines(name: string, pos: number, width: number): string[] {
		const fits = (line: string) => textWidth(line, TEXT) <= width;
		if (fits(name)) return [name];
		const words = name.split(' ');
		const cut = Math.ceil(words.length / 2);
		const two = [words.slice(0, cut).join(' '), words.slice(cut).join(' ')];
		if (pos < FULL_NAMES && words.length > 1 && two.every(fits)) return two;
		return [abbrSfName(name)];
	}

	function layout(p: Panel) {
		const max = Math.max(1, ...p.groups.flatMap((g) => [g.hero, g.peer]));
		const ticks = countGrid(max, PLOT_H, TEXT);
		const gutter = gutterWidth(
			ticks.map((t) => t.label),
			TEXT,
			12
		);
		const pitch = (p.w - gutter) / p.groups.length;
		const barW = Math.min(MAX_BAR, (pitch * PAIR_FRAC) / 2);
		const h = (v: number) => (v / max) * PLOT_H;
		return {
			...p,
			plotX: p.x + gutter,
			grid: ticks.map(({ v, label }) => ({ y: BASE - h(v), label })),
			cols: p.groups.map((g, i) => {
				const cx = p.x + gutter + pitch * (i + 0.5);
				return {
					cx,
					lines: p.labels(i, pitch - 8),
					bars: [
						{ x: cx - barW, h: h(g.hero), fill: HERO_FILL },
						{ x: cx, h: h(g.peer), fill: PEER_FILL }
					]
				};
			}),
			barW
		};
	}

	$: years = seriesYears(heroYearly.length, yearFrom + heroYearly.length - 1);
	$: panels = [
		{
			title: 'Citations by field',
			x: 0,
			w: FIELD_W,
			groups: subfields,
			labels: (i: number, width: number) => fieldLines(subfields[i].name, i, width),
			face: SANS
		},
		{
			title: 'Citations by year',
			x: FIELD_W + PANEL_GAP,
			w: INNER.w - FIELD_W - PANEL_GAP,
			groups: heroYearly.map((hero, i) => ({ hero, peer: peerYearly[i] ?? 0 })),
			labels: (i: number) => ((years.length - 1 - i) % YEAR_EVERY === 0 ? [String(years[i])] : []),
			face: MONO
		}
	].map(layout);

	$: hero = clipToWidth(heroName, NAME_W, LEGEND_SIZE);
	$: peer = clipToWidth(peerName, NAME_W, LEGEND_SIZE);
</script>

<svg viewBox="0 0 {INNER.w} {INNER.h}" xmlns="http://www.w3.org/2000/svg">
	<text x="0" y="21" font-family={SANS} font-size={LEGEND_SIZE} fill={INK}
		><tspan fill={HERO_FILL}>■</tspan><tspan dx="8">{hero}</tspan><tspan dx="18" fill={MUTED}
			>vs</tspan
		><tspan dx="18" fill={PEER_FILL}>■</tspan><tspan dx="8">{peer}</tspan>{#if peerCountry}<tspan
				dx="10"
				fill={MUTED}>· {peerCountry}</tspan
			>{/if}</text
	>
	{#each panels as p, pi (pi)}
		<text x={p.plotX} y={PLOT_TOP - 22} font-family={SANS} font-size={TITLE_SIZE} fill={MUTED}
			>{p.title}</text
		>
		<GridLines lines={p.grid} x1={p.plotX} x2={p.x + p.w} size={TEXT} gap={8} />
		{#each p.cols as c, ci (ci)}
			{#each c.bars as b, bi (bi)}
				{#if b.h > 0}
					<rect x={b.x} y={BASE - b.h} width={p.barW} height={b.h} fill={b.fill} />
				{/if}
			{/each}
			{#each c.lines as line, li (li)}
				<text
					x={c.cx}
					y={BASE + 22 + li * (TEXT + 3)}
					text-anchor="middle"
					font-family={p.face}
					font-size={TEXT}
					fill={MUTED}>{line}</text
				>
			{/each}
		{/each}
		<line x1={p.plotX} x2={p.x + p.w} y1={BASE} y2={BASE} stroke={FAINT} />
	{/each}
</svg>
