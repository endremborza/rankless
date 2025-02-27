<script lang="ts">
	import { fade } from 'svelte/transition';

	import type {
		QcSpec,
		LevelOutSpec,
		ControlSpec,
		AttributeLabels,
		SelectedBreakdowns
	} from '$lib/tree-types';
	import { getTopFzf } from '$lib/search-util';
	import Checkbox from './Checkbox.svelte';
	import VerticalCheckbox from './VerticalCheckbox.svelte';
	import NumberSlider from './NumberSlider.svelte';
	import CogWheel from './CogWheel.svelte';

	type FilterKey = 'exclude' | 'include';
	const filterKeys: [FilterKey, FilterKey] = ['exclude', 'include'];

	export let lVis: LevelOutSpec;
	export let selectedBreakdowns: SelectedBreakdowns;
	export let index: number;
	export let expandedIndex: number | undefined;
	export let childD1Rate: number;
	export let overHangRate: number;
	export let sideBarD2: number;
	export let svgD2: number;
	export let currentQcSpec: QcSpec;
	export let controlSpecs: ControlSpec[];

	export let attributeLabels: AttributeLabels;

	export let maxOnOneLevel: number = 15;
	export let minShow = 1;

	let controlHtmlD2 = 320;

	let duration = 400;
	let sliderHeight = 30;
	let labelWidth = 30;

	$: mainScale = (sideBarD2 * 0.85) / controlHtmlD2;
	$: isExpanded = index == expandedIndex;
	$: bif = currentQcSpec?.bifurcations[index];
	$: levelAttributes = attributeLabels[bif?.attribute_kind] || {};

	$: d1Offset = lVis.topOffset + lVis.totalSize - lVis.totalSize * (childD1Rate + overHangRate);
	$: d1Size = lVis.totalSize * childD1Rate;

	$: blockShape = { x: 0, y: d1Offset, height: d1Size, width: sideBarD2 };

	$: barShape = { x: -0.5 * svgD2, y: 0, height: lVis.totalSize * childD1Rate, width: svgD2 * 2 };
	$: foShape = { height: d1Size / mainScale, width: controlHtmlD2, x: 0, y: 0 };
	$: sliderWidth = foShape.width || 0 - labelWidth * 2;
	$: svgScaleHeight = sliderHeight * mainScale;
	$: heightInElements = foShape.height || 0 / svgScaleHeight;

	$: showTopN = heightInElements > 3.2;
	$: showMinOrMaxControl = heightInElements > 40000.8;
	$: minOrMaxClass = showMinOrMaxControl ? '' : 'control-hidden';
	$: expandedClass = isExpanded ? '' : 'control-hidden';

	let incExcFzfTerm = '';
	$: topFzf = getTopFzf(incExcFzfTerm, levelAttributes, 4);

	let editIncludeExclude = false;
	const makeIncludeExcludeEditable = () => (editIncludeExclude = true);
	const disableIncludeExcludeEditable = () => (editIncludeExclude = false);

	let possScaleTypes: [string, string] = ['volume', 'specialization'];
	let sideOptions: [string, string] = ['highest', 'lowest'];
	let showSide = controlSpecs[index].show_top ? 'highest' : 'lowest';
	$: ((ss) => {
		controlSpecs[index].show_top = ss == 'highest';
	})(showSide);

	function addFilterId(id: string, key: FilterKey) {
		return () => {
			controlSpecs[index][key] = [id, ...controlSpecs[index][key].filter((x) => x != id)];
		};
	}

	function dropFilterId(id: string, key: FilterKey) {
		return () => {
			controlSpecs[index][key] = controlSpecs[index][key].filter((x) => x != id);
		};
	}

	function labelFunction(id: string) {
		return levelAttributes[id]?.name || 'Unknown';
	}
</script>

