<script lang="ts">
	import {base} from '$app/paths';
	import {goto} from '$app/navigation';
	import {onMount} from 'svelte';
	import {handleStore} from '$lib/tree-loading';
	import {formatNumber} from '$lib/text-format-util';
	import {getTopFzfInsts} from '$lib/search-util';
	import type {SelectionOption} from '$lib/tree-types';
	import {INSTITUTION_TYPE} from '$lib/constants';

	export let resultsHidden: boolean;
	export let searchTerm: string;

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
	$: searchResults = getTopFzfInsts(searchTerm, instOptions, 6);
</script>

<div class="search-results" style="display: {resultsHidden ? 'none' : 'flex'};">
	<span id="result-closer" on:click={()=> (resultsHidden = true)}>&#10006;</span>
	{#each searchResults as searchResult}
	<div on:click={()=> onChange(searchResult)} class="result-card">
		<h3>
			{searchResult.name}
		</h3>
		<span class="subtitle">{formatNumber(searchResult.papers)} papers,
			{formatNumber(searchResult.citations)} citations</span>
	</div>
	{/each}
</div>

<style>
	h3 {
		margin: 0px;
		margin-bottom: 12px;
		font-size: 1.9em;
	}

	.search-results {
		width: 100%;
		height: 100dvh;
		backdrop-filter: blur(6px);
		position: fixed;
		top: 0px;
		z-index: 10;
		flex-direction: columns;
		flex-wrap: wrap;
		justify-content: space-around;
		align-items: start;
		padding-top: 180px;
	}

	.result-card {
		cursor: pointer;
		height: 210px;
		min-width: 240px;
		background-color: var(--color-theme-white);
		border: solid var(--color-theme-darkblue) 1px;
		box-shadow: 15px 15px 80px var(--color-theme-darkgrey3);
		border-radius: 10px;
		margin: 40px;
		margin-bottom: 20px;
		margin-top: 0px;
		text-align: left;
		flex: 0 0 13%;
		padding: 30px;
		display: flex;
		flex-direction: column;
		justify-content: space-around;
		left: 8%;
		transition: transform 0.2s ease;
	}

	/* Hover effect */
	.result-card:hover {
    	transform: translateY(-10px); /* Move the card up slightly on hover */
		color: var(--color-theme-darkblue);
	}

	.subtitle {
		font-size: 1.2em;
	}

	#result-closer {
		position: absolute;
		top: 70px;
		left: 95%;
		font-size: 37px;
		padding: 12px;
		text-align: center;
		border-radius: 35px;
		cursor: pointer;
	}
</style>
