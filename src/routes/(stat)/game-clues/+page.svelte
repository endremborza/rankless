<script lang="ts">
	import { onMount } from 'svelte';

	import type { PageData } from './$types';
	import GameGuessMap from '$lib/components/GameGuessMap.svelte';
	import GameShell from '$lib/components/GameShell.svelte';
	import { entToLink } from '$lib/tree-functions';
	import { formatNumber } from '$lib/text-format-util';
	import type { GameResultLog, PlayCard } from '$lib/types/game-clues';
	import {
		ccFlag,
		copyShareText,
		loadGameState,
		nextStreak,
		postGameLog,
		saveGameState
	} from '$lib/utils/game';
	import { N_CLUES, haversineKm, roundScore, shareText, type LatLon } from '$lib/utils/game-clues';

	export let data: PageData;

	const STORAGE_KEY = 'rankless-game';
	const EMPTY_STATE: StoredState = { streak: 0, lastDay: '', lastResult: null };

	type StoredState = {
		streak: number;
		lastDay: string;
		lastResult: {
			cluesUsed: number;
			distanceKm: number | null;
			score: number;
			gaveUp: boolean;
			guess: LatLon | null;
		} | null;
	};

	let mounted = false;
	let mode: 'daily' | 'practice' = 'daily';
	let card: PlayCard | null = null;
	let cluesShown = 1;
	let pin: LatLon | null = null;
	let locked = false;
	let gaveUp = false;
	let distanceKm: number | null = null;
	let score = 0;
	let streak = 0;
	let copied = false;
	let practiceNext: PlayCard | null = null;
	let prefetching = false;

	const day = data.day;

	onMount(() => {
		startDaily();
		mounted = true;
	});

	function startDaily() {
		mode = 'daily';
		card = data.card;
		const stored = loadGameState(STORAGE_KEY, EMPTY_STATE);
		streak = stored.streak;
		if (stored.lastDay === day && stored.lastResult) {
			const r = stored.lastResult;
			cluesShown = r.cluesUsed;
			pin = r.guess;
			locked = true;
			gaveUp = r.gaveUp;
			distanceKm = r.distanceKm;
			score = r.score;
			prefetchPractice();
		} else {
			resetRound();
		}
	}

	// Background loader for practice rounds: a card is prefetched when a round
	// locks (and after each consumed prefetch), so "play a practice round" is
	// instant and the full pack never ships to the browser.
	async function fetchPractice(): Promise<PlayCard | null> {
		try {
			const res = await fetch(`/api/game-clues?not=${encodeURIComponent(card?.semId ?? '')}`);
			if (!res.ok) return null;
			return (await res.json()) as PlayCard;
		} catch {
			return null;
		}
	}

	async function prefetchPractice() {
		if (prefetching || practiceNext || data.packSize < 2) return;
		prefetching = true;
		practiceNext = await fetchPractice();
		prefetching = false;
	}

	async function startPractice() {
		const next = practiceNext ?? (await fetchPractice());
		practiceNext = null;
		if (!next) return;
		mode = 'practice';
		card = next;
		resetRound();
		prefetchPractice();
	}

	function resetRound() {
		cluesShown = 1;
		pin = null;
		locked = false;
		gaveUp = false;
		distanceKm = null;
		score = 0;
		copied = false;
	}

	function nextClue() {
		if (cluesShown < visibleClueCount) cluesShown += 1;
	}

	function finishRound(surrendered: boolean) {
		if (!card || locked) return;
		locked = true;
		gaveUp = surrendered;
		if (!surrendered && pin) {
			distanceKm = haversineKm(pin, { lat: card.lat, lon: card.lon });
			score = roundScore(distanceKm, cluesShown);
		} else {
			distanceKm = null;
			score = 0;
		}
		if (mode === 'daily') {
			const stored = loadGameState(STORAGE_KEY, EMPTY_STATE);
			streak = nextStreak(stored.streak, stored.lastDay, day, surrendered);
			saveGameState(STORAGE_KEY, {
				streak,
				lastDay: day,
				lastResult: { cluesUsed: cluesShown, distanceKm, score, gaveUp, guess: pin }
			});
		}
		logResult();
		prefetchPractice();
	}

	function logResult() {
		if (!card) return;
		const payload: GameResultLog = {
			mode,
			day,
			semId: card.semId,
			cluesUsed: cluesShown,
			gaveUp,
			guessLat: pin?.lat ?? null,
			guessLon: pin?.lon ?? null,
			distanceKm,
			score
		};
		postGameLog('/api/game-clues', payload);
	}

	async function copyShare() {
		if (distanceKm == null && !gaveUp) return;
		copied = await copyShareText(shareText(day, cluesShown, visibleClueCount, distanceKm, score));
	}

	$: visibleClueCount = card ? Math.min(N_CLUES, card.clues.length) : 0;
	$: shownClues = card ? card.clues.slice(0, cluesShown) : [];
	$: target = locked && card ? { lat: card.lat, lon: card.lon } : null;
