<script lang="ts">
	export let hoverToggle: boolean;
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<span
	id="spec-info-hover"
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
		font-weight: 400;
		border: 1px solid var(--color-text);
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
</style>
