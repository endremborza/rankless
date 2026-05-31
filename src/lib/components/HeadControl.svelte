<script lang="ts">
	import HoverI from './HoverI.svelte';

	export let text: string;
	export let hoverToggle: boolean;
	export let checked: boolean;
	export let interactText = true;
</script>

<div id="spec-container">
	<HoverI bind:hoverToggle />
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<span
		id="spec-label"
		class="vw-md {interactText ? 'clickable' : ''}"
		on:click={() => {
			if (interactText) {
				checked = !checked;
			}
		}}
	>
		{text}
	</span>
	<slot>
		<input type="checkbox" bind:checked aria-label={text} />
	</slot>
</div>

<style>
	#spec-label {
		margin: min(9px, 1.2vw);
	}

	#spec-container {
		width: 100%;
		max-width: 440px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		flex-wrap: wrap;
	}
</style>
