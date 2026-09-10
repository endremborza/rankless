<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { fly } from 'svelte/transition';

	import type { PageData } from './$types';
	import GameFrame from '$lib/components/GameFrame.svelte';
	import GameMap from '$lib/components/GameMap.svelte';
	import GameStats from '$lib/components/GameStats.svelte';
	import type {
		DailyRun,
		DayStanding,
		PlayCard,
		PlayOption,
		RunLog,
		RunResult
	} from '$lib/types/game-geo';
	import {
		ccFlag,
		copyShareText,
		loadGameState,
		nextStreak,
		postGameLog,
		saveGameState
	} from '$lib/utils/game';
	import {
		BRAND,
		DAILY_SIZE,
		LIVES,
		QUESTIONS,
		RUN_SECONDS,
		answerLabel,
		formatPoints,
		gridLine,
		lifelineKeep,
		livesLeft,
		optionLabel,
		points,
		promptLabel,
		runShareText,
		verdictLine
	} from '$lib/utils/game-geo';

	export let data: PageData;

	// Decoupled from the route name: changing the key resets every player's streak.
	const STORAGE_KEY = 'rankless-game-geo';
	const RUN_MS = RUN_SECONDS * 1000;
	const TICK_MS = 100;
	// Daily history kept in the browser; oldest runs fall off.
	const MAX_RUNS = 400;

	type StoredState = {
		streak: number;
		lastStanding: DayStanding | null;
		runs: DailyRun[];
		survivalBest: number;
	};
	const EMPTY_STATE: StoredState = { streak: 0, lastStanding: null, runs: [], survivalBest: 0 };

	let mounted = false;
	let mode: 'daily' | 'survival' = 'daily';
	// `reveal` holds the answered card on screen — hit or miss — with the clock
	// stopped and its note up until the player continues: into the next card,
	// or (when that answer ended the run, already booked) into the result screen.
	let phase: 'idle' | 'playing' | 'reveal' | 'over' = 'idle';
	let runDone = false;
	let deck: PlayCard[] = [];
	let idx = -1;
	// Cards answered so far (hit, miss or timeout).
	let settled = 0;
	let picked: string | null = null;
	let timedOut = false;
	// The 50:50 on the current card: the two option keys it leaves, if used.
	let kept: string[] | null = null;
	let score = 0;
	let outOf = 0;
	let missed: string[] = [];
	let lifelined: string[] = [];
	let streak = 0;
	let runs: DailyRun[] = [];
	let survivalBest = 0;
	let standing: DayStanding | null = null;
	let playedToday = false;
	let copied = false;
	let fetching = false;
	let showStats = false;
	let msLeft = RUN_MS;
	let deadline = 0;
	let timer: ReturnType<typeof setInterval> | null = null;

	const day = data.day;

	onMount(() => {
		restoreDaily();
		mounted = true;
	});

	onDestroy(stopClock);

	function readState(): StoredState {
		return { ...EMPTY_STATE, ...loadGameState(STORAGE_KEY, EMPTY_STATE) };
	}

	function persist() {
		saveGameState(STORAGE_KEY, {
			streak,
			lastStanding: standing,
			runs,
			survivalBest
		} satisfies StoredState);
	}

	function stopClock() {
		if (timer) clearInterval(timer);
		timer = null;
	}

	// Restores the finished daily round from storage; false when today is
	// still unplayed (the caller decides what phase that means). The daily deck
	// is the same all day, so the stored ids resolve against it.
	function restoreDaily(): boolean {
		const stored = readState();
		streak = stored.streak;
		runs = stored.runs;
		survivalBest = stored.survivalBest;
		const last = runs[runs.length - 1];
		if (last?.day !== day) return false;
		playedToday = true;
		deck = data.deck;
		score = last.score;
		outOf = last.outOf;
		missed = last.missedSemIds;
		lifelined = last.lifelinedSemIds;
		standing = stored.lastStanding;
		settled = outOf;
		idx = -1;
		picked = null;
		timedOut = false;
		kept = null;
		runDone = false;
		phase = 'over';
		return true;
	}

	function beginRun(runMode: 'daily' | 'survival', cards: PlayCard[]) {
		stopClock();
		mode = runMode;
		deck = cards;
		outOf = cards.length;
		idx = 0;
		settled = 0;
		score = 0;
		missed = [];
		lifelined = [];
		if (runMode === 'daily') standing = null;
		copied = false;
		showStats = false;
		runDone = false;
		startCard();
	}

	function startDaily() {
		if (playedToday || !data.deck.length) return;
		beginRun('daily', data.deck);
	}

	async function startSurvival() {
		if (fetching) return;
		fetching = true;
		try {
			const res = await fetch('/api/game-geo');
			if (res.ok) beginRun('survival', (await res.json()) as PlayCard[]);
		} catch {
			// backend unreachable: stay on the current screen
		}
		fetching = false;
	}

	function backToDaily() {
		stopClock();
		mode = 'daily';
		deck = data.deck;
		if (!restoreDaily()) phase = 'idle';
	}

	function startCard() {
		picked = null;
		timedOut = false;
		kept = null;
		phase = 'playing';
		startClock();
	}

	function startClock() {
		stopClock();
		deadline = Date.now() + RUN_MS;
		msLeft = RUN_MS;
		timer = setInterval(() => {
			msLeft = Math.max(0, deadline - Date.now());
			if (msLeft <= 0) {
				timedOut = true;
				settle(false);
			}
		}, TICK_MS);
	}

	function pick(key: string) {
		if (phase !== 'playing' || picked !== null || !card) return;
		picked = key;
		settle(key === card.answer);
	}

	// Daily only: two options fall away for half the card's worth, and the
	// clock starts over.
	function useLifeline() {
		if (mode !== 'daily' || phase !== 'playing' || kept || !card) return;
		kept = lifelineKeep(card, day);
		lifelined = [...lifelined, card.semId];
		startClock();
	}

	// Every answer holds its reveal. The daily runs every card; survival ends on
	// the last life. A run-ending answer books the run right away, so the
	// reveal leads to the result instead of the next card.
	function settle(hit: boolean) {
		if (!card) return;
		stopClock();
		settled += 1;
		if (hit) score += points(true, kept !== null);
		else missed = [...missed, card.semId];
		runDone = idx + 1 >= deck.length || (mode === 'survival' && livesLeft(missed.length) === 0);
		if (runDone) finishRun();
		phase = 'reveal';
	}

	function continueFromReveal() {
		if (runDone) {
			phase = 'over';
			return;
		}
		idx += 1;
		startCard();
	}

	// Books the run (streak, history, best, log) without deciding what is on screen.
	function finishRun() {
		stopClock();
		const stored = readState();
		if (mode === 'daily') {
			const last = stored.runs[stored.runs.length - 1];
			// a scoreless run breaks the streak
			streak = nextStreak(stored.streak, last?.day ?? '', day, score === 0);
			playedToday = true;
			runs = [
				...stored.runs,
				{ day, score, outOf, missedSemIds: missed, lifelinedSemIds: lifelined }
			].slice(-MAX_RUNS);
		} else {
			survivalBest = Math.max(stored.survivalBest, settled - missed.length);
		}
		persist();
		logRun();
	}

	async function logRun() {
		const payload: RunLog = {
			mode,
			day,
			score,
			outOf,
			missedSemIds: missed,
			lifelinedSemIds: lifelined
		};
		const res = await postGameLog<RunResult>('/api/game-geo', payload);
		if (mode !== 'daily' || !res?.standing) return;
		standing = res.standing;
		persist();
	}

	async function copyShare() {
		copied = await copyShareText(shareText);
	}

	function nextDailyText(): string {
		const mins = Math.max(0, Math.round((Date.parse(day) + 24 * 3600 * 1000 - Date.now()) / 60000));
		return `Next daily in ${Math.floor(mins / 60)}h ${mins % 60}m`;
	}

	$: card = idx >= 0 && idx < deck.length ? deck[idx] : null;
	$: question = card ? QUESTIONS[card.kind] : null;
	$: timerPct = (msLeft / RUN_MS) * 100;
	$: placed = settled - missed.length;
	$: hearts = '♥'.repeat(livesLeft(missed.length)) + '♡'.repeat(Math.min(missed.length, LIVES));
	// A pick locks the buttons; reveal/over keep them frozen for the reveal.
	$: locked = picked !== null || phase === 'reveal' || phase === 'over';
	$: hit = card !== null && picked === card.answer;
	$: optionState = (o: PlayOption): string => {
		if (!card) return '';
		if (locked) return o.key === card.answer ? 'correct' : o.key === picked ? 'wrong' : 'faded';
		return kept && !kept.includes(o.key) ? 'faded' : '';
	};
	$: promptText = card ? promptLabel(card) : '';
	$: promptClass = promptText.length > 42 ? 'sm' : promptText.length > 26 ? 'md' : 'lg';
	$: headerLabel = mode === 'survival' ? 'Survival' : `Daily · ${day}`;
	$: missedCards = missed
		.map((id) => deck.find((c) => c.semId === id))
		.filter((c): c is PlayCard => c !== undefined);
	$: grid = gridLine(
		deck.map((c) => c.semId),
		missed,
		lifelined
	);
	$: shareText = runShareText(day, score, outOf, grid);
	$: nextIn = phase === 'over' && mode === 'daily' ? nextDailyText() : '';
	$: mapPoints =
		card?.kind === 'nearest-card'
			? card.options.map((o) => ({
					lat: o.lat,
					lon: o.lon,
					label: o.label,
					answer: o.key === card?.answer
				}))
			: [];
