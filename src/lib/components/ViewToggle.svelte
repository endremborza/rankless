<script lang="ts" generics="T extends string">
	// A section's switch between its views: each option a value and its label.
	export let options: readonly (readonly [T, string])[];
	export let value: T;
</script>

<div class="view-toggle">
	{#each options as [option, label], i (i)}
		<button
			class="toggle-btn"
			class:active={value === option}
			aria-pressed={value === option}
			on:click={() => (value = option)}>{label}</button
		>
	{/each}
</div>

<style>
	.view-toggle {
		display: flex;
		gap: 2px;
		flex-shrink: 0;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		border-radius: var(--control-bar-pill-radius);
		overflow: hidden;
	}

	.toggle-btn {
		background: none;
		border: none;
		font-family: inherit;
		font-size: var(--control-bar-font);
		padding: var(--control-bar-pill-pad);
		cursor: pointer;
		color: inherit;
		opacity: 0.5;
		transition:
			opacity 0.15s,
			background 0.15s;
	}

	.toggle-btn.active {
		opacity: 1;
		background: rgba(var(--color-range-15), 0.1);
	}
</style>
