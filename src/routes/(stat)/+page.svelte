<script lang="ts">
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { INSTITUTION_TYPE } from '$lib/constants';
	import type { SelectionOption } from '$lib/tree-types';
	import AutoComplete from 'simple-svelte-autocomplete';
	import { onMount } from 'svelte';
	import { handleStore } from '$lib/tree-loading';
	import HexagonLogo from '$lib/components/HexagonLogo.svelte';
	import Checkbox from '$lib/components/Checkbox.svelte';

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

	let rotScaler = 0.3;

	function onFocus() {
		rotScaler += 0.9;
	}

	function onBlur() {
		rotScaler -= 0.9;
	}
</script>

<div class="bstrip t1">
	<svg width="100%" height="800px" viewBox="-3 -3 12 6" xmlns="http://www.w3.org/2000/svg">
		<HexagonLogo {rotScaler} />
	</svg>

	<div class="bar">
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
		margin-bottom: 20px;
	}

	.bstrip {
		position: relative;
	}

	.t1 {
		margin-top: 80px;
		background-color: rgba(var(--color-range-65), 0.25);
	}

	.bar {
		position: absolute;
		top: 35%;
		width: 40%;
		padding: 150px;
		flex: 0 1 700px;
		display: flex;
		flex-wrap: wrap;
		align-items: end;
		justify-content: end;
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
		background-color: rgba(var(--color-range-80), 0.7) !important;
		border: 2px solid rgba(var(--color-range-45), 0.45);
		border-radius: 4px;
	}

	:global(.selected) {
		text-decoration: underline;
		font-weight: bolder;
	}
</style>
