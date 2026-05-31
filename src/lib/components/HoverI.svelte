<script lang="ts">
	export let hoverToggle: boolean;
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_mouse_events_have_key_events -->
<div
	id="spec-info-hover"
	on:mouseover={() => {
		hoverToggle = true;
	}}
	on:mouseleave={() => {
		hoverToggle = false;
	}}
>
	<span> i </span>
</div>

<style>
	#spec-info-hover {
		font-size: var(--text-xs);
		font-weight: 400;
		border: 1px solid var(--color-text);
		display: inline-flex;
		justify-content: center;
		align-items: center;
		cursor: pointer;
		border-radius: 1rem;
		height: 1.5rem;
		width: 1.5rem;
	}

	#spec-info-hover > span {
		pointer-events: none;
	}

	#spec-info-hover:hover {
		color: var(--color-theme-darkblue);
		border: 1.2px solid var(--color-theme-darkblue);
		background-color: var(--color-theme-white);
	}
</style>
