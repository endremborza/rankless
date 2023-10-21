<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';

	import AutoComplete from 'simple-svelte-autocomplete';
	import type {
		TreeInteractionEvent,
		QcSpecMap,
		QcSpec,
		SelectionOption,
		AttributeLabels,
		BareNode,
		ControlSpec,
		RootMeta,
		PathInTree,
		IndexEvent,
		WeightedNode,
		OMap,
		SpecBaseOptions
	} from '$lib/tree-types';
	import {
		getNodeByPath,
		getLevelVisuals,
		DEFAULT_CONTROL_SPEC,
		deriveVisibleTree,
		getSomePath,
		treePathToStr
	} from '$lib/tree-functions';

	import QuercusBranches from '$lib/components/QuercusBranches.svelte';
	import PathLevelInfoBox from '$lib/components/PathLevelInfoBox.svelte';
	import ControlInterface from '$lib/components/ControlInterface.svelte';
	import { APP_NAME } from '$lib/constants';
	import { getColor, getColorArr } from '$lib/style-util';
	import BrokenFittedText from '$lib/components/BrokenFittedText.svelte';
	import { fade } from 'svelte/transition';
	import { handleStore, mainPreload } from '$lib/tree-loading';

	const defaultChildRate = 0.3;

	let innerHeight: number;
	let innerWidth: number;
	let highlightedPath: PathInTree = [];
	let selectedPath: PathInTree = [];
	let expandControlInd: number | undefined;

	let footHeight = 50;
	let svgWidth = 100;
	let rootWidth = 25;
	let sideBarWidth = 17;
	let childRate = defaultChildRate;
	let overHangRate = 0.05;

	let headerRate = 0.12;
	let occupyRate = 0.9;

	let showHoverInfo = true;

	let hoverHeight = 10;
	let hoverWidth = sideBarWidth * 0.85;

	let foreignScales = 0.035;

	$: svgHeight = ((innerHeight - footHeight) / innerWidth) * svgWidth - 5; // TODO: bit hacky
	$: headerHeight = svgHeight * headerRate;
	$: treeVizHeight = svgHeight * (1 - headerRate) * occupyRate;

	let treeWidth = svgWidth - sideBarWidth;
	let treeXOffset = sideBarWidth;
	let xOffset = treeWidth * 0.1 + sideBarWidth;

	let fullQcSpecs: QcSpecMap = {};
	let specOptions: SelectionOption[] = [];
	let selectedQcSpecOption: SelectionOption;

	let specBaselineOptions: SpecBaseOptions = {};

	let qcRootOptions: SelectionOption[];
	let selectedQcRootOption: SelectionOption;

	let attributeLabels: AttributeLabels = {};

	$: currentQcSpec = fullQcSpecs[selectedQcSpecOption?.id || ''];
	$: loadNewQc(selectedQcSpecOption?.id, selectedQcRootOption?.id);

	const toSelOpt = (entry: [string, QcSpec]) => ({ id: entry[0], name: entry[1].title });

	onMount(() => {
		handleStore('root-descriptions', (jsv: OMap<SelectionOption[]>) => {
			qcRootOptions = jsv[$page.params.rootType];
			selectedQcRootOption = qcRootOptions.filter((x) => x.id == $page.params.rootId)[0];
		});

		mainPreload().then(([aLabels, allQcSpecs, baseOptions]) => {
			fullQcSpecs = Object.fromEntries(
				Object.entries(allQcSpecs).filter(([k, v]) => v.root_entity_type == $page.params.rootType)
			);
			specOptions = Object.entries(fullQcSpecs).map(toSelOpt);
			selectedQcSpecOption = specOptions[0];

			attributeLabels = aLabels;
			specBaselineOptions = baseOptions;
		});
	});

	function loadNewQc(specId: string | undefined, rootId: string | undefined) {
		if ([specId, rootId].includes(undefined)) {
			return;
		}
		goto(`${base}/view/${$page.params.rootType}/${rootId}`);
		handleStore(`qc-builds/${specId}/${rootId}`, (obj: WeightedNode) => {
			refillLevelSpecs();
			[completeTree, controlSpecs, rootMeta] = [
				obj,
				controlSpecs,
				getMeta() // TODO: if root type is not an entity type this is a problem
			];
		});
	}

	function getMeta() {
		try {
			return attributeLabels[currentQcSpec.root_entity_type][selectedQcRootOption?.id || ''].meta;
		} catch {
			return {};
		}
	}

	function getHighlightedBoxBase(
		highlightedPath: PathInTree,
		showHoverInfo: boolean,
		hoverLocation: { x: number; y: number }
	) {
		return showHoverInfo && highlightedPath.length > 0
			? { node: getNodeByPath(highlightedPath, visibleTreeInfo.tree), position: hoverLocation }
			: undefined;
	}

	function formatFilter(s: string, pcRootId: any) {
		let regexp = new RegExp('\\{pc_id\\}', 'gi');
		return s.replace(regexp, pcRootId);
	}
	function refillLevelSpecs() {
		const pcRootId = selectedQcRootOption?.id;
		while (controlSpecs.length > 0) {
			controlSpecs.pop();
		}

		if (![currentQcSpec, pcRootId].includes(undefined)) {
			for (var bf of currentQcSpec.bifurcations) {
				controlSpecs.push({
					...DEFAULT_CONTROL_SPEC,
					...JSON.parse(formatFilter(bf.control_format_str, pcRootId))
				});
			}
		}
	}

	let rootMeta: RootMeta = {};
	let controlSpecs: ControlSpec[] = [DEFAULT_CONTROL_SPEC];
	let completeTree: WeightedNode = { weight: 1 };
	let selectionState: BareNode = { children: {} };

	let hoverLocation = { x: 0, y: 0 };

	$: visibleTreeInfo = deriveVisibleTree(
		selectedQcRootOption?.id,
		completeTree,
		controlSpecs,
		selectionState,
		attributeLabels,
		currentQcSpec,
		specBaselineOptions
	);
	$: levelVisuals = getLevelVisuals(visibleTreeInfo, treeVizHeight, expandControlInd);

	$: highlightedBoxBase = getHighlightedBoxBase(highlightedPath, showHoverInfo, hoverLocation);

	function handleControlExpansion(event: CustomEvent<IndexEvent>) {
		if (event.detail.ind == expandControlInd) {
			expandControlInd = undefined;
			childRate = defaultChildRate;
		} else {
			expandControlInd = event.detail.ind;
			childRate = 0.5;
		}
	}

	function handleInteraction(event: CustomEvent<TreeInteractionEvent>) {
		const path = event.detail.path;
		const leafId = path[path.length - 1];
		const action = event.detail.action;

		if (action == 'highlight') {
			[hoverLocation, highlightedPath] = [event.detail.topLeftCorner, path];
			return;
		} else if (action == 'de-highlight') {
			highlightedPath = [];
			return;
		}

		let parentToChange = getNodeByPath(path.slice(0, path.length - 1), selectionState);
		if (parentToChange?.children === undefined) {
			return;
		}
		let isSelected = Object.keys(parentToChange.children).includes(leafId);

		if (isSelected) {
			delete parentToChange.children[leafId];
			selectedPath = getSomePath(selectionState);
		} else {
			selectedPath = path;
			parentToChange.children[leafId] = {
				children: parentToChange.children[leafId]?.children || {}
			};
		}
		selectionState = selectionState;
	}
