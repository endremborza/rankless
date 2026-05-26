<script lang="ts">
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { pluralize } from '$lib/text-format-util';
	import { MAX_LEVEL_COUNT, BE_REMOTE_URL, WIDE_LAYOUT_PX } from '$lib/constants';

	import QuercusBranches from '$lib/components/QuercusBranches.svelte';
	import PathLevelInfoBox from '$lib/components/PathLevelInfoBox.svelte';
	import BrokenFittedText from '$lib/components/BrokenFittedText.svelte';
	import NumberSlider from '$lib/components/NumberSlider.svelte';
	import MidpathBar from '$lib/components/MidpathBar.svelte';
	import HeadControl from './HeadControl.svelte';
	import { onMount } from 'svelte';
	import { replaceState } from '$app/navigation';
	import { debounce } from '$lib/util';
	import HoverBlock from './HoverBlock.svelte';
	import { htmlToText } from '$lib/utils/paper-helpers';

	export let conf: tt.FullTreeConfig;
	export let selectedQcRootId: number;

	export let rootName = '';
	export let prefixText = '';
	export let setUrl = true;
	export let allowControls = true;
	export let shoPathLevelInfo = true;
	export let shallowed = false;
	export let fixHeight = true;
	export let treeSpecs: tt.TreeSpecs;
	export let selectionState: tt.BareNode = { children: {} };
	export let completeTree: tt.ResponseNode;
	export let attributeLabels: tt.AttributeLabels;
	export let currentTreeSpec: tt.TreeSpec = treeSpecs.specs[conf.rootType][conf.treeId];
	export let selectedBreakdowns = tf.getDefaultBreakdowns(currentTreeSpec);
	export let isGlobalSpecialization = currentTreeSpec.defaultIsSpec;

	let mounted = false;
	let showPaper = false;

	let containerWidth: number;
	let containerHeight: number;

	let breakdownMatchLevel: number = currentTreeSpec.breakdowns.length;

	let highlightedPath: tt.PathInTree = []; //TODO: investigate why this is how it is
	let highlightRoot = selectedQcRootId;
	let selectedPath: tt.PathInTree = [];
	let expandControlInd: number | undefined;
	let armingPath: tt.PathInTree | null = null;
	let highlightDelay = 1000;

	let defaultChildD1Rate = 0.3;

	let svgD2 = 100;
	let rootD2 = 25;
	let d2Offset = (svgD2 - rootD2) / 3.3;

	let sideBarD2 = 0;

	let d1TopPadRate = 8;
	let d1BottomPadRate = 8;
	let headerRate = 11;
	let overHangRate = 0.05;

	let minimumChildWidth = 2.5;
	let showSpecInfoHover = false;
	let showFilterHover = false;

	let levelOutSpecs: tt.LevelOutSpec[] = tf.getDefaultLevelSpecs();
	let controlSpecs = tf.getDefaultControlSpecs(isGlobalSpecialization);
	let maxOnOneLevel = 15;

	onMount(async () => {
		mounted = true;
		if (shallowed && allowControls) {
			let initConf = conf;
			try {
				const jsv = await tf.fetchTree(BE_REMOTE_URL, initConf);
				if (
					initConf.treeId == conf.treeId &&
					initConf.semanticId == conf.semanticId &&
					initConf.year == conf.year
				) {
					[completeTree, attributeLabels, shallowed] = [jsv.tree, jsv.atts, false];
				}
			} catch (e) {
				console.error('error', e);
			}
		}
	});

	$: childD1Rate = expandControlInd == undefined ? defaultChildD1Rate : 0.7;
	$: svgD1 = (containerHeight / containerWidth) * svgD2;
	$: d1ToPixels = (d1: number) => (d1 * containerHeight) / svgD1;
	$: d2ToPixels = (d2: number) => (d2 * containerWidth) / svgD2;
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
	$: controlSpecs.globalSizeBase = isGlobalSpecialization ? 'specialization' : 'volume';

	$: updateUrl(conf, selectionState);

	$: updateLevelSpecs(
		visibleTreeInfo,
		svgD1 * (1 - (headerRate + d1BottomPadRate) / 100),
		expandControlInd,
		tf.getBreakdownOptions(treeSpecs, conf.rootType),
		selectedBreakdowns
	);

	const debouncedReplaceState = debounce((url: string) => replaceState(url, {}), 120);

	function updateUrl(conf: tt.FullTreeConfig, selectionState: tt.BareNode) {
		if (mounted && setUrl) {
			debouncedReplaceState(tf.toLinkWithParams(conf, selectionState));
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

	async function loadNewQc(conf: tt.FullTreeConfig) {
		showPaper = false;
		highlightedPath = [];
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
		let newTreeSpec = treeSpecs.specs[conf.rootType][conf.treeId];
		let newGlobalSpec = isGlobalSpecialization;
		if (newTreeSpec.defaultIsSpec != currentTreeSpec.defaultIsSpec) {
			newGlobalSpec = newTreeSpec.defaultIsSpec;
		}
		try {
			const jsv = await tf.fetchTree(BE_REMOTE_URL, conf);
			[
				completeTree,
				attributeLabels,
				selectionState,
				currentTreeSpec,
				highlightRoot,
				selectedBreakdowns,
				isGlobalSpecialization,
				shallowed
			] = [
				jsv.tree,
				jsv.atts,
				tf.intersectionTree(tf.pruneTree(selectionState, breakdownMatchLevel), jsv.tree),
				newTreeSpec,
				selectedQcRootId,
				selectedBreakdowns,
				newGlobalSpec,
				false
			];
		} catch (e) {
			console.error('error', e);
		}
	}

	function updateLevelSpecs(
		tree: tt.TreeInfo,
		svgD1: number,
		expandedControlInd: number | undefined,
		breakdownOptions: tt.BreakdownOptions,
		selectedBreakdowns: tt.SelectedBreakdowns
	) {
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
		const leafId = path[path.length - 1];
		let parentToChange = tf.getNodeByPath(path.slice(0, path.length - 1), selectionState);
		if (parentToChange?.children === undefined) {
			return false;
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
		return !isSelected;
	}

	function handleInteraction(event: CustomEvent<tt.TreeInteractionEvent>) {
		const path = event.detail.path;
		const action = event.detail.action;
		if (action == 'highlight') {
			highlightedPath = path;
			showPaper = false;
		} else if (action == 'arm') {
			armingPath = path;
		} else if (action == 'disarm') {
			armingPath = null;
		} else {
			if (selectNode(path)) {
				highlightedPath = path;
			}
		}
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

<div class="papered-figure-container {fixHeight ? 'wide-screen-heighted' : ''}">
	<div
		class="figure-container"
		bind:clientWidth={containerWidth}
		bind:clientHeight={containerHeight}
	>
		{#if !Object.values(svgShape).includes(NaN) && !Object.values(svgShape).some((e) => e === undefined)}
			<svg
				viewBox="{svgShape.x} {svgShape.y} {svgShape.width} {svgShape.height}"
				xmlns="http://www.w3.org/2000/svg"
			>
				<QuercusBranches
					branchReachBack={(svgD1 * headerRate) / 100}
					d2Offset={d2Offset + sideBarD2}
					{rootD2}
					{visibleTreeInfo}
					{levelOutSpecs}
					hoverDelay={highlightDelay}
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
					text={htmlToText(rootName) || ''}
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
				<h3>{prefixText}</h3>
			</div>

			{#if allowControls}
				<div
					class="floater"
					style={dBasedStyle(
						{ top: d1PadSize + headerShape.height * 0.5, height: 0 },
						{ left: 0, width: d2Offset * 0.88 },
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
						{ right: 0, width: 100 - headerShape.width - d2Offset },
						{}
					)}
				>
					<HeadControl
						bind:hoverToggle={showSpecInfoHover}
						bind:checked={isGlobalSpecialization}
						text={'Specialization'}
					/>
					{#if tf.hasYearFilter(conf.rootType)}
						<HeadControl
							bind:hoverToggle={showFilterHover}
							interactText={false}
							checked={false}
							text={`since`}
						>
							<select bind:value={conf.year} aria-label="Since year"
								>{#each treeSpecs.yearBreaks as y}
									<option>{y}</option>
								{/each}
							</select>
						</HeadControl>
					{/if}
				</div>
			{/if}
			{#each levelOutSpecs || [] as levelSpec, index}
				<MidpathBar
					{index}
					{levelSpec}
					d2OffsetCenter={d2Offset + rootD2 / 2}
					bind:selectedBreakdowns
					totalD1Offset={headerShape.height + d1PadSize}
					{dBasedStyle}
					rootType={conf.rootType}
					{allowControls}
				/>
			{/each}
			<HoverBlock
				show={showSpecInfoHover}
				style={dBasedStyle(
					{ top: d1PadSize + headerShape.height },
					{ left: d2Offset + headerShape.width * 0.2, width: headerShape.width * 1.6 },
					{}
				)}
			>
				Specialization is calculated using the expected prevelance of a country, source, or concept,
				and comparing it to the one present in the current breakdown flow. If it is switched off,
				the sheer volume of citations is considered.
			</HoverBlock>

			<HoverBlock
				show={showFilterHover}
				style={dBasedStyle(
					{ top: d1PadSize + headerShape.height * 1.1 },
					{ left: d2Offset + headerShape.width * 0.2, width: headerShape.width * 1.6 },
					{}
				)}
			>
				Filter the underlying dataset to papers published in or after {conf.year}. This includes {pluralize(
					'paper',
					completeTree.sourceCount
				)} making up this tree, where all necessary information is available to create this breakdown.
			</HoverBlock>
		{/if}
	</div>
	{#if shoPathLevelInfo}
		<div class="infobox-container">
			<PathLevelInfoBox
				path={highlightedPath}
				rootNode={completeTree}
				{rootName}
				treeSpec={currentTreeSpec}
				rootId={highlightRoot}
				{attributeLabels}
				delay={highlightDelay}
				{armingPath}
				bind:showPaper
				hasSpaceForPaper={containerWidth > WIDE_LAYOUT_PX}
			/>
		</div>
	{/if}
</div>

<style>
	#qc-header {
		fill: var(--hard-overlay);
	}

	#right-control {
		display: flex;
		flex-direction: column;
		justify-content: space-around;
		align-items: end;
	}

	.sentence-container {
		display: flex;
		justify-content: center;
		align-items: center;
	}

	.floater {
		position: absolute;
	}

	@media (max-width: 899px) {
		.figure-container {
			height: 75svh;
			flex: none;
		}
	}

	svg {
		width: 100%;
		height: 100%;
		display: block;
	}
</style>