<g transition:fade={{ duration }} style="transform: translate({blockShape.y}px, {blockShape.x}px)">
	<foreignObject
		width={foShape.width}
		height={foShape.height}
		style="transform: matrix({mainScale}, 0, 0, {mainScale}, 0, 0)"
	>
		<div class="main-controls" style="width: {foShape.width}px">
			{#if !isExpanded}
				<div />
			{:else}
				<div class="control-elem">
					<VerticalCheckbox
						bind:value={controlSpecs[index].size_base}
						values={possScaleTypes}
						width={sliderWidth}
					/>
				</div>
				<div class="control-elem" style="">
					{#if showTopN}
						<NumberSlider
							bind:value={controlSpecs[index].limit_n}
							min={minShow}
							max={maxOnOneLevel}
							width={foShape.width}
							{duration}
						/>
					{/if}
				</div>

				<div class="control-elem {minOrMaxClass}">
					{#if showMinOrMaxControl}
						<Checkbox bind:value={showSide} values={sideOptions} width={sliderWidth} />
					{/if}
				</div>

				<div class="control-elem {expandedClass}">
					{#if isExpanded}
						<input
							type="text"
							bind:value={incExcFzfTerm}
							placeholder="include/exclude"
							class="fzf-input"
						/>
						{#if editIncludeExclude}
							<div class="blurred-overlay">
								<button class="close-button" on:click={disableIncludeExcludeEditable}
									>&#10006;</button
								>
								{#each filterKeys as lKey}
									{#each controlSpecs[index][lKey] as valInd}
										<span class="selected-card"
											>{labelFunction(valInd)}
											<!-- svelte-ignore a11y-no-static-element-interactions -->
											<!-- svelte-ignore a11y-click-events-have-key-events -->
											<span on:click={dropFilterId(valInd, lKey)} class="clear-button"
												>&#10006;</span
											></span
										>
									{/each}
								{/each}
							</div>
						{:else if topFzf.length > 0}
							<div transition:fade={{ duration: 100 }} class="blurred-overlay">
								<button class="close-button" on:click={() => (incExcFzfTerm = '')}>&#10006;</button>
								<ul>
									{#each topFzf as fzfResult}
										<li>
											{fzfResult.name}
											<button on:click={addFilterId(fzfResult.id, 'include')}>include</button>
											<button on:click={addFilterId(fzfResult.id, 'exclude')}>exclude</button>
										</li>
									{/each}
								</ul>
							</div>
						{/if}
						<span class="include-exclude-desc">
							<span>
								{controlSpecs[index].include.length} included,
								{controlSpecs[index].exclude.length} excluded
							</span>
							<button on:click={makeIncludeExcludeEditable}>edit</button>
						</span>
					{/if}
				</div>
			{/if}
		</div>
	</foreignObject>
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<g style="transform: matrix(0.03,0,0,0.03,{blockShape.width * 0.9}, {blockShape.height * 0.9})">
		<g
			style="transform: scale(0.1) rotate({isExpanded
				? 0
				: 120}deg) translate(-256px,-256px) ;cursor: pointer;"
			on:click={() => {
				if (isExpanded) {
					expandedIndex = undefined;
				} else {
					expandedIndex = index;
				}
			}}
		>
			<CogWheel />
			<rect height="512" width="512" opacity="0" />
		</g>
	</g>
</g>

<style>
	rect,
	foreignObject {
		transition: 0.8s;
	}

	.main-controls {
		height: 100%;
		display: flex;
		flex-direction: column;
		justify-content: space-around;
		align-items: center;
	}

	.control-elem {
		flex: 1 0 0px;
		transition: flex 1s;
		display: flex;
		flex-direction: column;
		justify-content: center;
	}

	.control-hidden {
		flex: 0 1 0px;
	}

	.blurred-overlay {
		backdrop-filter: blur(28px);
		-webkit-backdrop-filter: blur(28px);
		border: 2px solid black;
		border-radius: 10px;
		position: absolute;
		top: 3px;
		left: 10px;
		width: 95%;
		height: 73%;
		z-index: 4;
	}

	.fzf-input {
		background-color: rgba(var(--color-range-15), 0.25) !important;
		border: 2px solid rgba(var(--color-range-55), 0.5) !important;
		border-radius: 4px !important;
		width: 100%;
		padding-top: 5px;
		padding-bottom: 5px;
	}

	.clear-button {
		font-weight: 900;
		cursor: pointer;
	}

	.close-button {
		position: absolute;
		top: 3px;
		right: 3px;
	}

	.include-exclude-desc {
		width: 100%;
		padding-top: 9px;
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.selected-card {
		border: 2px solid rgba(var(--color-range-15), 0.25);
		border-radius: 3px;
		background-color: rgba(var(--color-range-65), 0.45);
		padding: 5px;
		margin: 4px;
	}
</style>