</script>

<svelte:window bind:innerWidth bind:innerHeight />

<div class="treefix">
	<div class="treecontent">
		{#if ![headerHeight, svgWidth, svgHeight].includes(NaN)}
			<svg viewBox="0 {-headerHeight} {svgWidth} {svgHeight}" xmlns="http://www.w3.org/2000/svg">
				{#if selectedPath.length > 0}
					<g
						transform="translate({svgWidth * 0.6}, {-headerHeight * 0.9})"
						transition:fade={{ duration: 300 }}
					>
						<filter id="blurry">
							<feGaussianBlur in="SourceGraphic" stdDeviation={rootWidth * 1.3 * 0.008} />
						</filter>
						<rect
							id="info-bg"
							style="--selected-color: {getColorArr(
								getNodeByPath(selectedPath, visibleTreeInfo?.tree || {})?.scaleEnds.mid || 0.5
							)}"
							height={headerHeight * 1.2}
							width={rootWidth * 1.3}
							rx={0.3}
							opacity={0.95}
							filter="url(#blurry)"
						/>
						<foreignObject
							width={(rootWidth * 1.3) / foreignScales}
							height={(headerHeight * 1.2) / foreignScales}
							transform="scale({foreignScales},{foreignScales})"
						>
							<PathLevelInfoBox
								path={selectedPath}
								weightedRoot={completeTree}
								{specBaselineOptions}
								{attributeLabels}
								qcSpec={currentQcSpec}
								rootId={selectedQcRootOption?.id}
							/>
						</foreignObject>
						<a
							href={`${base}/path-profile/${selectedQcSpecOption.id}?r=${
								selectedQcRootOption.id
							}&p=${treePathToStr(selectedPath)}`}
							target="_blank"
						>
							<text y={1.8} font-size="1.2px" href="/">Open</text>
						</a>
					</g>
				{/if}
				<foreignObject
					y={-headerHeight / foreignScales}
					width={sideBarWidth / foreignScales}
					height={500}
					transform="scale({foreignScales},{foreignScales})"
				>
					<div style="padding: 20px">
						<div style="margin-bottom: 17px">
							<AutoComplete
								items={specOptions}
								bind:selectedItem={selectedQcSpecOption}
								labelFieldName="name"
								valueFieldName="id"
								hideArrow={true}
							/>
						</div>
						<div style="margin-top: 17px">
							<AutoComplete
								items={qcRootOptions}
								bind:selectedItem={selectedQcRootOption}
								labelFieldName="name"
								valueFieldName="id"
								hideArrow={true}
								maxItemsToShowInList={3}
							/>
						</div>
						<div style="margin-top: 8px;">
							<input type="checkbox" bind:checked={showHoverInfo} /> Show Infobox on Hover
						</div>
					</div>
				</foreignObject>

				{#each levelVisuals || [] as lVis, index}
					<ControlInterface
						{lVis}
						{index}
						{childRate}
						{overHangRate}
						{sideBarWidth}
						{svgWidth}
						{currentQcSpec}
						expandedIndex={expandControlInd}
						{attributeLabels}
						bind:controlSpecs
						on:control-expand={handleControlExpansion}
					/>
				{/each}
				<linearGradient id="hbow" x1="0%" y1="0%" x2="100%" y2="0%">
					{#each [0, 0.25, 0.5, 0.75, 1.0] as rStop}
						<stop offset="{rStop * 100}%" style="stop-color:{getColor(rStop)};stop-opacity:0.35" />
					{/each}
				</linearGradient>
				<QuercusBranches
					qcSpec={currentQcSpec}
					{xOffset}
					{rootWidth}
					{attributeLabels}
					{visibleTreeInfo}
					{selectionState}
					{levelVisuals}
					{rootMeta}
					{treeWidth}
					{treeXOffset}
					{childRate}
					{overHangRate}
					on:tree-interaction={handleInteraction}
				/>
				<rect
					x={xOffset}
					y={-headerHeight}
					width={rootWidth}
					height={headerHeight}
					fill="url(#hbow)"
				/>
				<g transform="translate({xOffset}, 0)">
					<BrokenFittedText
						height={headerHeight}
						width={rootWidth}
						text={selectedQcRootOption?.name || ''}
					/>
				</g>
				{#if highlightedBoxBase != undefined}
					<g
						transform="translate({highlightedBoxBase.position.x - hoverWidth}, {highlightedBoxBase
							.position.y - hoverHeight})"
					>
						<rect height={hoverHeight} width={hoverWidth} fill="pink" fill-opacity="0.85" />
						<foreignObject
							height={hoverHeight / foreignScales}
							width={hoverWidth / foreignScales}
							transform="scale({foreignScales},{foreignScales})"
						>
							<PathLevelInfoBox
								path={highlightedPath}
								weightedRoot={completeTree}
								{specBaselineOptions}
								{attributeLabels}
								qcSpec={currentQcSpec}
								rootId={selectedQcRootOption?.id}
							/>
						</foreignObject>
					</g>
				{/if}
			</svg>
		{/if}
	</div>
	<div class="treefoot" style="--foot-height: {footHeight}px">
		<a href={`${base}/`}><b>{APP_NAME}</b></a>
	</div>
</div>

<style>
	#info-bg {
		fill: rgba(var(--selected-color), 0.55);
		border-style: solid;
		border-color: black;
	}

	.treefix {
		display: flex;
		flex-flow: column;
		height: 100%;
	}

	.treefix .treecontent {
		flex: 1 1 auto;
	}

	.treefix .treefoot {
		display: flex;
		justify-content: center;
		align-items: center;
		flex: 0 0 var(--foot-height);
	}
</style>
