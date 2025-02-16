<script lang="ts">
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { pluralize } from '$lib/text-format-util';
	import { MAX_LEVEL_COUNT, BE_REMOTE_URL } from '$lib/constants';

	import QuercusBranches from '$lib/components/QuercusBranches.svelte';
	import PathLevelInfoBox from '$lib/components/PathLevelInfoBox.svelte';
	import BrokenFittedText from '$lib/components/BrokenFittedText.svelte';
	import NumberSlider from '$lib/components/NumberSlider.svelte';
	import MidpathBar from '$lib/components/MidpathBar.svelte';
	import HeadControl from './HeadControl.svelte';
	import { onMount } from 'svelte';
	import { replaceState } from '$app/navigation';
	import HoverBlock from './HoverBlock.svelte';
	import { fade } from 'svelte/transition';

	export let conf: tt.FullTreeConfig;
	export let selectedQcRootId: number;

	export let rootName = '';
	export let removeHighlightUnhover = true;
	export let prefixText = '';
	export let treeSpecs: tt.TreeSpecs;
	export let selectionState: tt.BareNode = { children: {} };
	export let completeTree: tt.ResponseNode;
	export let attributeLabels: tt.AttributeLabels;
	export let innerHeight: number;
	export let innerWidth: number;

	let mounted = false;
	let allowPapers = true;
	let showPaper = false;

	let currentTreeSpec: tt.TreeSpec = treeSpecs.specs[conf.rootType][conf.treeId];
	let breakdownMatchLevel: number = currentTreeSpec.breakdowns.length;

	let highlightedPath: tt.PathInTree = [];
	let highlightRoot = selectedQcRootId;
	let selectedPath: tt.PathInTree = [];
	let expandControlInd: number | undefined;

	let defaultChildD1Rate = 0.3;

	let svgD2 = 100;
	let rootD2 = 25;
	let d2Offset = (svgD2 - rootD2) / 3.3;
	let sideBarD2 = 0;
	let controlPad = 0;

	let d1TopPadRate = 9;
	let d1BottomPadRate = 20;
	let headerRate = 11;
	let overHangRate = 0.05;

	let minimumChildWidth = 2.5;
	let showHoverInfo = true;
	let showSpecInfoHover = false;
	let showFilterHover = false;

	let levelOutSpecs: tt.LevelOutSpec[] = tf.getDefaultLevelSpecs();
	let isGlobalSpecialization = currentTreeSpec.defaultIsSpec;
	let controlSpecs = tf.getDefaultControlSpecs(isGlobalSpecialization);
	let maxOnOneLevel = 15;
	let selectedBreakdowns = getDefaultBreakdowns(currentTreeSpec);

	onMount(() => {
		mounted = true;
	});

	$: childD1Rate = expandControlInd == undefined ? defaultChildD1Rate : 0.7;
	$: svgD1 = (innerHeight / innerWidth) * svgD2;
	$: d1ToPixels = (d1: number) => (d1 * innerHeight) / svgD1;
	$: d2ToPixels = (d2: number) => (d2 * innerWidth) / svgD2;
	$: dBasedStyle = getStyleMaker(d1ToPixels, d2ToPixels);
	$: d1PadSize = (d1TopPadRate * svgD1) / 100;

	$: headerShape = {
		height: (svgD1 * headerRate) / 100,
		width: rootD2,
		x: d2Offset + sideBarD2,
		y: (-svgD1 * headerRate) / 100
	};
	$: svgShape = {
		height: svgD1,
		width: svgD2,
		x: 0,
		y: (-(headerRate + d1TopPadRate) * svgD1) / 100
	};

	$: visibleTreeInfo = tf.deriveVisibleTree(
		completeTree,
		controlSpecs,
		selectionState,
		attributeLabels,
		currentTreeSpec
	);

	$: updateTreeSpecId(selectedBreakdowns);

	$: loadNewQc(conf);
	$: ((isSpec: Boolean) => {
		controlSpecs.globalSizeBase = isSpec ? 'specialization' : 'volume';
	})(isGlobalSpecialization);

	$: updateUrl(conf, selectionState);

	$: updateLevelSpecs(
		visibleTreeInfo,
		svgD1 * (1 - (headerRate + d1BottomPadRate) / 100),
		expandControlInd,
		tf.getBreakdownOptions(treeSpecs, conf.rootType),
		selectedBreakdowns
	);

	function getDefaultBreakdowns(treeSpec: tt.TreeSpec) {
		const out: tt.SelectedBreakdowns = [];
		for (let i = 0; i < MAX_LEVEL_COUNT; i++) {
			if (i >= treeSpec.breakdowns.length) break;
			const bdId = tf.idFromBd(treeSpec.breakdowns[i] || {});
			out.push(bdId);
		}
		return out;
	}

	function updateUrl(conf: tt.FullTreeConfig, selectionState: tt.BareNode) {
		if (mounted) {
			let newUrl = tf.toLinkWithParams(conf, selectionState);
			replaceState(newUrl, {});
			// goto(newUrl);
		}
	}

	function updateTreeSpecId(selectedBreakdowns: tt.SelectedBreakdowns) {
		if (selectedBreakdowns.length == 0) {
			return;
		}
		let newBreakdownMatchLevel = 0;
		const newSelections = [];
		let bdKeys = tf.getBreakdownOptions(treeSpecs, conf.rootType);
		let bdLevel;
		for (let selectedBD of selectedBreakdowns) {
			if (selectedBD == '') {
				break;
			}
			newSelections.push(selectedBD);
			bdLevel = bdKeys[selectedBD];
			if (bdLevel === undefined) break;
			if (bdLevel.treeSpecs.includes(conf.treeId)) {
				newBreakdownMatchLevel++;
			} else {
				break;
			}
			bdKeys = bdLevel.children;
		}
		let newSelectedTreeSpecId;
		if (bdLevel != undefined) {
			newSelectedTreeSpecId = bdLevel.treeSpecs[0];
		} else {
			newSelectedTreeSpecId = conf.treeId;
		}
		if (newSelectedTreeSpecId == conf.treeId) {
			return;
		}
		//iter breakdown selections, pick tree spec when only one option remains, fill rest of selected breakdowns
		//find depth upto breakdowns match with last qc
		//prune selection to that depth
		for (let i = newBreakdownMatchLevel; i < controlSpecs.levelSpecs.length; i++) {
			// controlSpecs[i].include = [];
		}
		[conf.treeId, breakdownMatchLevel] = [newSelectedTreeSpecId, newBreakdownMatchLevel];
	}

	function loadNewQc(conf: tt.FullTreeConfig) {
		showPaper = false;
		if (!mounted) {
			return;
		}
		while (selectedBreakdowns.length > 0) {
			// pop so that svelte does not update it
			selectedBreakdowns.pop();
		}
		for (let bd of treeSpecs.specs[conf.rootType][conf.treeId].breakdowns) {
			selectedBreakdowns.push(tf.idFromBd(bd));
		}
		while (selectedBreakdowns.length < MAX_LEVEL_COUNT) {
			selectedBreakdowns.push('');
		}
		fetch(tf.treeBeUrl(BE_REMOTE_URL, conf)).then((res) => {
			res
				.json()
				.then((jsv: tt.TreeResponse) => {
					[
						completeTree,
						attributeLabels,
						selectionState,
						currentTreeSpec,
						highlightRoot,
						selectedBreakdowns
					] = [
						jsv.tree,
						jsv.atts,
						tf.intersectionTree(tf.pruneTree(selectionState, breakdownMatchLevel), jsv.tree),
						treeSpecs.specs[conf.rootType][conf.treeId],
						selectedQcRootId,
						selectedBreakdowns
					];
				})
				.catch((e) => {
					console.error('error', e);
				});
		});
	}

	function updateLevelSpecs(
		tree: tt.TreeInfo,
		svgD1: number,
		expandedControlInd: number | undefined,
		breakdownOptions: tt.BreakdownOptions,
		selectedBreakdowns: tt.SelectedBreakdowns
	) {
		showPaper = false;
		if (selectedBreakdowns.length == 0) return;
		let visibleLevelCount = 0;
		for (let meta of (tree.meta || []).slice(1)) {
			if (meta.totalNodes > 0) visibleLevelCount++;
		}
		let currentOptions = breakdownOptions;
		let topOffset = 0;
		const stepSize =
			expandedControlInd === undefined ? svgD1 / visibleLevelCount : svgD1 / visibleLevelCount / 2;
		for (let i = 0; i < MAX_LEVEL_COUNT; i++) {
			levelOutSpecs[i].totalSize = expandedControlInd == i ? svgD1 / 2 + stepSize : stepSize;
			levelOutSpecs[i].topOffset = topOffset;
			levelOutSpecs[i].levelOptions = Object.keys(currentOptions);
			levelOutSpecs[i].isVisible = i < visibleLevelCount;
			topOffset += levelOutSpecs[i].totalSize;
			if (i == visibleLevelCount - 1) topOffset += svgD1 / 2;
			currentOptions = currentOptions[selectedBreakdowns[i]]?.children || {};
		}
	}

	function selectNode(path: tt.PathInTree) {
		//console.log(commLog.join(';'));
		const leafId = path[path.length - 1];
		let parentToChange = tf.getNodeByPath(path.slice(0, path.length - 1), selectionState);
		if (parentToChange?.children === undefined) {
			return;
		}
		let isSelected = Object.keys(parentToChange.children).includes(leafId.toString());
		if (isSelected) {
			delete parentToChange.children[leafId];
			selectedPath = tf.getSomePath(selectionState);
		} else {
			selectedPath = path;
			parentToChange.children[leafId] = {
				children: parentToChange.children[leafId]?.children || {}
			};
		}
		showPaper = false;
		selectionState = selectionState;
	}

	function handleInteraction(event: CustomEvent<tt.TreeInteractionEvent>) {
		const path = event.detail.path;
		const action = event.detail.action;
		if (action == 'highlight') {
			highlightedPath = path;
			showPaper = false;
			return;
		} else if (action == 'de-highlight') {
			if (removeHighlightUnhover) {
				highlightedPath = [];
			}
			return;
		}
		selectNode(path);
	}

	function getStyleMaker(d1Parser: (n: number) => number, d2Parser: (n: number) => number) {
		return (d1Obj: object, d2Obj: object, d1RateObj: object) => {
			return [
				[d1Obj || {}, d1Parser, 'px'],
				[d2Obj || {}, d2Parser, 'px'],
				[d1RateObj || {}, (x: number) => x, '%']
			]
				.map(([dObj, dParser, suffix]) =>
					Object.entries(dObj)
						.map(([k, v]) => `${k}: ${dParser(v)}${suffix};`)
						.join('')
				)
				.join('');
		};
	}
