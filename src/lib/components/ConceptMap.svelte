<script lang="ts">
	import { nodes, edges } from '$lib/assets/data/concept-map.json';
	import { subfields, fields, domains } from '$lib/assets/data/field-hierarchy.json';
	import fieldOrderMap from '$lib/assets/data/fields-ordered.json';
	import { getColor } from '$lib/style-util';

	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { HIGH_OP, LOW_OP } from '$lib/constants';
	import { onMount } from 'svelte';
	import FlatOutFrame from './FlatOutFrame.svelte';

	export let rootName = '';
	export let rootId: number;
	export let indsByEntityType: tt.IndsByEntityType;
	export let conf: tt.FullTreeConfig;
	export let treeSpecs: tt.TreeSpecs;

	const minSize = 1.5;
	const maxSize = 3.1;
	const minOpacity = LOW_OP * 1.5;
	const maxOpacity = 100; //HIGH_OP;

	const getOpFromRate = (x: number) => x * (maxOpacity - minOpacity) + minOpacity;
	const getSizeFromRate = (x: number) => x * (maxSize - minSize) + minSize;

	let svgEl: SVGSVGElement;
	let styleEl: SVGStyleElement | null = null;
	let infoPath: string[] = [];
	let mounted = false;
	let fontSize = 2.3;
	let hovered = '0';
	let hoveredParent = 0;
	let toDomains = false;

	let isSpec = true;
	let flatOut = {};
	$: parents = toDomains ? domains : getFieldArr();
	$: getParent = toDomains ? getDomain : getFieldColorOrder;
	$: {
		if (styleEl != undefined && flatOut != undefined && mounted) {
			styleEl.textContent = getClassStyles(flatOut, hovered, -1, 0, 0.2);
		}
	}

	function classNamer(s: string) {
		return `subfield-circle-${s}`;
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

	function getFieldArr() {
		const fieldsOut = [];
		for (let i = 0; i < fields.length; i++) {
			fieldsOut[fieldOrderMap[i]] = fields[i][0];
		}
		return fieldsOut;
	}

	function getClassStyles(
		levels: tt.LevelT,
		highlighted: string,
		highlightedQ: number,
		nBreakPoints: number,
		pullerRate: number
	) {
		if (Object.values(levels).length == 0) return '';
		const { linScaler, newBreakPoints } = tf.getFlatRescaler(levels, nBreakPoints, pullerRate);
		let scaler = (w: number) => {
			let op = getOpFromRate(linScaler(w));
			let size = getSizeFromRate(linScaler(w));
			return { op, hl: false, size };
		};
		if (nBreakPoints > 0) {
			scaler = (w: number) => {
				let oI = 0;
				for (let i = 1; i <= nBreakPoints; i++) {
					if (w >= newBreakPoints[i]) oI++;
				}
				let size = getSizeFromRate(oI / nBreakPoints);
				return { op: getOpFromRate(oI / nBreakPoints), hl: oI == highlightedQ, color: size };
			};
		}
		const sLines = [];
		for (const [c, { w }] of Object.entries(levels)) {
			let isHighlighted = c == highlighted;
			let { op, hl, size } = scaler(w);
			isHighlighted = isHighlighted || hl;
			let line = `r: ${size.toFixed(2)}px; fill-opacity: ${op / 100};`;
			if (isHighlighted) {
				line += `stroke-width: 1.5;`;
			}
			sLines.push(`circle.${classNamer(c)} {${line}}`);
		}
		return sLines.join('\n');
	}

	onMount(() => {
		const svgNS = 'http://www.w3.org/2000/svg';
		styleEl = document.createElementNS(svgNS, 'style') as SVGStyleElement;
		svgEl.insertBefore(styleEl, svgEl.firstChild);
		mounted = true;
	});

	const SF_SEM_MAP: Record<tt.RootType, Record<string, string>> = {
		countries: {},
		institutions: {
			'subfields-true': 'of papers published by authors at',
			'subfields-false': 'of papers citing works of authors at'
		},
		authors: { 'subfields-true': 'of papers published by' },
		sources: { 'subfields-true': 'of papers published in' },
		subfields: {}
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
	<svg
		bind:this={svgEl}
		viewBox="-40 -10 180 120"
		style="--fs: {fontSize}px; --r: {minSize * 0.35}px; --op: {(minOpacity * 0.5) / 100}"
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
		{#each parents.entries() as [i, parent]}
			{#if parent.length > 0}
				<g
					transform="translate(0, {i * fontSize * 1.2})"
					on:mouseover={() => (hoveredParent = i)}
					role="none"
				>
					<rect x="-5" y={-fontSize * 0.77} height={fontSize} width="3" fill={getParentColor(i)} />
					<text x="-6" text-anchor="end">{parent}</text>
				</g>
			{/if}
		{/each}
		{#each Object.entries(nodes) as [sfi, [cx, cy]]}
			<circle
				{cx}
				{cy}
				class={classNamer(sfi)}
				role="region"
				fill={getParentColor(getParent(sfi))}
				on:mouseover={() => {
					hovered = sfi;
					infoPath = [sfi];
				}}
				stroke-width="0.2"
				stroke={getParent(sfi) == hoveredParent ? 'white' : 'none'}
			/>
		{/each}
	</svg>
</FlatOutFrame>

<div>
	{subfields[parseInt(hovered)][0]} -> {fields[getField(hovered)][0]} -> {domains[
		getDomain(hovered)
	]}
</div>

<style>
	svg {
		width: 100%;
		height: 800px;
	}

	text {
		font-size: var(--fs);
	}

	line {
		opacity: var(--op);
	}

	circle {
		r: var(--r);
		fill-opacity: var(--op);
	}

	.parent-head {
		height: 30px;
	}
</style>
