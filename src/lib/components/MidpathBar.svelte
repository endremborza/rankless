<script lang="ts">
	import { semantify, semOptioned } from '$lib/text-format-util';
	import type { LevelOutSpec, OMap, RootType } from '$lib/tree-types';
	import { fade } from 'svelte/transition';

	export let levelSpec: LevelOutSpec;
	export let index: number;
	export let selectedBreakdowns: string[];
	export let totalD1Offset: number;
	export let d2OffsetCenter: number;
	export let rootType: RootType;
	export let allowControls: boolean = true;
	export let dBasedStyle: (d1: OMap<number>, d2: OMap<number>, d3: OMap<number>) => string;

	$: canSelect = levelSpec.levelOptions.length > 1 && allowControls;
</script>

{#if levelSpec.isVisible}
	<div
		transition:fade={{ duration: 400 }}
		class="sentenceline"
		style={dBasedStyle(
			{
				top: levelSpec.topOffset + levelSpec.totalSize * 0.2 + totalD1Offset,
				height: levelSpec.totalSize * 0.25
			},
			{},
			{}
		)}
	>
		<div class="sel-cover {canSelect ? 'sel-clicky' : ''}" style="--d2-shift: {d2OffsetCenter}%">
			<span>
				{semantify(selectedBreakdowns[index], rootType, selectedBreakdowns, index).split('<')[0]}
			</span>
		</div>
		{#if canSelect}
			<select
				bind:value={selectedBreakdowns[index]}
				class="sel-base"
				style="opacity: 0"
				aria-label="Breakdown selection"
			>
				{#each levelSpec.levelOptions as bd}
					<option value={bd}>
						{semOptioned(semantify(bd, rootType, selectedBreakdowns, index), bd)}
					</option>
				{/each}
			</select>
		{/if}
		<div class="bg filler" />
	</div>
{/if}

<style>
	span {
		text-align: center;
	}

	option {
		font-size: min(1.5rem, 3.5vw);
		text-align: center;
	}

	select {
		cursor: pointer;
		-webkit-appearance: menulist-button;
		appearance: menulist-button;
	}

	.sentenceline {
		position: absolute;
		transition: all 700ms;
		display: flex;
		justify-content: left;
		align-items: center;
		left: 0%;
		width: 100%;
		backdrop-filter: blur(5px);
		-webkit-backdrop-filter: blur(5px);
		box-shadow: 0 0 4px 4px #ffffff80;
	}

	.filler {
		position: absolute;
		left: 0px;
		width: 100%;
		height: 100%;
	}

	.bg {
		z-index: -1;
	}

	.sel-base {
		position: absolute;
		top: 0px;
		height: 100%;
		width: 100%;
	}

	.sel-cover {
		display: flex;
		justify-content: center;
		align-items: center;
		margin-left: var(--d2-shift);
		transform: translateX(-50%);
	}

	.sel-clicky > span::after {
		content: ' \25BD';
	}

	.sel-cover > span {
		padding: 8px;
		background: #ffffff70;
		backdrop-filter: blur(10px);
		-webkit-backdrop-filter: blur(10px);
	}

	.sel-clicky > span {
		border: 1px solid var(--color-theme-darkblue);
		color: var(--color-theme-darkblue);
	}
</style>