</script>

<svelte:head>
	<title>{BRAND} — Rankless</title>
	<meta
		name="description"
		content="Institution names can point far from home. {DAILY_SIZE} cards a day: where is it actually, which city, which is closest, which one is not here."
	/>
</svelte:head>

<GameFrame
	label={headerLabel}
	streak={mounted ? streak : 0}
	longStreak={phase === 'idle' || phase === 'over'}
>
	{#if !mounted}
		<div class="center-fill">Loading…</div>
	{:else if !data.deck.length}
		<div class="center-fill error">No cards in the store yet.</div>
	{:else if phase === 'idle'}
		<div class="start">
			<div class="title-block">
				<h1 class="title"><span>Campus</span><span>Quest</span></h1>
				<div class="ramp-bar title-bar"></div>
			</div>
			<p class="tagline">
				An institution's name can point far from home. Where is it actually — and which city, which
				is closest, which one is not here?
			</p>
			<div class="stat-tiles">
				<div class="stat t0">
					<span class="num">{DAILY_SIZE}</span><span class="lbl">Cards</span>
				</div>
				<div class="stat t1">
					<span class="num">{RUN_SECONDS}s</span><span class="lbl">Each</span>
				</div>
				<div class="stat t3"><span class="num">50:50</span><span class="lbl">Lifeline</span></div>
			</div>
		</div>
		<div class="bottom-stack">
			<button class="g-btn primary" on:click={startDaily}>Play today's run</button>
			<button class="g-btn ghost" on:click={startSurvival} disabled={fetching}>Survival</button>
			<div class="foot-note">Same deck for everyone · resets 00:00 UTC</div>
		</div>
	{:else if (phase === 'playing' || phase === 'reveal') && card && question}
		<div class="progress-row">
			{#if mode === 'daily'}
				<span class="count">{idx + 1}<span class="of">/{deck.length}</span></span>
				<span class="count">{formatPoints(score)}<span class="of"> pts</span></span>
			{:else}
				<span class="count">{placed}<span class="of"> placed</span></span>
				<span class="hearts lives" aria-label="{livesLeft(missed.length)} of {LIVES} lives left"
					>{hearts}</span
				>
			{/if}
		</div>
		<div class="timer" class:paused={locked}>
			<div
				class="timer-fill ramp-bar"
				class:urgent={msLeft < RUN_MS / 4}
				style="width: {timerPct}%"
			></div>
		</div>
		<div class="stage">
			<span class="ask">{question.above}</span>
			<h2 class="prompt {promptClass}">{promptText}</h2>
			<span class="ask">{question.below}</span>
			{#if card.badges.length}
				<div class="badges">
					{#each card.badges as b, i (i)}
						<span class="badge">{b.label} · {b.subfield}</span>
					{/each}
				</div>
			{/if}
		</div>
		<div class="options" class:names={question.options !== 'country'}>
			{#each card.options as o, i (i)}
				<button
					class="option t{i} {optionState(o)}"
					disabled={locked || (kept !== null && !kept.includes(o.key))}
					on:click={() => pick(o.key)}
				>
					{#if question.options === 'country'}
						<span class="opt-flag">{ccFlag(o.key)}</span>
					{/if}
					<span class="opt-name">{optionLabel(card.kind, o)}</span>
					{#if locked && o.km !== undefined}
						<span class="opt-km">{o.km} km</span>
					{/if}
				</button>
			{/each}
		</div>
		{#if mode === 'daily'}
			<button class="lifeline" on:click={useLifeline} disabled={locked || kept !== null}>
				{kept ? '50:50 used · ½ point' : '50:50 · half a point, fresh clock'}
			</button>
		{/if}
		{#if phase === 'reveal'}
			<div class="sheet reveal" in:fly={{ y: 220, duration: 200 }}>
				<span class="verdict-tag" class:ok={hit}>
					{hit ? (kept ? '✓ Correct · ½' : '✓ Correct') : timedOut ? '⏱ Time ran out' : '✗ Wrong'}
				</span>
				<div class="sheet-head">
					{#if question.options === 'country'}
						<span class="sheet-flag">{ccFlag(card.answer)}</span>
					{/if}
					<div class="sheet-names">
						<span class="sheet-answer">{answerLabel(card)}</span>
						<span class="sheet-sub">{promptText}</span>
					</div>
				</div>
				{#if card.kind === 'nearest-card'}
					<GameMap anchor={card} points={mapPoints} />
				{/if}
				<p class="note">{card.note}</p>
				<button class="g-btn primary" on:click={continueFromReveal}>
					{runDone ? 'See result' : 'Next'}
				</button>
			</div>
		{/if}
	{:else}
		<div class="results">
			<span class="ask">{mode === 'daily' ? `Today's run · ${day}` : 'Survival'}</span>
			{#if mode === 'daily'}
				<p class="verdict">{verdictLine(score, outOf)}</p>
				<div class="score-row">
					<span class="score-big">{formatPoints(score)}</span><span class="score-word"
						>/{outOf}</span
					>
				</div>
				<span class="grid">{grid}</span>
			{:else}
				<p class="verdict">{placed === outOf ? 'Cleared the whole pack' : 'Run over'}</p>
				<div class="score-row">
					<span class="score-big">{placed}</span><span class="score-word">placed</span>
				</div>
				<span class="hearts big-hearts">{hearts}</span>
				<span class="standing">Best {survivalBest}</span>
			{/if}
			{#if missedCards.length}
				<ul class="misses">
					{#each missedCards as c, i (i)}
						<li>
							<span class="miss-name">{promptLabel(c)}</span>
							<span class="miss-where">{answerLabel(c)}</span>
						</li>
					{/each}
				</ul>
			{/if}
			{#if mode === 'daily'}
				<div class="ramp-bar divider"></div>
				{#if standing}
					<span class="standing">#{standing.rank} of {standing.players} today</span>
				{/if}
				<button class="stats-line" on:click={() => (showStats = true)}>
					Played {runs.length} · Best {formatPoints(Math.max(0, ...runs.map((r) => r.score)))} · Stats
					›
				</button>
			{/if}
		</div>
		<div class="bottom-stack">
			{#if mode === 'daily'}
				<button class="g-btn primary" on:click={copyShare}
					>{copied ? 'Copied!' : 'Share result'}</button
				>
				<div class="share-preview">{shareText.split('\n')[1]}</div>
				<button class="g-btn ghost" on:click={startSurvival} disabled={fetching}>Survival</button>
				{#if nextIn}<div class="foot-note">{nextIn}</div>{/if}
			{:else}
				<button class="g-btn primary" on:click={startSurvival} disabled={fetching}
					>Play again</button
				>
				<button class="g-btn ghost" on:click={backToDaily}>Back to daily</button>
			{/if}
		</div>
		{#if showStats}
			<div class="sheet" in:fly={{ y: 220, duration: 200 }}>
				<GameStats {runs} {streak} />
				<button class="g-btn ghost" on:click={() => (showStats = false)}>Close</button>
			</div>
		{/if}
	{/if}
</GameFrame>

<style>
	.center-fill {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.error {
		color: var(--color-err);
	}

	.start {
		--tile-gap: 10px;
		flex: 1;
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 26px;
		min-height: 0;
	}

	.title-block {
		display: flex;
		flex-direction: column;
	}

	.title {
		display: flex;
		flex-direction: column;
		gap: 4px;
		margin: 0;
		font-size: clamp(44px, 15vw, 62px);
		line-height: 1;
		letter-spacing: -2px;
		text-transform: uppercase;
	}

	/* The bar's right edge lands exactly on the middle stat tile's right edge. */
	.title-bar {
		height: 10px;
		width: calc((100% - 2 * var(--tile-gap)) * 2 / 3 + var(--tile-gap));
		margin-top: 14px;
	}

	.tagline {
		margin: 0;
		font-size: var(--text-md);
		line-height: 1.5;
		text-wrap: pretty;
	}

	.stat-tiles {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: var(--tile-gap);
	}

	.stat {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 4px;
		padding: 14px 6px;
		border: 1px solid;
	}

	.stat .num {
		font-size: 26px;
		font-weight: 700;
		line-height: 1;
		white-space: nowrap;
	}

	.stat .lbl {
		font-size: var(--text-xs);
		letter-spacing: 2px;
		text-transform: uppercase;
		color: var(--game-sub);
	}

	.bottom-stack {
		display: flex;
		flex-direction: column;
		gap: 12px;
		flex-shrink: 0;
	}

	.foot-note {
		font-size: var(--text-xs);
		color: var(--game-sub);
		text-align: center;
	}

	.progress-row {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		flex-shrink: 0;
	}

	.count {
		font-size: 17px;
		font-weight: 700;
	}

	.count .of {
		color: var(--game-sub);
		font-weight: 400;
	}

	.lives {
		font-size: 19px;
	}

	.timer {
		height: 10px;
		border: 1px solid var(--border-light);
		flex-shrink: 0;
	}

	.timer.paused {
		opacity: 0.4;
	}

	.timer-fill {
		height: 100%;
		transition: width 0.1s linear;
	}

	.timer-fill.urgent {
		background: var(--color-err);
	}

	/* The bottom bias centers the question optically, not geometrically. */
	.stage {
		flex: 1;
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
		gap: 14px;
		text-align: center;
		padding: 0 6px clamp(12px, 4svh, 36px);
		min-height: 0;
	}

	.ask {
		font-size: var(--text-sm);
		letter-spacing: 3px;
		text-transform: uppercase;
		color: var(--game-sub);
	}

	.prompt {
		margin: 0;
		font-weight: 700;
		line-height: 1.15;
		text-wrap: balance;
	}

	.prompt.lg {
		font-size: min(34px, 8.5vw);
	}

	.prompt.md {
		font-size: min(27px, 7vw);
	}

	.prompt.sm {
		font-size: min(21px, 5.5vw);
	}

	/* Real standing, no country leak: the card's top-percentile subfield badges. */
	.badges {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: 8px;
	}

	.badge {
		border: 1px solid var(--border-light);
		padding: 4px 10px;
		font-size: 12px;
		color: var(--game-sub);
		white-space: nowrap;
	}

	.options {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 12px;
		flex-shrink: 0;
	}

	.option {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 8px;
		height: clamp(112px, 17svh, 150px);
		border: 1px solid;
		background: none;
		font-family: inherit;
		color: var(--color-text);
		cursor: pointer;
		padding: 8px;
	}

	.option:disabled {
		cursor: default;
	}

	.opt-flag {
		font-size: 42px;
		line-height: 1;
	}

	.opt-name {
		font-size: 13px;
		font-weight: 700;
		letter-spacing: 1px;
		text-transform: uppercase;
	}

	/* Name rows are several times the reading of a flag row: a hard two-line cap. */
	.options.names .option {
		height: clamp(84px, 12svh, 110px);
	}

	.options.names .opt-name {
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		overflow: hidden;
		letter-spacing: 0.5px;
		text-transform: none;
		font-size: 14px;
		line-height: 1.3;
	}

	.opt-km {
		position: absolute;
		right: 8px;
		bottom: 6px;
		font-size: var(--text-xs);
		color: var(--game-sub);
	}

	.lifeline {
		border: 1px dashed var(--border-light);
		background: none;
		padding: 8px;
		font-family: inherit;
		font-size: var(--text-sm);
		color: var(--accent-text);
		cursor: pointer;
		flex-shrink: 0;
	}

	.lifeline:disabled {
		cursor: default;
		color: var(--game-sub);
	}

	/* Positional tile tints off the palette ramp — decorative, never meaningful. */
	.t0 {
		background: rgba(var(--color-range-10), 0.14);
		border-color: rgba(var(--color-range-10), 0.55);
	}

	.t1 {
		background: rgba(var(--color-range-50), 0.1);
		border-color: rgba(var(--color-range-50), 0.45);
	}

	.t2 {
		background: rgba(var(--color-range-80), 0.14);
		border-color: rgba(var(--color-range-80), 0.55);
	}

	.t3 {
		background: rgba(var(--color-range-100), 0.2);
		border-color: rgba(var(--color-range-85), 0.6);
	}

	@media (prefers-color-scheme: dark) {
		.t0 {
			background: rgba(var(--color-range-10), 0.22);
			border-color: rgba(var(--color-range-10), 0.65);
		}

		.t1 {
			background: rgba(var(--color-range-50), 0.28);
			border-color: rgba(var(--color-range-110), 0.6);
		}

		.t2 {
			background: rgba(var(--color-range-80), 0.24);
			border-color: rgba(var(--color-range-80), 0.7);
		}

		.t3 {
			background: rgba(var(--color-range-100), 0.18);
			border-color: rgba(var(--color-range-100), 0.55);
		}
	}

	/* Verdict states override the tints; green/red carry meaning, the tints never do. */
	.option.correct {
		border-color: var(--color-ok);
		box-shadow: inset 0 0 0 1px var(--color-ok);
		background: color-mix(in srgb, var(--color-ok) 10%, transparent);
	}

	.option.correct .opt-name {
		color: var(--color-ok);
	}

	.option.wrong {
		border-color: var(--color-err);
		box-shadow: inset 0 0 0 1px var(--color-err);
		background: color-mix(in srgb, var(--color-err) 8%, transparent);
	}

	.option.wrong .opt-name {
		color: var(--color-err);
	}

	.option.faded {
		opacity: 0.3;
	}

	.verdict-tag {
		font-size: var(--text-sm);
		font-weight: 700;
		letter-spacing: 2px;
		text-transform: uppercase;
		color: var(--color-err);
	}

	.verdict-tag.ok {
		color: var(--color-ok);
	}

	.sheet-head {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.sheet-flag {
		font-size: 44px;
		line-height: 1;
	}

	.sheet-names {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.sheet-answer {
		font-size: 21px;
		font-weight: 700;
		letter-spacing: 1px;
		text-transform: uppercase;
		text-wrap: balance;
	}

	.sheet-sub {
		font-size: var(--text-sm);
		color: var(--game-sub);
	}

	.note {
		margin: 0;
		font-size: 13px;
		line-height: 1.55;
		text-wrap: pretty;
	}

	.results {
		flex: 1;
		display: flex;
		flex-direction: column;
		justify-content: center;
		align-items: center;
		gap: 12px;
		text-align: center;
		min-height: 0;
	}

	.verdict {
		margin: 0;
		font-size: var(--text-md);
		font-weight: 700;
		text-wrap: balance;
	}

	.score-row {
		display: flex;
		align-items: baseline;
		gap: 10px;
	}

	.score-big {
		font-size: clamp(64px, 24vw, 96px);
		line-height: 1;
		font-weight: 700;
	}

	.score-word {
		font-size: 20px;
		font-weight: 700;
	}

	.grid {
		font-size: 22px;
		letter-spacing: 2px;
	}

	.big-hearts {
		font-size: 24px;
		letter-spacing: 6px;
	}

	.misses {
		list-style: none;
		margin: 0;
		padding: 0;
		width: 100%;
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: 13px;
	}

	.misses li {
		display: flex;
		justify-content: space-between;
		gap: 10px;
		text-align: left;
	}

	.miss-name {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		color: var(--color-err);
	}

	.miss-where {
		flex-shrink: 0;
		max-width: 55%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		font-weight: 700;
	}

	.divider {
		height: 10px;
		width: 62%;
		max-width: 240px;
	}

	.standing {
		font-weight: 700;
	}

	.stats-line {
		border: none;
		background: none;
		padding: 4px 0;
		font-family: inherit;
		font-size: var(--text-sm);
		color: var(--accent-text);
		cursor: pointer;
	}

	.share-preview {
		font-size: var(--text-xs);
		color: var(--game-sub);
		text-align: center;
		overflow-wrap: anywhere;
	}
</style>
