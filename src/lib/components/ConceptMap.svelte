<script lang="ts">
	import { nodes, edges } from '$lib/assets/data/concept-map.json';
	import { subfields, fields, domains } from '$lib/assets/data/field-hierarchy.json';
	import fieldOrderMap from '$lib/assets/data/fields-ordered.json';
	import { getColor, getColorArr } from '$lib/style-util';

	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { LOW_OP } from '$lib/constants';
	import { onMount } from 'svelte';
	import FlatOutFrame from './FlatOutFrame.svelte';

	export let rootName = '';
	export let rootId: number;
	export let indsByEntityType: tt.IndsByEntityType;
	export let conf: tt.FullTreeConfig;
	export let treeSpecs: tt.TreeSpecs;

	const minSize = 1.1;
	const maxSize = 2.2;
	const minSaturation = 0.95;
	const maxSaturation = 0;
	const minOpacity = LOW_OP * 2;
	const maxOpacity = 100;
	let defaultSat = 0.8;
	let defaultOp = 1;
	let defaultLineOp = 0.5;
	let nBreakPoints = 2;

	const getOpFromRate = (x: number) => x * (maxOpacity - minOpacity) + minOpacity;
	const getSatFromRate = (x: number) => x * (maxSaturation - minSaturation) + minSaturation;
	const getSizeFromRate = (x: number) => x * (maxSize - minSize) + minSize;

	let svgEl: SVGSVGElement;
	let styleEl: SVGStyleElement | null = null;
	let infoPath: number[] = [];
	let mounted = false;
	let hovered = '0';
	let hoveredParent: number | undefined = undefined;
	let toDomains = false;

	let isSpec = true;
	let flatOut = {};
	$: parents = toDomains ? domains : getFieldArr();
	$: getParent = toDomains ? getDomain : getFieldColorOrder;
	$: setClassStyles(styleEl, flatOut, mounted, hovered, hoveredParent);

	function classNamer(s: string) {
		return `subfield-circle-${s}`;
	}

	function flashClassNamer(s: string) {
		return `subfield-flash-${s}`;
	}

	function getFieldColorOrder(sf: string) {
		return (fieldOrderMap[getField(sf)] || 0) as number;
	}

	function getField(sf: string) {
		return subfields[parseInt(sf)][1] as number;
	}

	function getDomain(sf: string) {
		let field = getField(sf);
		let domain = fields[field][1];
		return domain;
	}

	function getParentColor(i: number) {
		let colInd = toDomains ? i - 1 : i - 1;
		return getColor(colInd / (parents.length - 1));
	}

	function getParentColorArr(i: number) {
		let colInd = toDomains ? i - 1 : i - 1;
		return getColorArr(colInd / (parents.length - 1));
	}

	function getFieldArr() {
		const fieldsOut = [];
		for (let i = 0; i < fields.length; i++) {
			fieldsOut[fieldOrderMap[i] as number] = fields[i][0];
		}
		return fieldsOut;
	}

	function getClassStyles(
		levels: tt.LevelT,
		highlighted: string,
		highlightedParent: number | undefined,
		pullerRate: number
	) {
		if (Object.values(levels).length == 0) return '';
		const { linScaler, newBreakPoints } = tf.getFlatRescaler(levels, nBreakPoints, pullerRate);

		let scaler = (w: number) => {
			let size = getSizeFromRate(linScaler(w));
			let oI = 0;
			for (let i = 1; i <= nBreakPoints; i++) {
				if (w >= newBreakPoints[i]) oI++;
			}
			let sat = getSatFromRate(oI / nBreakPoints);
			return { sat, size };
		};
		const sLines = [];
		for (const [c, { w }] of Object.entries(levels)) {
			let isHighlighted = c == highlighted;
			if (hoveredParent != undefined) {
				isHighlighted = getParent(c) == highlightedParent;
			}
			let { sat, size } = scaler(w);

			let line = `r: ${size.toFixed(2)}px;`;
			let flashLine = `r: ${(size * 0.9).toFixed(2)}px; fill-opacity: ${sat};`;
			if (isHighlighted) {
				line += `stroke-width: 0.5px; stroke: var(--color-text);`;
			}
			//
			sLines.push(`circle.${classNamer(c)} {${line}}`);
			sLines.push(`circle.${flashClassNamer(c)} {${flashLine}}`);
		}
		return sLines.join('\n');
	}

	function setClassStyles(
		styleEl: SVGStyleElement | null,
		flatOut: tt.LevelT | undefined,
		mounted: boolean,
		hovered: string,
		hoveredParent: number | undefined
	) {
		if (styleEl != undefined && flatOut != undefined && mounted) {
			styleEl.textContent = getClassStyles(flatOut, hovered, hoveredParent, 0.2);
		}
	}

	onMount(() => {
		const svgNS = 'http://www.w3.org/2000/svg';
		styleEl = document.createElementNS(svgNS, 'style') as SVGStyleElement;
		svgEl.insertBefore(styleEl, svgEl.firstChild);
		mounted = true;
	});

	const SF_SEM_MAP: Record<tt.RootType, Record<string, string>> = {
		countries: {
			'subfields-true': 'of papers published by authors working in',
			'subfields-false': 'of papers citing works of authors working in'
		},
		institutions: {
			'subfields-true': 'of papers published by authors at',
			'subfields-false': 'of papers citing works of authors at'
		},
		authors: {
			'subfields-true': 'of papers published by',
			'subfields-false': 'of papers citing papers by'
		},
		sources: { 'subfields-true': 'of papers published in' },
		subfields: { 'subfields-false': 'of papers citing papers about' },
		'hit-papers': { 'subfields-false': 'of papers citing' }
	};

	function subfieldSemantify(rootType: tt.RootType, bd: string) {
		let oBase = SF_SEM_MAP[rootType];
		if (oBase == undefined) return bd;
		return oBase[bd] || bd;
	}
