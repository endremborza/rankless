<script lang="ts">
	import type { TreeSpecs } from '$lib/wire/rankless_trees/io';
	import { nodes as nodesData, edges } from '$lib/assets/data/concept-map.json';
	import { subfields, fields, domains } from '$lib/assets/data/field-hierarchy.json';
	import { getColorArr } from '$lib/style-util';
	import { getNetworkText } from '$lib/text-format-util';
	import {
		DOMAIN_ID_MAP,
		SUBFIELD_NULL_R,
		SUBFIELD_SEMANTICS,
		domainRate,
		subfieldColor,
		subfieldHier,
		subfieldStyles
	} from '$lib/utils/flat-out-styles';

	import type * as tt from '$lib/tree-types';
	import { onMount } from 'svelte';
	import FlatOutFrame from './FlatOutFrame.svelte';

	export let rootName = '';
	export let rootId: number;
	export let indsByEntityType: tt.IndsByEntityType;
	export let conf: tt.FullTreeConfig;
	export let treeSpecs: TreeSpecs;

	let defaultSat = 0.8;
	let defaultOp = 1;
	let defaultLineOp = 0.35;

	type Hierarchy = Record<
		number,
		{ name: string; children: Record<number, { name: string; children: number[] }> }
	>;
	type ParentSelect = [number | undefined, number | undefined];

	const nodes = nodesData as Record<number, number[]>;
	const backupNames = getMap(subfields as [string, number][]);
	const nodeKeys = Object.keys(backupNames);
	const parents = getParentsObject();
	const parentEntries = Object.entries(parents).map(
		([k, v]) => [Number(k), v] as [number, (typeof parents)[number]]
	);

	let infoPath: number[] = [];
	let mounted = false;
	let hovered = '0';
	let hoveredParent: ParentSelect = [undefined, undefined];

	let hoveredOverCircle = false;
	let showPaper = false;
	let fixedSelect = false;
	let isSpec = true;
	let flatOut = {};

	let treeId: number;
	$: sourceSide = getSourceSide(treeSpecs, conf.rootType, treeId);
	$: styleTag = mounted ? `<style>${getClassStyles(flatOut, hovered, hoveredParent)}</style>` : '';
	$: updateTreeId(indsByEntityType);

	function getSourceSide(treeSpecs: TreeSpecs, rootType: tt.RootType, treeId: number) {
		let treeSpec = treeSpecs.specs[rootType][treeId];
		if (treeSpec == undefined) return false;
		return treeSpec.breakdowns[0].sourceSide;
	}
	function updateTreeId(inds: tt.IndsByEntityType) {
		treeId = inds.subfields.includes(9) ? 9 : indsByEntityType.subfields[0];
	}

	function getMap(ents: [string, number][]) {
		let out: Record<number, string> = {};
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

	function isParentHovered(sfi: string, hoveredParent: ParentSelect) {
		if (hoveredParent[0] == undefined) return false;
		let [_, field, domain] = getHier(sfi);
		if (hoveredParent[1] == undefined) return domain == hoveredParent[0];
		return field == hoveredParent[1];
	}

	function getHier(sfi: string): [number, number, number] {
		let sfin = parseInt(sfi);
		return [sfin, ...subfieldHier(sfin)];
	}

	function getNodeColor(sfi: string) {
		return subfieldColor(parseInt(sfi));
	}

	function getParentColorArr(i: number) {
		return getColorArr(domainRate(i));
	}

	function domainIdRemapper(loadedId: number) {
		return DOMAIN_ID_MAP[loadedId];
	}

	function getParentsObject(): Hierarchy {
		const out: Hierarchy = {};
		for (let i = 0; i < domains.length; i++) {
			let name = domains[i];
			if (name.length == 0) continue;
			let remappedId = domainIdRemapper(i);
			out[remappedId] = { name, children: {} };
		}
		for (let i = 0; i < fields.length; i++) {
			let [name, domainId] = fields[i] as [string, number];
			if (name.length == 0) continue;
			let parent = domainIdRemapper(domainId);
			out[parent].children[i] = { name, children: [] };
		}
		for (let i = 0; i < subfields.length; i++) {
			let [name, parent] = subfields[i] as [string, number];
			if (name.length == 0) continue;
			let grandP = domainIdRemapper(fields[parent][1] as number);
			out[grandP].children[parent].children.push(i);
		}
		return out;
	}

	function getClassStyles(levels: tt.LevelT, highlighted: string, highlightedParent: ParentSelect) {
		if (Object.values(levels).length == 0) return '';
		const styles = subfieldStyles(levels, isSpec);
		const sLines = [];
		for (const key of nodeKeys) {
			let isHighlighted = key == highlighted || isParentHovered(key, highlightedParent);
			let line = '';
			let flashLine = '';
			const style = styles[key];
			if (style != undefined) {
				line += `r: ${style.r.toFixed(2)}px;`;
				flashLine += `r: ${(style.r * 0.9).toFixed(2)}px; fill-opacity: ${style.sat};`;
			}
			if (isHighlighted) {
				line += `stroke-width: 0.8px; stroke: var(--color-text);`;
			}
			sLines.push(`circle.${classNamer(key)} {${line}}`);
			sLines.push(`circle.${flashClassNamer(key)} {${flashLine}}`);
		}
		return sLines.join('\n');
	}

	onMount(() => {
		mounted = true;
	});

	function subfieldSemantify(rootType: tt.RootType, bd: string) {
		let oBase = SUBFIELD_SEMANTICS[rootType];
		if (oBase == undefined) return bd;
		return oBase[bd] || bd;
	}
</script>

<div class="fof-container">
	<div class="wide-screen-heighted">
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
			showInfobox={conf.rootType !== 'hit-papers'}
			{infoPath}
		>
			<!-- svelte-ignore a11y_mouse_events_have_key_events -->
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
			<div class="concept-map-container">
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<svg
					viewBox="-8 -8 146 116"
					style="--op: {defaultOp}; --lop: {defaultLineOp}; --sat: {defaultSat}"
					on:click={() => {
						if (!hoveredOverCircle) {
							fixedSelect = false;
						}
					}}
				>
					{@html styleTag}
					{#each edges as [s, t, w], __i (__i)}
						<line
							x1={nodes[s][0]}
							y1={nodes[s][1]}
							x2={nodes[t][0]}
							y2={nodes[t][1]}
							stroke="black"
							stroke-width="0.1"
						/>
					{/each}
					{#each Object.entries(nodes) as [sfi, [cx, cy]] (sfi)}
						<circle
							{cx}
							{cy}
							class={classNamer(sfi)}
							role="region"
							fill={getNodeColor(sfi)}
							stroke={getNodeColor(sfi)}
							on:mouseover={() => {
								if (!fixedSelect) {
									hoveredOverCircle = true;
									hovered = sfi;
									infoPath = [parseInt(sfi)];
								}
							}}
							on:mouseleave={() => {
								hoveredOverCircle = false;
							}}
							on:click={() => {
								fixedSelect = true;
								hovered = sfi;
								infoPath = [parseInt(sfi)];
								showPaper = true;
							}}
							r={SUBFIELD_NULL_R}
							stroke-width="0.2"
						/>
						<circle
							{cx}
							{cy}
							class="{flashClassNamer(sfi)} nopointer"
							stroke="none"
							r={SUBFIELD_NULL_R * 0.9}
							fill="var(--text-bg)"
						/>
					{/each}
				</svg>
				<div class="concept-map-legend">
					{#each parentEntries as [i, parent] (i)}
						<span
							class="vw-sm"
							on:mouseover={() => (hoveredParent = [i, undefined])}
							on:mouseleave={() => (hoveredParent = [undefined, undefined])}
							role="none"
							style="background-color:rgba({getParentColorArr(i)}, 0.4);">{parent.name}</span
						>
					{/each}
				</div>
			</div>
		</FlatOutFrame>
	</div>
	<p class="vw-base">{@html getNetworkText(conf.rootType, rootName, isSpec, sourceSide)}</p>
</div>

<style>
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
		flex-direction: column;
		width: 100%;
		height: 100%;
	}

	.concept-map-container > svg {
		flex: 1 1 0;
		min-height: 0;
		height: 100%;
		width: 100%;
		display: block;
	}

	@media (max-width: 899px) {
		.concept-map-container {
			aspect-ratio: 1 / 1;
			max-height: 60svh;
		}
	}

	.concept-map-legend {
		flex: 0 0 auto;
		display: flex;
		flex-wrap: wrap;
		gap: 7px;
	}

	.concept-map-legend > span {
		padding: 3px;
		cursor: default;
		flex: 1 1 auto;
		text-align: center;
	}
</style>
