<script lang="ts">
	export let hoverToggle: boolean;
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<span
	id="spec-info-hover"
	class="small-hover"
	on:mouseover={() => {
		hoverToggle = true;
	}}
	on:mouseleave={() => {
		hoverToggle = false;
	}}>i</span
>

<style>
	#spec-info-hover {
		font-size: 0.7rem;
		border: 1px solid var(--color-theme-darkgrey);
		padding: 4px;
		padding-left: 8px;
		padding-right: 8px;
		border-radius: 1rem;
		cursor: pointer;
	}

	#spec-info-hover:hover {
		color: var(--color-theme-darkblue);
		border: 1.2px solid var(--color-theme-darkblue);
		background-color: var(--color-theme-white);
	}

	.small-hover {
		font-size: min(0.7rem, 2.2vw);
	}
</style>
