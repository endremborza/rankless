<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	import type { PageData } from './$types';
	import GameShell from '$lib/components/GameShell.svelte';
	import type { CountryPlayCard, CountryRunLog } from '$lib/types/game-countries';
	import {
		ccFlag,
		ccName,
		copyShareText,
		loadGameState,
		nextStreak,
		postGameLog,
		saveGameState
	} from '$lib/utils/game';
	import { ADVANCE_MS, RUN_SECONDS, runShareText } from '$lib/utils/game-countries';

	export let data: PageData;

	const STORAGE_KEY = 'rankless-game-countries';
	const RUN_MS = RUN_SECONDS * 1000;
	const TICK_MS = 100;

	type StoredState = {
		streak: number;
		lastDay: string;
		lastScore: number;
		lastOutOf: number;
		lastSwept: boolean;
	};
	const EMPTY_STATE: StoredState = {
		streak: 0,
		lastDay: '',
		lastScore: 0,
		lastOutOf: 0,
		lastSwept: false
	};

	let mounted = false;
	let mode: 'daily' | 'practice' = 'daily';
	let phase: 'idle' | 'playing' | 'over' = 'idle';
	let deck: CountryPlayCard[] = [];
	let idx = -1;
	let picked: string | null = null;
	let timedOut = false;
	let swept = false;
	let score = 0;
	let outOf = 0;
	let streak = 0;
	let playedToday = false;
	let copied = false;
	let fetching = false;
	let msLeft = RUN_MS;
	let deadline = 0;
	let timer: ReturnType<typeof setInterval> | null = null;
	let advancing: ReturnType<typeof setTimeout> | null = null;

	const day = data.day;

	onMount(() => {
		restoreDaily();
		mounted = true;
	});

	onDestroy(stopClocks);

	function stopClocks() {
		if (timer) clearInterval(timer);
		if (advancing) clearTimeout(advancing);
		timer = null;
		advancing = null;
	}

	// Restores the finished daily round from storage; false when today is
	// still unplayed (the caller decides what phase that means).
	function restoreDaily(): boolean {
		const stored = loadGameState(STORAGE_KEY, EMPTY_STATE);
		streak = stored.streak;
		if (stored.lastDay !== day) return false;
		playedToday = true;
		score = stored.lastScore;
		outOf = stored.lastOutOf;
		swept = stored.lastSwept;
		idx = -1;
		picked = null;
		timedOut = false;
		phase = 'over';
		return true;
	}

	function beginRun(runMode: 'daily' | 'practice', cards: CountryPlayCard[]) {
		stopClocks();
		mode = runMode;
		deck = cards;
		outOf = cards.length;
		idx = 0;
		score = 0;
		picked = null;
		timedOut = false;
		swept = false;
		copied = false;
		phase = 'playing';
		startTimer();
	}

	function startDaily() {
		if (playedToday || !data.deck.length) return;
		beginRun('daily', data.deck);
	}

	async function startPractice() {
		if (fetching) return;
		fetching = true;
		try {
			const res = await fetch('/api/game-countries');
			if (res.ok) beginRun('practice', (await res.json()) as CountryPlayCard[]);
		} catch {
			// backend unreachable: stay on the current screen
		}
		fetching = false;
	}

	function backToDaily() {
		stopClocks();
		mode = 'daily';
		deck = data.deck;
		if (!restoreDaily()) phase = 'idle';
	}

	function startTimer() {
		deadline = Date.now() + RUN_MS;
		msLeft = RUN_MS;
		timer = setInterval(() => {
			msLeft = Math.max(0, deadline - Date.now());
			if (msLeft <= 0) {
				timedOut = true;
				endRun();
			}
		}, TICK_MS);
	}

	function pick(cc: string) {
		if (phase !== 'playing' || picked !== null || !card) return;
		if (timer) clearInterval(timer);
		timer = null;
		picked = cc;
		if (cc === card.cc) {
			score += 1;
			advancing = setTimeout(advance, ADVANCE_MS);
		} else {
			endRun();
		}
	}

	function advance() {
		advancing = null;
		if (idx + 1 >= deck.length) {
			swept = true;
			endRun();
			return;
		}
		idx += 1;
		picked = null;
		startTimer();
	}

	function endRun() {
		stopClocks();
		phase = 'over';
		if (mode === 'daily') {
			const stored = loadGameState(STORAGE_KEY, EMPTY_STATE);
			// a scoreless run breaks the streak, like giving up does in the clue game
			streak = nextStreak(stored.streak, stored.lastDay, day, score === 0);
			playedToday = true;
			saveGameState(STORAGE_KEY, {
				streak,
				lastDay: day,
				lastScore: score,
				lastOutOf: outOf,
				lastSwept: swept
			});
		}
		logRun();
	}

	function logRun() {
		const payload: CountryRunLog = {
			mode,
			day,
			score,
			outOf,
			failedSemId: swept ? null : (card?.semId ?? null)
		};
		postGameLog('/api/game-countries', payload);
	}

	async function copyShare() {
		copied = await copyShareText(runShareText(day, score, outOf));
	}

	$: card = idx >= 0 && idx < deck.length ? deck[idx] : null;
	$: timerPct = (msLeft / RUN_MS) * 100;
	$: missed = phase === 'over' && !swept && card !== null;
	// A pick locks the buttons; over-state keeps them frozen for the reveal.
	$: locked = picked !== null || phase === 'over';
	$: optionState = (cc: string): string => {
		if (!locked || !card) return '';
		if (cc === card.cc) return 'correct';
		if (cc === picked) return 'wrong';
		return 'faded';
	};
