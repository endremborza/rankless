<script lang="ts">
	import {slide} from 'svelte/transition';

	export let title: string;
	export let id: string;
	export let selectedId: string | undefined;

	function onClick() {
		if (selectedId == id) {
			selectedId = undefined;
		} else {
			selectedId = id;
		}
	}

	$: isSelected = selectedId == id;
</script>

<div {id} on:click={onClick} class="accord-header">
	<svg viewBox="-10 -10 20 20">
		<g style="transform: {isSelected ? 'rotate(45deg)' : 'rotate(0deg)'}">
			<path d="M-9,0h18" />
			<path d="M0,-9v18" />
		</g>
	</svg>
	<h3 style="color: {isSelected ? 'var(--color-theme-darkblue)' : ''};">{title}</h3>
</div>
{#if isSelected}
<p transition:slide={{ duration: 500 }}>
	<slot />
</p>
{/if}
<hr />

<style>
	h3:hover {
		color: var(--color-theme-darkgrey3);
	}

	svg {
		height: 30px;
		width: 30px;
		flex: 0 0 30px;
		margin-right: 18px;
	}

	path {
		stroke: black;
		width: 1px;
	}

	p,
	g {
		transition: all 200ms;
	}

	p {
		padding-bottom: 10px;
	}

	.accord-header {
		display: flex;
		align-items: center;
		cursor: pointer;
		scroll-margin-top: 100px;
	}
</style>