</script>

{#if !Object.values(svgShape).includes(NaN) && !Object.values(svgShape).some((e) => e === undefined)}
	<svg
		viewBox="{svgShape.x} {svgShape.y} {svgShape.width} {svgShape.height}"
		xmlns="http://www.w3.org/2000/svg"
	>
		<QuercusBranches
			branchReachBack={(svgD1 * headerRate) / 100}
			d2Offset={d2Offset + sideBarD2}
			{rootD2}
			{attributeLabels}
			{visibleTreeInfo}
			{selectionState}
			{levelOutSpecs}
			treeD2={svgD2 - sideBarD2}
			treeD2Offset={sideBarD2}
			{childD1Rate}
			{overHangRate}
			childBaseSize={minimumChildWidth}
			on:ti={handleInteraction}
		/>
		<rect id="qc-header" {...headerShape} rx="0.4" />

		<BrokenFittedText
			height={headerShape.height * 0.7}
			width={headerShape.width * 0.8}
			text={rootName || ''}
			anchor={'center'}
			bottomAligned={false}
			x={headerShape.x + headerShape.width / 2}
			y={headerShape.y + headerShape.height * 0.75}
			allowRotation={false}
		/>
	</svg>

	<div
		class="floater sentence-container"
		style={dBasedStyle({ top: 0 }, { left: d2Offset, width: rootD2 }, { height: d1TopPadRate })}
	>
		<p id="sentence-starter">{prefixText}</p>
	</div>

	<div
		class="floater"
		style={dBasedStyle(
			{ top: d1PadSize + headerShape.height * 0.5, height: 0 },
			{ left: controlPad, width: d2Offset * 0.88 },
			{}
		)}
	>
		<NumberSlider bind:value={controlSpecs.globalLimit} min={1} max={maxOnOneLevel} />
	</div>
	<div
		class="floater"
		id="right-control"
		style={dBasedStyle(
			{ top: d1PadSize, height: headerShape.height },
			{ right: controlPad, width: 100 - headerShape.width - d2Offset - controlPad },
			{}
		)}
	>
		<HeadControl
			bind:hoverToggle={showSpecInfoHover}
			bind:checked={isGlobalSpecialization}
			text={'Specialization'}
		/>
		<HeadControl
			bind:hoverToggle={showFilterHover}
			interactText={false}
			checked={false}
			text={`${pluralize('paper', completeTree.sourceCount)} since`}
		>
			<select bind:value={conf.year}
				>{#each treeSpecs.yearBreaks as y}
					<option>{y}</option>
				{/each}
			</select>
		</HeadControl>
	</div>
	{#each levelOutSpecs || [] as levelSpec, index}
		<MidpathBar
			{index}
			{levelSpec}
			d2OffsetCenter={d2Offset + rootD2 / 2}
			bind:selectedBreakdowns
			totalD1Offset={headerShape.height + d1PadSize}
			{dBasedStyle}
			rootType={conf.rootType}
		/>
	{/each}
	{#if showHoverInfo && highlightedPath.length > 0}
		<!-- svelte-ignore a11y-click-events-have-key-events -->
		<div
			transition:fade={{ duration: 200 }}
			class="hoverover shadowy clickable"
			role="treegrid"
			tabindex="0"
			style={dBasedStyle(
				{},
				{ right: 0, width: 100 },
				{ bottom: 0, height: d1BottomPadRate / (showPaper ? 0.5 : 2) }
			)}
			on:click={() => {
				if (allowPapers) {
					showPaper = !showPaper;
				}
			}}
		>
			<PathLevelInfoBox
				path={highlightedPath}
				rootNode={completeTree}
				{rootName}
				treeSpec={currentTreeSpec}
				rootId={highlightRoot}
				{attributeLabels}
				{showPaper}
			/>
		</div>
	{/if}

	<HoverBlock
		show={showSpecInfoHover}
		style={dBasedStyle(
			{ top: d1PadSize + headerShape.height },
			{ left: d2Offset + headerShape.width * 0.2, width: headerShape.width * 1.6 },
			{}
		)}
	>
		Specialization is calculated using the expected prevelance of a country, source, or concept, and
		comparing it to the one present in the current breakdown flow. If it is switched off, the sheer
		volume of citations is considered.
	</HoverBlock>

	<HoverBlock
		show={showFilterHover}
		style={dBasedStyle(
			{ top: d1PadSize + headerShape.height * 1.1 },
			{ left: d2Offset + headerShape.width * 0.2, width: headerShape.width * 1.6 },
			{}
		)}
	>
		Filter the underlying dataset to papers published in or after {conf.year}.
	</HoverBlock>
{/if}

<style>
	#qc-header {
		fill: #ffffff90;
	}

	#header-bg {
		fill: var(--color-theme-darkgrey);
	}

	#right-control {
		display: flex;
		flex-direction: column;
		justify-content: space-around;
		align-items: end;
	}

	#spec-hover {
		padding: 12px;
		font-size: 0.9rem;
	}

	#sentence-starter {
		font-size: min(1.5rem, 3.3vw);
		text-align: center;
	}

	#num-stat-subtitle {
		font-size: min(min(1.1rem, 1.9vw), 1.8svh);
		text-align: center;
	}

	.sentence-container {
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.floater {
		position: absolute;
	}

	svg {
		width: 100%;
		height: 100%;
	}
</style>
