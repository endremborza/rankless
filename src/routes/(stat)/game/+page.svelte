<!-- Hub for the games. -->
<script lang="ts">
	import GameShell from '$lib/components/GameShell.svelte';
	import { BRAND, DAILY_SIZE, PATH } from '$lib/utils/game-geo';
</script>

<svelte:head>
	<title>Games — Rankless</title>
	<meta
		name="description"
		content="A daily geography quiz over verified scholarly data: where an institution really is, which city, which is closest, which one is not here."
	/>
</svelte:head>

<GameShell title="Games">
	<p class="intro">A daily round over the live citation data. New cards every day.</p>
	<div class="games">
		<a class="game-tile" href={PATH}>
			<h2>🏛️ {BRAND}</h2>
			<p>
				Institution names can point far from home. {DAILY_SIZE} cards a day: where is it actually, which
				city, which is closest, which one is not here — trust your first instinct.
			</p>
		</a>
	</div>
</GameShell>

<style>
	.games {
		display: grid;
		gap: 1rem;
	}

	.game-tile {
		display: block;
		padding: 1.25rem 1.5rem;
		border: 1px solid var(--border-light);
		color: inherit;
		text-decoration: none;
	}

	.game-tile:hover {
		border-color: currentColor;
	}

	.game-tile h2 {
		margin: 0 0 0.5rem;
	}

	.game-tile p {
		margin: 0;
	}
</style>