</script>

<svelte:head>
	<title>Guess the institution — Rankless</title>
	<meta
		name="description"
		content="A daily guessing game: pin the hidden research institution on the map from a ladder of verified citation facts."
	/>
</svelte:head>

<GameShell title="Guess the institution" streak={mounted ? streak : 0} wide>
	<p class="intro">
		A hidden research institution, described by facts from its citation record — hardest first. Drop
		a pin on the map; the earlier and closer, the more points.
	</p>

	{#if !mounted}
		<p>Loading…</p>
	{:else if !card}
		<p class="error">No cards in the store yet.</p>
	{:else}
		<div class="mode-row">
			<span class="mode-label">{mode === 'daily' ? `Daily · ${day}` : 'Practice round'}</span>
			{#if mode === 'practice'}
				<button class="btn" on:click={startDaily}>Back to daily</button>
			{/if}
		</div>

		<ol class="clues">
			{#each shownClues as clue, i (i)}
				<li>
					<span class="clue-stage">{i + 1}</span>
					<span>{clue.text}</span>
				</li>
			{/each}
		</ol>

		{#if !locked}
			<div class="actions">
				<button class="btn" on:click={nextClue} disabled={cluesShown >= visibleClueCount}>
					Next clue ({cluesShown}/{visibleClueCount})
				</button>
				<button class="btn primary" on:click={() => finishRound(false)} disabled={!pin}>
					{pin ? 'Lock in guess' : 'Place your pin first'}
				</button>
				<button class="btn subtle" on:click={() => finishRound(true)}>Give up</button>
			</div>
		{/if}

		<GameGuessMap bind:pin {target} disabled={locked} />

		{#if locked}
			<div class="reveal">
				<h2>
					{ccFlag(card.cc)}
					<a href={entToLink({ rootType: 'institutions', semanticId: card.semId })}>{card.name}</a>
				</h2>
				<p>
					{formatNumber(card.papers)} papers · {formatNumber(card.citations)} citations — every clue above
					is a reproduced query against the live data.
				</p>
				{#if gaveUp}
					<p class="verdict">No guess this time — 0 points.</p>
				{:else if distanceKm != null}
					<p class="verdict">
						<strong>{Math.round(distanceKm)} km</strong> off after {cluesShown}
						clue{cluesShown === 1 ? '' : 's'} — <strong>{score} points</strong>.
					</p>
				{/if}
				<div class="actions">
					{#if mode === 'daily'}
						<button class="btn" on:click={copyShare}>{copied ? 'Copied!' : 'Copy result'}</button>
					{/if}
					<button class="btn primary" on:click={startPractice}>Play a practice round</button>
				</div>
			</div>
		{/if}
	{/if}
</GameShell>

<style>
	.clues {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin: 0 0 1rem;
		padding: 0;
		list-style: none;
	}

	.clues li {
		display: flex;
		gap: 0.6rem;
		align-items: baseline;
		padding: 0.5rem 0.75rem;
		border: 1px solid var(--border-light);
	}

	.clue-stage {
		font-weight: 700;
		min-width: 1.2rem;
		text-align: center;
	}
</style>
