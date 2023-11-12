<script lang="ts">
	import { fade } from 'svelte/transition';

	import type { QcSpec, LevelVisElem, ControlSpec, AttributeLabels } from '$lib/tree-types';
	import BrokenFittedText from './BrokenFittedText.svelte';
	import AutoComplete from 'simple-svelte-autocomplete';
	import { expandThis, getDispatch } from '$lib/tree-events';
	import Checkbox from './Checkbox.svelte';
	import CollapseButton from './CollapseButton.svelte';

	export let lVis: LevelVisElem;
	export let index: number;
	export let expandedIndex: number | undefined;
	export let childRate: number;
	export let overHangRate: number;
	export let sideBarWidth: number;
	export let svgWidth: number;
	export let currentQcSpec: QcSpec;
	export let controlSpecs: ControlSpec[];

	export let attributeLabels: AttributeLabels;

	export let maxOnOneLevel: number = 15;
	export let minShow = 1;

	export let controlHtmlWidth = 320;

	let duration = 200;
	let labelWidth = 30;
	let sliderHeight = 30;
	let thumbWidth = 80;
	let thumbHeight = sliderHeight - 4;
	$: sliderWidth = controlHtmlWidth - labelWidth * 2;

	const dispatch = getDispatch();

	$: isExpanded = index == expandedIndex;
	$: bif = currentQcSpec?.bifurcations[index];
	$: topOffset = lVis.topOffset + lVis.totalSize - lVis.totalSize * (childRate + overHangRate);
	$: fullHeight = lVis.totalSize * childRate;
	$: leftPad = sideBarWidth * 0.02;
	$: topPad = fullHeight * 0.03;

	$: mainScale = (sideBarWidth * 0.85) / controlHtmlWidth;

	$: svgScaleHeight = sliderHeight * mainScale;

	$: heightInElements = fullHeight / svgScaleHeight;

	// let items = [];

	$: levelAttributes = attributeLabels[bif?.attribute_kind] || {};

	$: items = Object.keys(levelAttributes);

	let possScaleTypes: [string, string] = ['volume', 'specialization'];
	let sideOptions: [string, string] = ['highest', 'lowest'];
	let showSide = controlSpecs[index].show_top ? 'highest' : 'lowest';
	$: ((ss) => {
		controlSpecs[index].show_top = ss == 'highest';
	})(showSide);

	function dropId(id: string, key: 'include' | 'exclude') {
		return () => {
			controlSpecs[index][key] = controlSpecs[index][key].filter((x) => x != id);
		};
	}

	function labelFunction(id: string) {
		return levelAttributes[id]?.name || 'Unknown';
	}
</script>

{#if bif != undefined}
	<g transition:fade={{ duration: 1000 }} style="--y-off: {topOffset}px; --x-off: {leftPad}px">
		<rect
			fill="grey"
			fill-opacity={isExpanded ? 0.5 : 0.3}
			x={-leftPad}
			height={fullHeight}
			width={svgWidth}
		/>
		<g style="--x-off: {sideBarWidth * 0.1}px; --y-off: {-0.5}px">
			<BrokenFittedText
				text={currentQcSpec?.bifurcations[index]?.description || ''}
				width={sideBarWidth * 0.9}
				height={svgScaleHeight * 2}
			/>
		</g>

		<!-- svelte-ignore a11y-click-events-have-key-events -->
		<!-- svelte-ignore a11y-no-static-element-interactions -->
		<g
			style="--x-off: {sideBarWidth * 0.85}px; --y-off: {topPad}px"
			on:click={expandThis(dispatch, index)}
		>
			<CollapseButton
				size={svgScaleHeight}
				text={isExpanded ? 'collapse' : 'expand'}
				rotated={isExpanded ? 180 : 0}
			/>
		</g>

		<g style="--y-off: {topPad}px;">
			<foreignObject
				width={controlHtmlWidth}
				height={(fullHeight / mainScale) * 1.5}
				transform="scale({mainScale},{mainScale})"
			>
				<div
					class="main-controls"
					style="--full-width: {controlHtmlWidth}px; --slider-width: {sliderWidth}px; --label-width: {labelWidth}px; --thumb-width: {thumbWidth}px; --slider-height: {sliderHeight}px; --thumb-height: {thumbHeight}px"
				>
					<div id="spec-checkbox">
						<Checkbox
							bind:value={controlSpecs[index].size_base}
							values={possScaleTypes}
							width={sliderWidth}
						/>
					</div>
					{#if heightInElements > 2.8}
						<div
							id="topn-control"
							style="--r: {labelWidth +
								((sliderWidth - thumbWidth) * (controlSpecs[index].limit_n - minShow)) /
									(maxOnOneLevel - minShow)}px"
							transition:fade={{ duration }}
						>
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

					{#if isExpanded}
						<div id="side-checkbox" transition:fade={{ duration }}>
							<Checkbox bind:value={showSide} values={sideOptions} width={sliderWidth} />
						</div>

						<div class="sub-controls" transition:fade={{ duration }}>
							{#each ['include', 'exclude'] as lKey}
								<div class="sub-input">
									<AutoComplete
										{items}
										className={'sub-input-selector'}
										inputClassName={'sub-input-box'}
										bind:value={controlSpecs[index][lKey]}
										multiple={true}
										hideArrow={true}
										{labelFunction}
										maxItemsToShowInList={5}
										placeholder={lKey}
									>
										<span slot="tag" />
									</AutoComplete>
								</div>
								<div class="card-set">
									{#each controlSpecs[index][lKey] as valInd}
										<span class="selected-card"
											>{labelFunction(valInd)}
											<!-- svelte-ignore a11y-no-static-element-interactions -->
											<!-- svelte-ignore a11y-click-events-have-key-events -->
											<span on:click={dropId(valInd, lKey)} class="clear-button">&#10006;</span
											></span
										>
									{/each}
								</div>
							{/each}
						</div>
					{/if}
				</div>
			</foreignObject>
		</g>
	</g>
{/if}

<style>
	rect {
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
		-webkit-user-select: none; /* Safari */
		-ms-user-select: none; /* IE 10 and IE 11 */
		user-select: none; /* Standard syntax */
	}

	#spec-checkbox {
		margin-bottom: 10px;
	}

	#side-checkbox {
		margin-top: 10px;
		margin-bottom: 10px;
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
		-webkit-appearance: none; /* Remove default styles on webkit browsers */
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
		width: var(--full-width);
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
	}

	.clear-button {
		font-weight: 900;
		cursor: pointer;
	}

	.sub-input {
		display: flex;
		justify-content: space-between;
		align-items: center;
		width: var(--slider-width);
	}

	.card-set {
		width: var(--slider-width);
		margin-top: 3px;
		margin-bottom: 7px;
		display: flex;
		flex-wrap: wrap;
	}

	.selected-card {
		border: 2px solid rgba(var(--color-range-15), 0.25);
		border-radius: 3px;
		background-color: rgba(var(--color-range-65), 0.45);
		padding: 5px;
		margin: 4px;
	}

	:global(.sub-input-selector) {
		width: 100%;
	}

	:global(.input-container) {
		background-color: rgba(var(--color-range-15), 0.25) !important;
		border: 2px solid rgba(var(--color-range-55), 0.5) !important;
		border-radius: 4px !important;
	}
</style>
