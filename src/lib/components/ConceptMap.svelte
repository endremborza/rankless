<script lang="ts">
	import { nodes, edges } from '$lib/assets/data/concept-map.json';
	import { subfields, fields, domains } from '$lib/assets/data/field-hierarchy.json';
	import fieldOrderMap from '$lib/assets/data/fields-ordered.json';
	import { getColor, getColorArr } from '$lib/style-util';
	import { getNetworkText } from '$lib/text-format-util';

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
	const nullSize = 0.8;
	const minSaturation = 0.95;
	const maxSaturation = 0.2;
	const minOpacity = LOW_OP * 2;
	const maxOpacity = 100;
	let defaultSat = 0.8;
	let defaultOp = 1;
	let defaultLineOp = 0.35;
	let nBreakPoints = 2;

	const getOpFromRate = (x: number) => x * (maxOpacity - minOpacity) + minOpacity;
	const getSatFromRate = (x: number) => x * (maxSaturation - minSaturation) + minSaturation;
	const getSizeFromRate = (x: number) => x * (maxSize - minSize) + minSize;
	const backupNames = getMap(subfields);

	let svgEl: SVGSVGElement;
	let styleEl: SVGStyleElement | null = null;
	let infoPath: number[] = [];
	let mounted = false;
	let hovered = '0';
	let hoveredParent: number | undefined = undefined;
	let toDomains = false;
	let treeId = indsByEntityType.subfields.includes(9) ? 9 : indsByEntityType.subfields[0];
	//TODO: anny change can cock this up

	let hoveredOverCircle = false;
	let showPaper = false;
	let isSpec = true;
	let flatOut = {};
	$: sourceSide = treeSpecs.specs[conf.rootType][treeId].breakdowns[0].sourceSide;
	$: parents = toDomains ? domains : getFieldArr();
	$: getParent = toDomains ? getDomain : getFieldColorOrder;
	$: setClassStyles(styleEl, flatOut, mounted, hovered, hoveredParent, backupNames);

	function getMap(ents: [string, number][]) {
		let out = {};
		for (let i = 0; i < ents.length; i++) {
			out[i] = ents[i][0];
		}
		return out;
	}

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
		pullerRate: number,
		backups: Record<number, string>
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
		for (const key of Object.keys(backups)) {
			let isHighlighted = key == highlighted;
			if (hoveredParent != undefined) {
				isHighlighted = getParent(key) == highlightedParent;
			}
			let line = '';
			let flashLine = '';
			let wDic = levels[key];
			if (wDic != undefined) {
				let { sat, size } = scaler(wDic.w);
				line += `r: ${size.toFixed(2)}px;`;
				flashLine += `r: ${(size * 0.9).toFixed(2)}px; fill-opacity: ${sat};`;
			}
			if (isHighlighted) {
				line += `stroke-width: 0.8px; stroke: var(--color-text);`;
			}
			sLines.push(`circle.${classNamer(key)} {${line}}`);
			sLines.push(`circle.${flashClassNamer(key)} {${flashLine}}`);
		}
		return sLines.join('\n');
	}

	function setClassStyles(
		styleEl: SVGStyleElement | null,
		flatOut: tt.LevelT | undefined,
		mounted: boolean,
		hovered: string,
		hoveredParent: number | undefined,
		backups: Record<number, string>
	) {
		if (styleEl != undefined && flatOut != undefined && mounted) {
			styleEl.textContent = getClassStyles(flatOut, hovered, hoveredParent, 0.2, backups);
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
	{backupNames}
	bind:treeId
	bind:flatOut
	bind:isSpec
	bind:showPaper
	{infoPath}
>
	<!-- svelte-ignore a11y-mouse-events-have-key-events -->
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
	<div class="concept-map-container">
		<div class="concept-map-parents">
			{#each parents.entries() as [i, parent]}
				<span
					class="hover-xs"
					on:mouseover={() => (hoveredParent = i)}
					on:mouseleave={() => (hoveredParent = undefined)}
					role="none"
					style="background-color:rgba({getParentColorArr(i)}, 0.4);">{parent}</span
				>
			{/each}
		</div>
		<!-- svelte-ignore a11y-no-static-element-interactions -->
		<svg
			bind:this={svgEl}
			viewBox="-8 -8 146 116"
			style="--op: {defaultOp}; --lop: {defaultLineOp}; --sat: {defaultSat}"
			on:click={() => {
				if (!hoveredOverCircle) {
					if (showPaper) showPaper = false;
				}
			}}
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
						if (!showPaper) {
							hoveredOverCircle = true;
							hovered = sfi;
							infoPath = [sfi];
						}
					}}
					on:mouseleave={() => {
						hoveredOverCircle = false;
					}}
					on:click={() => {
						showPaper = true;
					}}
					r={nullSize}
					stroke-width="0.2"
				/>
				<circle
					{cx}
					{cy}
					class="{flashClassNamer(sfi)} nopointer"
					stroke="none"
					r={nullSize * 0.9}
					fill="var(--text-bg)"
				/>
			{/each}
		</svg>
	</div>
</FlatOutFrame>

<p>
	{getNetworkText(conf.rootType, rootName, isSpec, sourceSide)}
</p>

<style>
	svg {
		max-height: 70svh;
		flex: 9 9 750px;
	}

	line {
		opacity: var(--lop);
	}

	circle {
		filter: contrast(var(--sat));
		opacity: var(--op);
		transition: all 800ms;
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
		flex: 2 1 300px;
		display: flex;
		flex-wrap: wrap;
		gap: 7px;
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
