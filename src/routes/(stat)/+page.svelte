<script lang="ts">
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { INSTITUTION_TYPE } from '$lib/constants';
	import type { SelectionOption } from '$lib/tree-types';
	import AutoComplete from 'simple-svelte-autocomplete';
	import { onMount } from 'svelte';
	import { handleStore } from '$lib/tree-loading';
	import HexagonLogo from '$lib/components/HexagonLogo.svelte';

	let instOptions: SelectionOption[] = [];

	onMount(() => {
		handleStore('root-descriptions', (jsv) => {
			// @ts-ignore
			instOptions = jsv[INSTITUTION_TYPE];
		});
	});

	function onChange(e: SelectionOption | undefined) {
		if (e != undefined) {
			goto(`${base}/view/${INSTITUTION_TYPE}/${e.id}`); //TODO this is capitalized!!
		}
	}

	let rotScaler = 1.2;

	function onFocus() {
		rotScaler -= 0.9;
	}

	function onBlur() {
		rotScaler += 0.9;
	}
</script>

<div class="bstrip t1">
	<div id="logo-bar">
		<svg width="100%" height="100%" viewBox="-3 -3 6 6" xmlns="http://www.w3.org/2000/svg">
			<HexagonLogo {rotScaler} />
		</svg>
	</div>

	<div id="search-bar">
		<h1>Explore the impact of an academic institution!</h1>
		<AutoComplete
			className={'inst-selector'}
			inputClassName={'inst-input'}
			dropdownClassName={'inst-dropdown'}
			selectId={'inst-selected'}
			items={instOptions}
			{onChange}
			{onFocus}
			{onBlur}
			labelFieldName="name"
			valueFieldName="id"
			hideArrow={true}
		/>
	</div>
</div>

<style>
	h1 {
		text-align: center;
	}

	.bstrip {
		position: relative;
	}

	.t1 {
		margin-top: 80px;
		background-color: rgba(var(--color-range-65), 0.25);
	}

	#logo-bar {
		flex: 1;
		flex-basis: 200px;
		height: 600px;
		min-width: 200px;
		max-width: 600px;
	}

	#search-bar {
		width: 70%;
		padding-top: 150px;
		padding-bottom: 100px;
		padding-right: 40px;
		padding-left: 40px;
		flex: 3;
		min-width: 200px;
		max-width: 800px;
		display: flex;
		flex-wrap: wrap;
		align-items: end;
		justify-content: start;
	}

	:global(.inst-selector) {
		font-size: x-large;
		width: 100%;
	}
	:global(.inst-input) {
		background-color: rgba(var(--color-range-20), 0.7);
		border: 2px solid rgba(var(--color-range-55), 0.85);
		border-radius: 4px;
		width: 100%;
	}
	:global(.inst-dropdown) {
		background-color: rgba(var(--color-range-95), 0.98) !important;
		border: 2px solid rgba(var(--color-range-45), 0.45);
		border-radius: 4px;
	}

	:global(.selected) {
		text-decoration: underline;
		font-weight: bolder;
	}
</style>
