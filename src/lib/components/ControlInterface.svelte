<script lang="ts">
	import { fade } from 'svelte/transition';

	import type { QcSpec, LevelVisElem, ControlSpec, AttributeLabels } from '$lib/tree-types';
	import BrokenFittedText from './BrokenFittedText.svelte';
	import { getDispatch, expandThis } from '$lib/tree-events';
	import { getTopFzf } from '$lib/search-util';
	import Checkbox from './Checkbox.svelte';
	import CollapseButton from './CollapseButton.svelte';

	type FilterKey = 'exclude' | 'include';
	const filterKeys: [FilterKey, FilterKey] = ['exclude', 'include'];

	export let lVis: LevelVisElem;
	export let index: number;
	export let expandedIndex: number | undefined;
	export let childHeightRate: number;
	export let overHangRate: number;
	export let sideBarWidth: number;
	export let svgWidth: number;
	export let currentQcSpec: QcSpec;
	export let controlSpecs: ControlSpec[];

	export let attributeLabels: AttributeLabels;

	export let maxOnOneLevel: number = 15;
	export let minShow = 1;

	export let controlHtmlWidth = 320;

	const dispatch = getDispatch();
	let duration = 400;
	let labelWidth = 30;
	let sliderHeight = 30;
	let thumbWidth = 80;
	let thumbHeight = sliderHeight - 4;
	$: sliderWidth = controlHtmlWidth - labelWidth * 2;

	$: isExpanded = index == expandedIndex;
	$: bif = currentQcSpec?.bifurcations[index];
	$: topOffset =
		lVis.topOffset + lVis.totalSize - lVis.totalSize * (childHeightRate + overHangRate);
	$: fullHeight = lVis.totalSize * childHeightRate;

	$: mainScale = (sideBarWidth * 0.85) / controlHtmlWidth;

	$: svgScaleHeight = sliderHeight * mainScale;

	$: heightInElements = fullHeight / svgScaleHeight;

	$: levelAttributes = attributeLabels[bif?.attribute_kind] || {};

	$: showTopN = heightInElements > 3.2;
	$: topNClass = showTopN ? '' : 'control-hidden';
	$: showMinOrMaxControl = heightInElements > 4.8;
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

{#if bif != undefined}
	<g transition:fade={{ duration }} style="--y-off: {topOffset}px;">
		<rect
			fill="grey"
			height="1"
			width={svgWidth}
			style="transform: matrix(1, 0, 0, {fullHeight}, 0, 0); opacity: {isExpanded ? 0.5 : 0.3}"
		/>
		<BrokenFittedText
			text={currentQcSpec?.bifurcations[index]?.description || ''}
			width={sideBarWidth * 0.9}
			height={svgScaleHeight * 2}
			x={sideBarWidth * 0.1}
			y={-0.5}
		/>

		<foreignObject
			width={controlHtmlWidth}
			height={fullHeight / mainScale}
			style="transform: matrix({mainScale}, 0, 0, {mainScale}, 0, 0)"
		>
			<div
				class="main-controls"
				style="--full-width: {controlHtmlWidth}px; --slider-width: {sliderWidth}px; --label-width: {labelWidth}px; --thumb-width: {thumbWidth}px; --slider-height: {sliderHeight}px; --thumb-height: {thumbHeight}px"
			>
				<div class="control-elem">
					<Checkbox
						bind:value={controlSpecs[index].size_base}
						values={possScaleTypes}
						width={sliderWidth}
					/>
				</div>
				<div
					class="control-elem {topNClass}"
					style="--r: {labelWidth +
						((sliderWidth - thumbWidth) * (controlSpecs[index].limit_n - minShow)) /
							(maxOnOneLevel - minShow)}px"
				>
					{#if showTopN}
						<div id="topn-control" transition:fade={{ duration }}>
							<div id="topn-slider">
								<span>{minShow}</span>
								<input
									id="topn-input"
									type="range"
									min={minShow}
									max={maxOnOneLevel}
									bind:value={controlSpecs[index].limit_n}
								/>
								<span>{maxOnOneLevel}</span>
							</div>
							<label for="topn-input">show {controlSpecs[index].limit_n}</label>
						</div>
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
			</div>
		</foreignObject>
		<!-- svelte-ignore a11y-click-events-have-key-events -->
		<!-- svelte-ignore a11y-no-static-element-interactions -->
		<g
			style="transform: matrix(1,0,0,1,{sideBarWidth * 0.85}, {fullHeight * 0.03})"
			on:click={expandThis(dispatch, index)}
		>
			<CollapseButton size={svgScaleHeight} rotated={isExpanded ? 180 : 0} />
		</g>
	</g>
{/if}

<style>
	rect,
	foreignObject {
		transition: 0.8s;
	}

	#topn-control {
		position: relative;
		width: 100%;
		display: flex;
		flex-direction: column;
	}

	#topn-control > label {
		text-align: center;
		position: absolute;
		width: var(--thumb-width);
		height: var(--slider-height);
		left: var(--r);
		top: 2px;
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1;
		pointer-events: none;
		-webkit-user-select: none;
		/* Safari */
		-ms-user-select: none;
		/* IE 10 and IE 11 */
		user-select: none;
		/* Standard syntax */
	}

	#topn-slider {
		display: flex;
		align-items: center;
	}

	#topn-slider > span {
		width: var(--label-width);
		text-align: center;
	}

	input[type='range'] {
		width: var(--slider-width);
		height: var(--slider-height);
		/* border: solid var(--color-theme-darkgrey) 2px; */
		background-color: var(--color-theme-lightblue);
		opacity: 0.9;
		border-radius: var(--slider-height);
		z-index: 0;
		outline: none;
		appearance: none;
		-webkit-appearance: none;
		/* Remove default styles on webkit browsers */
	}

	input[type='range']::-webkit-slider-thumb {
		width: var(--thumb-width);
		height: var(--thumb-height);
		background-color: rgba(var(--color-range-20), 0.6);
		color: rgba(var(--color-range-20), 0.6);
		border: 2px solid rgba(var(--color-range-50), 0.6);
		border-radius: var(--thumb-height);
		cursor: pointer;
		position: relative;
		z-index: 2;
		appearance: none;
		-webkit-appearance: none;
	}

	input[type='range']::-moz-range-thumb {
		width: var(--thumb-width);
		height: var(--thumb-height);
		background-color: rgba(var(--color-range-10), 0.6);
		color: rgba(var(--color-range-25), 0.6);
		border: 2px solid rgba(var(--color-range-50), 0.6);
		border-radius: var(--thumb-height);
		cursor: pointer;
		position: relative;
		z-index: 2;
	}

	.main-controls {
		height: 100%;
		width: var(--full-width);
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
		font-size: var(--thumb-height) px;
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

	.sub-input {
		display: flex;
		justify-content: space-between;
		align-items: center;
		width: var(--slider-width);
	}

	.selected-card {
		border: 2px solid rgba(var(--color-range-15), 0.25);
		border-radius: 3px;
		background-color: rgba(var(--color-range-65), 0.45);
		padding: 5px;
		margin: 4px;
	}
</style>
