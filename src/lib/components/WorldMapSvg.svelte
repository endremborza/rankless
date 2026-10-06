<script lang="ts">
	import type { TreeResponse, TreeSpecs } from '$lib/wire/rankless_trees/io';
	import { onMount } from 'svelte';

	import type * as tt from '$lib/tree-types';

	import countryPaths from '$lib/assets/data/country-svg-paths.json';
	import { formatNumber, getMapText } from '$lib/text-format-util';
	import {
		COUNTRY_SEMANTICS,
		countryLevels as toCountryLevels,
		countryStyles,
		mapWeightText,
		type Bucket
	} from '$lib/utils/flat-out-styles';
	import FlatOutFrame from './FlatOutFrame.svelte';

	export let rootName = '';
	export let rootId: number;
	export let indsByEntityType: tt.IndsByEntityType;
	export let conf: tt.FullTreeConfig;
	export let treeSpecs: TreeSpecs;

	const OPA_SF = 'opa';
	const FILL_SF = 'fill';
	const PW_SF = 'pw';
	const SC_SF = 'sc';

	let resp: TreeResponse | undefined;
	let countryLevels: tt.LevelT = {};
	let highlighted = '';
	let highlightedQ = -1;
	let infoPath: number[] = [];

	let xMin = 0;
	let yMin = -20;
	let mapWidth = 2000;
	let mapHeight = 950;
	let mounted = false;

	let buckets: Bucket[] = [];

	let clicked = false;
	let isSpec = false;
	let treeId: number;
	let flatOut = {};

	$: isRefSide = treeSpecs.specs[conf.rootType][treeId]?.breakdowns[0].sourceSide;
	$: weightText = mapWeightText(isSpec, isRefSide);
	$: updateL1(flatOut, resp);
	$: styleTag = mounted
		? `<style>${getClassStyles(countryLevels, highlighted, highlightedQ, isSpec)}</style>`
		: '';
	$: updateTreeId(indsByEntityType);

	function updateTreeId(inds: tt.IndsByEntityType) {
		treeId = inds.countries[0];
	}
	function varNamer(s: string, suffix: string) {
		return `--${s.toLowerCase().replaceAll(' ', '-')}-${suffix}`;
	}

	function getClassStyles(
		levels: tt.LevelT,
		highlighted: string,
		highlightedQ: number,
		ratio: boolean
	) {
		if (Object.values(levels).length == 0) return '';
		const styles = countryStyles(levels, ratio);
		const sLines = [];
		for (const [c, { fill, opacity, bucket }] of Object.entries(styles.byName)) {
			sLines.push(`${varNamer(c, FILL_SF)}: ${fill};`);
			sLines.push(`${varNamer(c, OPA_SF)}: ${opacity};`);
			if (c == highlighted || bucket == highlightedQ) {
				sLines.push(`${varNamer(c, PW_SF)}: 4.5;`);
				sLines.push(`${varNamer(c, SC_SF)}: rgb(var(--color-range-20));`);
			}
		}
		buckets = styles.buckets;
		return `:root{ ${sLines.join('\n')} }`;
	}

	function updateL1(flatOut: undefined | tt.LevelT, resp: undefined | TreeResponse) {
		if (flatOut != undefined && resp != undefined) {
			try {
				countryLevels = toCountryLevels(flatOut, resp.atts);
			} catch (error) {
				console.error('flatOutUpdateFailed', error);
			}
		}
	}

	function setHover(cc: string) {
		return () => {
			if (!clicked) {
				highlighted = cc;
				if (highlighted in countryLevels && highlighted != '') {
					infoPath = [countryLevels[highlighted].id];
				} else {
					infoPath = [];
				}
			}
		};
	}

	onMount(() => {
		mounted = true;
	});

	function countrySemantify(rootType: tt.RootType, bd: string) {
		let oBase = COUNTRY_SEMANTICS[rootType];
		if (oBase == undefined) return '';
		return oBase[bd] || '';
	}
	function getDefaultPathStyle(cc: string) {
		let lines = [
			`fill: var(${varNamer(cc, FILL_SF)}, none)`,
			`fill-opacity: var(${varNamer(cc, OPA_SF)}, 0);`,
			`stroke-width: var(${varNamer(cc, PW_SF)}, 1);`,
			`stroke: var(${varNamer(cc, SC_SF)}, var(--color-text));`
		];
		return lines.join(';');
	}
</script>

<div class="fof-container">
	<div class="wide-screen-heighted">
		<FlatOutFrame
			titlePrefix="Countries"
			l1Type="countries"
			semantifyer={countrySemantify}
			{rootName}
			{rootId}
			{indsByEntityType}
			{conf}
			{treeSpecs}
			year={treeSpecs.yearBreaks[0]}
			bind:flatOut
			bind:treeId
			bind:resp
			bind:isSpec
			showInfobox={conf.rootType !== 'hit-papers'}
			{infoPath}
		>
			<div class="world-map-container">
				<svg viewBox="{xMin} {yMin} {mapWidth} {mapHeight}">
					{@html styleTag}
					<!-- svelte-ignore a11y_mouse_events_have_key_events -->
					<!-- svelte-ignore a11y_click_events_have_key_events -->
					<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
					{#each Object.entries(countryPaths) as [cc, cpaths] (cc)}
						{#each cpaths as d, __i (__i)}
							<path
								{d}
								style={getDefaultPathStyle(cc)}
								stroke-width="1"
								stroke="black"
								role="region"
								on:mouseover={setHover(cc)}
								on:mouseleave={setHover('')}
								on:click={() => {
									clicked = !clicked;
									setHover(cc)();
								}}
							/>
						{/each}
					{/each}
				</svg>
				<div class="world-map-labels">
					<!-- svelte-ignore a11y_mouse_events_have_key_events -->
					<div class="label-bp-container">
						{#each buckets as { lo, hi, shade }, i (i)}
							<div
								class="label-bp-box"
								style="background-color: rgba({shade.rgb}, {shade.opacity}); color: {shade.opacity <
								0.5
									? 'var(--color-text)'
									: 'var(--color-theme-white)'}"
								role="region"
								on:mouseover={() => {
									highlightedQ = i;
								}}
								on:mouseleave={() => {
									highlightedQ = -1;
								}}
							>
								<span>{formatNumber(lo)}</span> <span>-</span>
								<span>{formatNumber(hi)}</span>
							</div>
						{/each}
					</div>
					<div id="w-text">{weightText}</div>
				</div>
			</div>
		</FlatOutFrame>
	</div>
	<p class="vw-base">{@html getMapText(conf.rootType, rootName, isSpec, isRefSide)}</p>
</div>

<style>
	path {
		stroke: var(--color-text);
		transition: all 800ms;
	}

	.world-map-container {
		display: flex;
		flex-direction: column;
		width: 100%;
		height: 100%;
	}

	.world-map-container > svg {
		flex: 1 1 0;
		min-height: 0;
		height: 100%;
		width: 100%;
		display: block;
	}

	@media (max-width: 899px) {
		.world-map-container {
			aspect-ratio: 14 / 9;
			max-height: 60svh;
		}
	}

	.world-map-labels {
		display: flex;
		gap: var(--unified-padding);
		justify-content: center;
		flex-wrap: wrap;
	}

	.label-bp-box {
		flex: 1;
		max-width: 120px;
		display: flex;
		justify-content: space-evenly;
		padding: 4px;
		font-weight: 600;
		font-size: 12px;
		cursor: default;
	}

	.label-bp-container {
		width: 100%;
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: var(--unified-padding);
	}

	#w-text {
		width: 100%;
		text-align: center;
	}
</style>
