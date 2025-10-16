<script lang="ts">
	import { nodes, edges } from '$lib/assets/data/concept-map.json';
	import { subfields, fields, domains } from '$lib/assets/data/field-hierarchy.json';
	import { getColor, getColorArr } from '$lib/style-util';
	import { getNetworkText, SPEC_BPS } from '$lib/text-format-util';

	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { onMount } from 'svelte';
	import FlatOutFrame from './FlatOutFrame.svelte';

	export let rootName = '';
	export let rootId: number;
	export let indsByEntityType: tt.IndsByEntityType;
	export let conf: tt.FullTreeConfig;
	export let treeSpecs: tt.TreeSpecs;

	const minSize = 1;
	const maxSize = 2.3;
	const nullSize = 0.8;
	const minSaturation = 0.95;
	const maxSaturation = 0.05;
	let defaultSat = 0.8;
	let defaultOp = 1;
	let defaultLineOp = 0.35;
	let nBreakPoints = 2;

	type Hierarchy = Record<
		number,
		{ name: string; children: Record<number, { name: string; children: number[] }> }
	>;
	type ParentSelect = [number | undefined, number | undefined];

	const getSatFromRate = (x: number) =>
		Math.pow(x, 0.35) * (maxSaturation - minSaturation) + minSaturation;
	const getSizeFromRate = (x: number) => Math.pow(x, 0.65) * (maxSize - minSize) + minSize;
	const backupNames = getMap(subfields);
	const nodeKeys = Object.keys(backupNames);
	const parents = getParentsObject();

	let svgEl: SVGSVGElement;
	let styleEl: SVGStyleElement | null = null;
	let infoPath: number[] = [];
	let mounted = false;
	let hovered = '0';
	let hoveredParent: ParentSelect = [undefined, undefined];

	let hoveredOverCircle = false;
	let showPaper = false;
	let isSpec = true;
	let flatOut = {};

	$: treeId = indsByEntityType.subfields.includes(9) ? 9 : indsByEntityType.subfields[0];
	$: sourceSide = getSourceSide(treeSpecs, conf.rootType, treeId);
	$: setClassStyles(styleEl, flatOut, mounted, hovered, hoveredParent);

	function getSourceSide(treeSpecs: tt.TreeSpecs, rootType: tt.RootType, treeId: number) {
		let treeSpec = treeSpecs.specs[rootType][treeId];
		if (treeSpec == undefined) return false;
		return treeSpec.breakdowns[0].sourceSide;
	}
	function getExpandPrefix(path: number[]) {
		return 'Top Paper';
		if (path.length == 0) return 'Top Paper';
		return backupNames[path[path.length - 1]] || 'Top Paper';
	}

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

	function getDomainRate(domainId: number) {
		return (domainId - 1) / (domains.length - 2);
	}

	function isParentHovered(sfi: string, hoveredParent: ParentSelect) {
		if (hoveredParent[0] == undefined) return false;
		let [_, field, domain] = getHier(sfi);
		if (hoveredParent[1] == undefined) return domain == hoveredParent[0];
		return field == hoveredParent[1];
	}

	function getHier(sfi: string): [number, number, number] {
		let sfin = parseInt(sfi);
		let fieldId = subfields[sfin][1] as number;
		let domainId = fields[fieldId][1] as number;
		return [sfin, fieldId, domainId];
	}

	function getNodeColor(sfi: string) {
		return getColor(getDomainRate(getHier(sfi)[2]));
	}

	function getParentColorArr(i: number) {
		return getColorArr(getDomainRate(i));
	}

	function getParentsObject(): Hierarchy {
		const out: Hierarchy = {};
		for (let i = 0; i < domains.length; i++) {
			let name = domains[i];
			if (name.length == 0) continue;
			out[i] = { name, children: {} };
		}
		for (let i = 0; i < fields.length; i++) {
			let [name, parent] = fields[i] as [string, number];
			if (name.length == 0) continue;
			out[parent].children[i] = { name, children: [] };
		}
		for (let i = 0; i < subfields.length; i++) {
			let [name, parent] = subfields[i] as [string, number];
			if (name.length == 0) continue;
			let grandP = fields[parent][1] as number;
			out[grandP].children[parent].children.push(i);
		}
		return out;
	}

	function getClassStyles(
		levels: tt.LevelT,
		highlighted: string,
		highlightedParent: ParentSelect,
		pullerRate: number
	) {
		if (Object.values(levels).length == 0) return '';
		const { linScaler, newBreakPoints } = tf.getFlatRescaler(levels, nBreakPoints, pullerRate);
		const dynBreakPoints = isSpec ? SPEC_BPS : newBreakPoints;
		let scaler = (w: number) => {
			let size = getSizeFromRate(linScaler(w));
			let oI = 0;
			for (const bp of dynBreakPoints) {
				if (w >= bp) oI++;
			}
			let sat = getSatFromRate(oI / dynBreakPoints.length);
			return { sat, size };
		};
		const sLines = [];
		for (const key of nodeKeys) {
			let isHighlighted = key == highlighted || isParentHovered(key, highlightedParent);
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
		hoveredParent: ParentSelect
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
	{backupNames}
	bind:treeId
	bind:flatOut
	bind:isSpec
	bind:showPaper
	{infoPath}
	{getExpandPrefix}
>
	<!-- svelte-ignore a11y-mouse-events-have-key-events -->
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
	<div class="concept-map-container">
		<div class="concept-map-parents">
			{#each Object.entries(parents) as [i, parent]}
				<span
					class="hover-xs"
					on:mouseover={() => (hoveredParent = [i, undefined])}
					on:mouseleave={() => (hoveredParent = [undefined, undefined])}
					role="none"
					style="background-color:rgba({getParentColorArr(i)}, 0.4);">{parent.name}</span
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
					fill={getNodeColor(sfi)}
					stroke={getNodeColor(sfi)}
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
		flex: 2 1 100%;
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
