<script lang="ts">
	export let text: string | null;
</script>

{#if text}
	<p class="data-note" role="note"><span class="label">Data note:</span> {text}</p>
{/if}

<style>
	.data-note {
		margin: 24px 0 0;
		padding: 0.5rem 0.7rem;
		border: 1px solid var(--color-warn);
		font-size: var(--text-sm);
	}

	.label {
		font-weight: 700;
	}
</style>