</script>

<svelte:head>
	<title>Name that country — Rankless</title>
	<meta
		name="description"
		content="A daily speed round: universities whose names point everywhere but home. Four countries, {RUN_SECONDS} seconds — how many can you place before you slip?"
	/>
</svelte:head>

<GameShell title="Name that country" streak={mounted ? streak : 0}>
	<p class="intro">
		Real universities whose names point everywhere but home. Pick the country from four options —
		{RUN_SECONDS} seconds each, no lifelines. One wrong pick ends the run; your score is how many you
		place in a row.
	</p>

	{#if !mounted}
		<p>Loading…</p>
	{:else if !data.deck.length}
		<p class="error">No cards in the store yet.</p>
	{:else}
		<div class="mode-row">
			<span class="mode-label">{mode === 'daily' ? `Daily · ${day}` : 'Practice run'}</span>
			{#if mode === 'practice' && phase === 'over'}
				<button class="btn" on:click={backToDaily}>Back to daily</button>
			{/if}
		</div>

		{#if phase === 'idle'}
			<div class="actions">
				<button class="btn primary" on:click={startDaily}>Start today's run</button>
				<button class="btn" on:click={startPractice} disabled={fetching}>Practice run</button>
			</div>
		{:else}
			{#if idx >= 0}
				<div class="progress-row">
					<span>{Math.min(idx + 1, deck.length)}/{deck.length}</span>
					<span class="score-label">score {score}</span>
				</div>
			{/if}

			{#if phase === 'playing'}
				<div class="timer" class:paused={picked !== null}>
					<div
						class="timer-fill"
						class:urgent={msLeft < RUN_MS / 4}
						style="width: {timerPct}%"
					></div>
				</div>
			{/if}

			{#if card}
				<h2 class="uni-name">{card.name}</h2>
				<div class="options">
					{#each card.options as cc, i (i)}
						<button class="option {optionState(cc)}" disabled={locked} on:click={() => pick(cc)}>
							<span class="opt-flag">{ccFlag(cc)}</span>
							{ccName(cc)}
						</button>
					{/each}
				</div>
			{/if}

			{#if phase === 'over'}
				<div class="reveal">
					{#if missed && card}
						<p>
							{timedOut ? '⏱️ Time ran out on' : 'That one was'}
							<strong>{card.name}</strong> — {ccFlag(card.cc)}
							<strong>{ccName(card.cc)}</strong>.
							{card.note}
						</p>
					{:else if swept}
						<p>🏆 You swept the whole deck.</p>
					{/if}
					<p class="verdict">
						<strong>{score}</strong> in a row{mode === 'daily' ? ` on ${day}` : ''}.
					</p>
					<div class="actions">
						{#if mode === 'daily'}
							<button class="btn" on:click={copyShare}>{copied ? 'Copied!' : 'Copy result'}</button>
						{/if}
						<button class="btn primary" on:click={startPractice} disabled={fetching}>
							{mode === 'practice' ? 'Play again' : 'Practice run'}
						</button>
					</div>
				</div>
			{/if}
		{/if}
	{/if}
</GameShell>

<style>
	.progress-row {
		display: flex;
		justify-content: space-between;
		font-weight: 600;
		margin-bottom: 0.5rem;
	}

	.timer {
		height: 6px;
		border: 1px solid var(--border-light);
		margin-bottom: 1rem;
	}

	.timer.paused {
		opacity: 0.4;
	}

	.timer-fill {
		height: 100%;
		background: var(--color-ok);
		transition: width 0.1s linear;
	}

	.timer-fill.urgent {
		background: var(--color-err);
	}

	.uni-name {
		margin: 0.5rem 0 1rem;
	}

	.options {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
		gap: 0.75rem;
		margin-bottom: 1rem;
	}

	.option {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		padding: 0.75rem 1rem;
		border: 1px solid var(--border-light);
		background: transparent;
		color: inherit;
		font-size: var(--text-md, 1rem);
		cursor: pointer;
		text-align: left;
	}

	.option:hover:not(:disabled) {
		border-color: currentColor;
	}

	.option:disabled {
		cursor: default;
	}

	.option.correct {
		border-color: var(--color-ok);
		box-shadow: inset 0 0 0 1px var(--color-ok);
	}

	.option.wrong {
		border-color: var(--color-err);
		box-shadow: inset 0 0 0 1px var(--color-err);
	}

	.option.faded {
		opacity: 0.45;
	}

	.opt-flag {
		font-size: 1.3em;
	}
</style>
