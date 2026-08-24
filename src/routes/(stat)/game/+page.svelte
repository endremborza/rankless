<!-- Hub for the games; also keeps pre-split /game share links working. -->
<script lang="ts">
	import GameShell from '$lib/components/GameShell.svelte';
</script>

<svelte:head>
	<title>Games — Rankless</title>
	<meta
		name="description"
		content="Daily guessing games over verified scholarly data: pin the hidden institution on a map, or race to place misleadingly named universities."
	/>
</svelte:head>

<GameShell title="Games">
	<p class="intro">Two daily rounds over the live citation data. New cards every day.</p>
	<div class="games">
		<a class="game-tile" href="/game-clues">
			<h2>🗺️ Guess the institution</h2>
			<p>
				A hidden research institution, described by verified citation facts — hardest first. Drop a
				pin on the map; the earlier and closer, the more points.
			</p>
		</a>
		<a class="game-tile" href="/game-countries">
			<h2>🏛️ Name that country</h2>
			<p>
				Universities whose names point everywhere but home. Four countries, a few seconds each — one
				wrong pick ends the run.
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
