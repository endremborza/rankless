<script lang="ts">
	import { fade } from 'svelte/transition';

	export let value: number;
	export let min: number;
	export let max: number;
	export let duration = 400;
</script>

<div class="vert-zero" transition:fade={{ duration }}>
	<input id="slider" type="range" {min} {max} bind:value />
	<label for="slider"><span>−</span><span>+</span></label>
</div>

<style>
	div {
		width: 100%;
	}

	input {
		width: 80%;
	}

	label {
		text-align: center;
		position: absolute;
		font-weight: 600;
		width: 100%;
		display: flex;
		align-items: center;
		justify-content: space-between;
		z-index: 1;
		pointer-events: none;
		-webkit-user-select: none;
		-ms-user-select: none;
		user-select: none;
	}
</style>
