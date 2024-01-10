<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';

	import type {
		TreeInteractionEvent,
		QcSpecMap,
		QcSpec,
		SelectionOption,
		AttributeLabels,
		BareNode,
		ControlSpec,
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
	import BrokenFittedText from '$lib/components/BrokenFittedText.svelte';
	import { fade } from 'svelte/transition';
	import { handleStore, mainPreload } from '$lib/tree-loading';
	import Checkbox from '$lib/components/Checkbox.svelte';

	const COMMS: OMap<(s: string) => void> = {
		ce: (e) => expandControlLevel(parseInt(e)),
		se: (e) => selectNode(e.split('-')),
		sp: (e) => {
			const i = parseInt(e);
			if (i < controlSpecs.length) {
				controlSpecs[i].size_base = 'specialization';
			}
		},
		qc: (e) => {
			if (Object.keys(fullQcSpecs).includes(e)) {
				selectedQcSpecId = e;
			}
		},
		mi: (e) => {
			const i = parseInt(e.slice(0, 1));
			if (i < controlSpecs.length) {
				controlSpecs[i].include = e.slice(1).split(',');
			}
		}
	};

	async function runEventSequence(evSeqString: string) {
		if (evSeqString.length == 0) return;
		for (const evDesc of evSeqString.split(';')) {
			const evKey = evDesc.slice(0, 2);
			const evParams = evDesc.slice(2);
			// console.log('parsed comm', evKey, evParams);
			if (evKey == 'sl') {
				await new Promise((r) => setTimeout(r, parseFloat(evParams) * 1000));
			} else {
				const comm = COMMS[evKey];
				if (comm != undefined) {
					comm(evParams);
				}
			}
		}
	}

	const defaultChildRate = 0.3;
	let commLog: string[] = [];

	let innerHeight: number;
	let innerWidth: number;
	let highlightedPath: PathInTree = [];
	let selectedPath: PathInTree = [];
	let expandControlInd: number | undefined;

	let svgWidth = 100;
	let rootWidth = 25;
	let sideBarWidth = 17;
	let childHeightRate = defaultChildRate;
	let overHangRate = 0.05;

	let topPadRate = 0.03;
	let headerRate = 0.12;
	let occupyRate = 0.85;

	let minimumChildWidth = 2.5;

	let showHoverInfo = true;

	let hoverHeight = 12.5;
	let hoverWidth = sideBarWidth * 0.85;

	let foreignScales = 0.035;

	$: svgHeight = (innerHeight / innerWidth) * svgWidth - 5; // TODO: bit hacky
	$: topPadHeight = svgHeight * topPadRate;
	$: headerHeight = svgHeight * headerRate;
	$: treeVizHeight = svgHeight * (1 - headerRate) * occupyRate;

	let treeWidth = svgWidth - sideBarWidth - 2;
	let treeXOffset = sideBarWidth + 1;
	let xOffset = treeWidth * 0.15 + sideBarWidth;

	let fullQcSpecs: QcSpecMap = {};
	let specOptions: SelectionOption[] = [];
	let selectedQcSpecId: string;
	let currentQcSpec: QcSpec;

	let specBaselineOptions: SpecBaseOptions = {};

	let qcRootOptions: SelectionOption[];
	let selectedQcRootOption: SelectionOption;

	let attributeLabels: AttributeLabels = {};

	$: loadNewQc(selectedQcSpecId, selectedQcRootOption?.id);

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
			selectedQcSpecId = specOptions[0].id;

			attributeLabels = aLabels;
			specBaselineOptions = baseOptions;

			runEventSequence($page.url.searchParams.get('e') || '');
		});
	});

	function loadNewQc(specId: string | undefined, rootId: string | undefined) {
		if (specId == null || rootId == null) {
			return;
		}
		goto(`${base}/view/${$page.params.rootType}/${rootId}${$page.url.search}`);
		handleStore(`qc-builds/${specId}/${rootId}`, (obj: WeightedNode) => {
			[completeTree, controlSpecs, selectionState, currentQcSpec, controlSpecs] = [
				obj,
				controlSpecs,
				{ children: {} },
				fullQcSpecs[selectedQcSpecId],
				getEmptyLevelSpecs(specId, rootId)
			];
		});
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
	function getEmptyLevelSpecs(specId: string, pcRootId: string) {
		const out = [];
		for (var bf of fullQcSpecs[specId].bifurcations) {
			out.push({
				...DEFAULT_CONTROL_SPEC,
				...JSON.parse(formatFilter(bf.control_format_str, pcRootId))
			});
		}
		return out;
	}

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

	function expandControlLevel(ind: number) {
		if (ind == expandControlInd) {
			expandControlInd = undefined;
			childHeightRate = defaultChildRate;
		} else {
			expandControlInd = ind;
			childHeightRate = 0.5;
		}
	}

	function selectNode(path: PathInTree) {
		commLog.push(`se${path.join('-')}`);
		//console.log(commLog.join(';'));
		const leafId = path[path.length - 1];
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

	const handleControlExpansion = (event: CustomEvent<IndexEvent>) =>
		expandControlLevel(event.detail.ind);

	function handleInteraction(event: CustomEvent<TreeInteractionEvent>) {
		const path = event.detail.path;
		const action = event.detail.action;

		if (action == 'highlight') {
			[hoverLocation, highlightedPath] = [event.detail.topLeftCorner, path];
			return;
		} else if (action == 'de-highlight') {
			highlightedPath = [];
			return;
		}
		selectNode(path);
	}
</script>

<svelte:window bind:innerWidth bind:innerHeight />

<div class="treefix">
	{#if ![headerHeight, svgWidth, svgHeight].includes(NaN)}
		<svg
			viewBox="0 {-headerHeight - topPadHeight} {svgWidth} {svgHeight}"
			xmlns="http://www.w3.org/2000/svg"
		>
			<rect
				fill="grey"
				fill-opacity={0.3}
				x={0}
				y={-headerHeight}
				height={headerHeight}
				width={svgWidth}
			/>

			<rect id="qc-header" y={-headerHeight} x={xOffset} width={rootWidth} height={headerHeight} />

			{#if false && selectedPath.length > 0}
				<g style="--x-off: {svgWidth * 0.6}px; --y-off: {-headerHeight * 0.95}px">
					<filter id="blurry">
						<feGaussianBlur in="SourceGraphic" stdDeviation={rootWidth * 1.3 * 0.008} />
					</filter>
					<foreignObject
						width={(rootWidth * 1.3) / foreignScales}
						height={(headerHeight * 0.9) / foreignScales}
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
						href={`${base}/path-profile/${selectedQcSpecId}?r=${
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
					<div id="qc-type-selector">
						<select bind:value={selectedQcSpecId}>
							{#each Object.entries(fullQcSpecs) as [qcK, qcE]}
								<option value={qcK}>
									{qcE.title}
								</option>
							{/each}
						</select>
					</div>
					<div id="hover-check">
						<span>Infobox on Hover</span>
						<Checkbox values={[true, false]} labels={['On', 'Off']} bind:value={showHoverInfo} />
					</div>
				</div>
			</foreignObject>

			{#each levelVisuals || [] as lVis, index}
				<ControlInterface
					{lVis}
					{index}
					{childHeightRate}
					{overHangRate}
					{sideBarWidth}
					{svgWidth}
					{currentQcSpec}
					expandedIndex={expandControlInd}
					{attributeLabels}
					bind:controlSpecs
					on:ce={handleControlExpansion}
				/>
			{/each}

			<QuercusBranches
				qcSpec={currentQcSpec}
				branchReachBack={headerHeight}
				{xOffset}
				{rootWidth}
				{attributeLabels}
				{visibleTreeInfo}
				{selectionState}
				{levelVisuals}
				{treeWidth}
				{treeXOffset}
				{childHeightRate}
				{overHangRate}
				childBaseWidth={minimumChildWidth}
				on:ti={handleInteraction}
			/>

			<BrokenFittedText
				height={headerHeight - 2}
				width={rootWidth * 0.8}
				text={selectedQcRootOption?.name || ''}
				anchor={'middle'}
				x={xOffset + rootWidth / 2}
				y={-1}
				allowRotation={false}
			/>
			{#if highlightedBoxBase != undefined}
				<g
					transition:fade={{ duration: 100 }}
					style="--x-off:{highlightedBoxBase.position.x - hoverWidth}px; --y-off:{highlightedBoxBase
						.position.y - hoverHeight}px"
				>
					<rect
						id="hover-rect"
						height={hoverHeight}
						width={hoverWidth}
						fill="var(--color-theme-white)"
						fill-opacity="0.85"
						stroke="black"
						stroke-width="0.1px"
						rx="0.2"
					/>
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

<style>
	#qc-header {
		stroke: var(--color-theme-darkgrey);
		stroke-width: 0.06;
		filter: drop-shadow(0.2px 0.2px 0.8px rgb(0 0 0 / 0.8));
		fill: var(--color-theme-white);
		opacity: 0.5;
	}

	#qc-type-selector {
		margin-bottom: 17px;
		display: flex;
		justify-content: center;
	}

	#hover-rect {
		filter: drop-shadow(0.2px 0.2px 0.5px rgb(0 0 0 / 0.7));
	}

	#hover-check {
		display: flex;
		align-items: center;
		justify-content: center;
		margin-top: 8px;
	}

	#hover-check > span {
		margin: 5px;
	}

	option {
		font-size: 25px;
		background-color: var(--color-theme-darkgrey);
	}

	select {
		font-size: 25px;
		width: 90%;
		height: 45px;
		border: 2px solid rgba(var(--color-range-50), 0.6);
		border-radius: 10px;
		background-color: rgba(var(--color-range-10), 0.6);
	}

	.treefix {
		height: 100%;
	}
</style>
