<script lang="ts">
	import {getSankeyPath, type Point} from '$lib/visual-util';
	import osuInst from '$lib/assets/data/osu-inst.json';
	import BrokenFittedText from './BrokenFittedText.svelte';
	import {formatNumber} from '$lib/text-format-util';

	export let sWidth: number;
	export let sHeight: number;
	export let isWideScreen: boolean;
	export let ratePin: (s: number, e: number, os: number) => number;
	export let rateScale: (s: number, f: number) => number;

	type pDef = {
		cTop: Point;
		cBot: Point;
		widths: {parent: number; child: number};
		bottomStretch: number;
		topStretch: number;
	};
	const toP = (o: pDef) => getSankeyPath(o.cTop, o.cBot, o.widths, o.bottomStretch, o.topStretch);

	let pad = 0.4;

	function topPlus(pO: pDef) {
		return pO.cTop.x + pO.widths.parent + pad;
	}
	function botPlus(pO: pDef) {
		return pO.cBot.x + pO.widths.child + pad;
	}

	function cText(n: number) {
		return `${formatNumber(n)} citations`;
	}

	$: h = sHeight / sWidth;

	$: phaseTwo = rateScale(6.6, 0.8);

	$: topExtension = (1 - rateScale(3, 2)) * 150 * h;
	$: y = 3 * h + topExtension - phaseTwo * 10 * h;

	// width is normalized to 100
	// height is measured in 100h
	// should be basically the screen

	$: l1Bottom = 10 * h;
	function getS(c: {weight: number}[]): number {
		let o = 0;
		for (let i = 0; i < c.length; i++) {
			const ch = c[i];
			o += ch.weight;
		}
		return o;
	}
	function getL(
		c: {children: {weight: number; name: string}[]}[]
	): {name: string; weight: number}[] {
		const o = [];
		for (let i = 0; i < c.length; i++) {
			for (let j = 0; j < c[i].children.length; j++) {
				o.push(c[i].children[j]);
			}
		}
		return o;
	}
	$: osuSum = getS(osuInst);

	$: p1Obj = {
		cTop: {x: 65, y},
		cBot: {x: 15, y: y + 50 * h - phaseTwo * 25 * h},
		widths: {parent: 4, child: (osuInst[0].weight / osuSum) * 17},
		bottomStretch: l1Bottom,
		topStretch: 2.5 * h + topExtension
	};

	$: p2Obj = {
		cTop: {x: topPlus(p1Obj), y},
		cBot: {x: botPlus(p1Obj), y: p1Obj.cBot.y},
		widths: {parent: 5, child: (osuInst[1].weight / osuSum) * 17},
		bottomStretch: l1Bottom,
		topStretch: 2.5 + topExtension
	};

	$: p1 = toP(p1Obj);
	$: p2 = toP(p2Obj);

	$: bottomStretch = 15 * h;
	$: topStretch = 3 * h;
	$: l2end = 75 * h;

	$: osuL2 = getL(osuInst);
	$: l2Sum = getS(osuL2);

	$: getL2Obj = (tOff: number, bOff: number, parent: number, i: number) => ({
		cTop: {x: tOff, y: p1Obj.cBot.y + p1Obj.bottomStretch + topStretch + pad},
		cBot: {x: bOff, y: l2end},
		widths: {parent, child: ((osuL2[i] || {weight: 0}).weight / l2Sum) * 43},
		bottomStretch,
		topStretch
	});

	$: p11Obj = getL2Obj(p1Obj.cBot.x, 2, 2, 0);
	$: p12Obj = getL2Obj(topPlus(p11Obj), botPlus(p11Obj), 7.5, 1);
	$: p13Obj = getL2Obj(
		topPlus(p12Obj),
		botPlus(p12Obj),
		p1Obj.widths.child - p11Obj.widths.parent - p12Obj.widths.parent - 2 * pad,
		2
	);

	$: p21Obj = getL2Obj(p2Obj.cBot.x, botPlus(p13Obj), 2, 3);
	$: p22Obj = getL2Obj(topPlus(p21Obj), botPlus(p21Obj), 1, 4);
	$: p23Obj = getL2Obj(
		topPlus(p22Obj),
		botPlus(p22Obj),
		p2Obj.widths.child - p21Obj.widths.parent - p22Obj.widths.parent - 2 * pad,
		5
	);
</script>

<svg viewBox="0 0 100 {100 * h}" xmlns="http://www.w3.org/2000/svg" width="100%" height="110svh"
	style="top: {ratePin(3.15, 8, -0.05)}px">
	<path d={p1} style="fill: rgb(var(--color-range-25));" opacity="75%" />
	<path d={p2} style=" fill: rgb(var(--color-range-75));" opacity="75%" />
	{#each [{ pO: p11Obj, cR: 5 }, { pO: p12Obj, cR: 20 }, { pO: p13Obj, cR: 50 }, { pO: p21Obj, cR: 60 }, { pO:
	p22Obj, cR: 70 }, { pO: p23Obj, cR: 90 }] as { pO, cR }, i}
	<path d={toP(pO)} style=" fill: rgb(var(--color-range-{cR}));" opacity="{phaseTwo * 75}%" />
	<g opacity="{Math.pow(phaseTwo, 2) * 100}%">
		<BrokenFittedText x={pO.cBot.x + pad} y={pO.cBot.y + bottomStretch / 2.5} text={osuL2[i].name}
			height={bottomStretch / 2.6} width={pO.widths.child - 2 * pad} />
		<BrokenFittedText x={pO.cBot.x + pO.widths.child * 0.05} y={pO.cBot.y + bottomStretch - pad}
			text={cText(osuL2[i].weight)} height={bottomStretch / 2} width={pO.widths.child * 0.9} />
	</g>
	{/each}
	<g opacity="{Math.pow(phaseTwo, 2) * 100}%">
		{#each [p1Obj, p2Obj] as pO, i}
		<BrokenFittedText x={pO.cBot.x + pad} y={pO.cBot.y + l1Bottom / 2} text={osuInst[i].name}
			height={l1Bottom / 2} width={pO.widths.child - 2 * pad} />

		<BrokenFittedText x={pO.cBot.x + 2 * pad} y={pO.cBot.y + l1Bottom - pad} text={cText(osuInst[i].weight)}
			height={l1Bottom / 3.5} width={pO.widths.child - 4 * pad} />
		{/each}
	</g>
</svg>

<style>
	:global(g) {
		transition: transform 0ms !important;
	}

	svg {
		position: absolute;
		z-index: 3;
	}
</style>
