<script lang="ts">
	import MaybeLink from '$lib/components/MaybeLink.svelte';
	import type * as tt from '$lib/tree-types';
	import { pluralize } from '$lib/text-format-util';
	import { getColor } from '$lib/style-util';

	export let lineWidth: number;
	export let instRels: tt.InstRel[];

	function getSpanConfig(rels: tt.InstRel[]): {
		min: number;
		max: number;
		span: number;
		ticks: number[];
		colors: string[];
		spans: { min: number; max: number }[];
		orderedRels: tt.InstRel[][];
	} {
		let min = Infinity;
		let max = -Infinity;
		let spanRec: Record<string, tt.InstRel[]> = {};
		const spans: { min: number; max: number }[] = [];
		for (const rel of rels) {
			min = Math.min(min, rel.start);
			max = Math.max(max, rel.end);
			let key = `${rel.start}-${rel.end}`;
			if (spanRec[key] == undefined) {
				const entry = { min: rel.start, max: rel.end };
				spans.push(entry);
				spanRec[key] = [rel];
			} else {
				spanRec[key].push(rel);
			}
		}

		const orderedRels: tt.InstRel[][] = [];
		spans.sort((l, r) => r.max - r.min - (l.max - l.min));
		for (const s of spans) {
			let key = `${s.min}-${s.max}`;
			orderedRels.push(spanRec[key]);
		}
		let span = max - min;
		const eScale = (n: number) => ((n - min) / span) * lineWidth;
		const reScale = (e: { min: number; max: number }) => {
			let upper = e.max == e.min ? e.min + 0.5 : e.max;
			return {
				max: eScale(upper),
				min: eScale(e.min)
			};
		};
		let ticks = [];
		for (let y = min; y <= max; y++) {
			ticks.push(eScale(y));
		}
		let colors = [];
		for (let i = 0; i < spans.length; i++) {
			colors.push(getColor(i / (spans.length - 1)));
		}
		return { min, max, ticks, span, spans: spans.map(reScale), orderedRels, colors };
	}

	function semRange(r: { start: number; end: number }) {
		if (r.start < r.end) {
			return `(${r.start} - ${r.end})`;
		}
		return `(${r.start})`;
	}

	$: spanConfig = getSpanConfig(instRels);
</script>

<svg viewBox="-2 -3 {lineWidth + 4} {3 + spanConfig.spans.length}">
	<text text-anchor="middle" y="-1.2" font-size="1.6">{spanConfig.min}</text>
	<text text-anchor="middle" y="-1.2" x={lineWidth} font-size="1.6">{spanConfig.max}</text>
	{#each spanConfig.spans.entries() as [i, el] (i)}
		<line x1={el.min} y1={i} x2={el.max} y2={i} stroke-width={1} stroke={spanConfig.colors[i]} />
	{/each}
	{#each spanConfig.ticks as tick, __i (__i)}
		<line x1={tick} x2={tick} y1={-1} y2={-0.5} stroke="black" stroke-width="0.1" />
	{/each}
</svg>
<div id="affl">
	{#each spanConfig.orderedRels.entries() as [i, oRels] (i)}
		{#each oRels as iRel, __i (__i)}
			<span>
				<span style="color: {spanConfig.colors[i]}; font-size: x-large">■</span>
				<MaybeLink name={iRel.name} semanticId={iRel.semId} rootType="institutions" />
				<ul>
					<li style="font-size: small;">
						{pluralize('paper', iRel.papers)} with {pluralize('citation', iRel.citations)}
						{semRange(iRel)}
					</li>
				</ul>
			</span>
		{/each}
	{/each}
</div>
