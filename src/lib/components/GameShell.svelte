<!-- Centered-card frame for the hub and the clue game (/game, /game-clues),
	with title + streak header and their shared chrome classes (intro, mode-row,
	actions, reveal, verdict, error) as :global styles scoped under the card.
	The arcade game pages use the full-viewport GameFrame instead. -->
<script lang="ts">
	export let title: string;
	export let streak = 0;
	export let wide = false;
</script>

<main class="page">
	<section class="card shadowy padded" class:wide>
		<div class="head-row">
			<h1>{title}</h1>
			{#if streak > 0}
				<div class="streak">🔥 {streak}-day streak</div>
			{/if}
		</div>
		<slot />
	</section>
</main>

<style>
	.page {
		padding: 2rem;
		display: flex;
		justify-content: center;
	}

	.card {
		width: min(760px, 95%);
		background: var(--text-bg-2);
		padding: 2rem;
	}

	.card.wide {
		width: min(980px, 95%);
	}

	.head-row {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: 1rem;
	}

	.streak {
		font-weight: 600;
		white-space: nowrap;
	}

	.card :global(.intro) {
		margin-bottom: 1rem;
	}

	.card :global(.mode-row) {
		display: flex;
		align-items: center;
		gap: 1rem;
		margin-bottom: 0.75rem;
	}

	.card :global(.mode-label) {
		font-weight: 600;
	}

	.card :global(.actions) {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		margin: 0.75rem 0;
	}

	.card :global(.reveal) {
		margin-top: 1rem;
		padding-top: 1rem;
		border-top: 1px solid var(--border-light);
	}

	.card :global(.verdict) {
		font-size: var(--text-lg);
	}

	.card :global(.error) {
		color: var(--color-err);
	}
</style>