</script>

<FlatOutFrame
	titlePrefix="Fields"
	l1Type="subfields"
	semantifyer={subfieldSemantify}
	{rootName}
	{rootId}
	{indsByEntityType}
	{conf}
	{treeSpecs}
	bind:flatOut
	bind:isSpec
	{infoPath}
>
	<!-- svelte-ignore a11y-mouse-events-have-key-events -->
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
	<div class="concept-map-container">
		<div class="concept-map-parents">
			{#each parents.entries() as [i, parent]}
				<span
					class="hover-s"
					on:mouseover={() => (hoveredParent = i)}
					on:mouseleave={() => (hoveredParent = undefined)}
					role="none"
					style="background-color:rgba({getParentColorArr(i)}, 0.4);">{parent}</span
				>
			{/each}
		</div>
		<svg
			bind:this={svgEl}
			viewBox="-8 -8 146 116"
			style="--op: {defaultOp}; --lop: {defaultLineOp}; --sat: {defaultSat}"
		>
			{#each edges as [s, t, w]}
				<line
					x1={nodes[s][0]}
					y1={nodes[s][1]}
					x2={nodes[t][0]}
					y2={nodes[t][1]}
					stroke="black"
					stroke-width="0.1"
				/>
			{/each}
			{#each Object.entries(nodes) as [sfi, [cx, cy]]}
				<circle
					{cx}
					{cy}
					class={classNamer(sfi)}
					role="region"
					fill={getParentColor(getParent(sfi))}
					stroke={getParentColor(getParent(sfi))}
					on:mouseover={() => {
						hovered = sfi;
						infoPath = [sfi];
					}}
					r={minSize * 0.7}
				/>
				<circle
					{cx}
					{cy}
					class="{flashClassNamer(sfi)} nopointer"
					stroke="none"
					r={minSize * 0.7 * 0.9}
					fill="var(--text-bg)"
				/>
			{/each}
		</svg>
	</div>
</FlatOutFrame>

<style>
	svg {
		max-height: 80svh;
		flex: 9 9 750px;
	}

	line {
		opacity: var(--lop);
	}

	circle {
		filter: contrast(var(--sat));
		opacity: var(--op);
		transition: all 800ms;
		stroke-width: 0.2;
	}

	.nopointer {
		pointer-events: none;
	}

	.parent-head {
		height: 30px;
	}

	.concept-map-container {
		display: flex;
		flex-wrap: wrap-reverse;
	}

	.concept-map-parents {
		flex: 3 1 300px;
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		justify-content: space-between;
		align-items: center;
	}

	.concept-map-parents > span {
		padding: 3px;
		cursor: default;
		flex: 1 1 auto;
		text-align: center;
	}
</style>
