<!-- Centered-card frame for the games hub (/game): title header and the
	.intro chrome. The game pages use the full-viewport GameFrame instead. -->
<script lang="ts">
	export let title: string;
</script>

<main class="page">
	<section class="card shadowy padded">
		<h1>{title}</h1>
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

	.card :global(.intro) {
		margin-bottom: 1rem;
	}
</style>
