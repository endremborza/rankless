<!-- Personal stats for the country game's daily runs: the browser's own
	history (localStorage), nothing server-side. Rendered inside GameFrame, so
	the .ramp-bar chrome is in scope. -->
<script lang="ts">
	import type { DailyRun } from '$lib/types/game-countries';
	import { HIST_BUCKETS, runStats } from '$lib/utils/game-countries';

	export let runs: DailyRun[];
	export let streak = 0;

	$: stats = runStats(runs);
	$: peak = Math.max(1, ...stats.hist);
</script>

<div class="stats">
	<span class="heading">Your daily runs</span>
	<div class="tiles">
		<div class="tile"><span class="num">{stats.played}</span><span class="lbl">Played</span></div>
		<div class="tile"><span class="num">{stats.best}</span><span class="lbl">Best</span></div>
		<div class="tile"><span class="num">{stats.avg}</span><span class="lbl">Average</span></div>
		<div class="tile"><span class="num">{streak}</span><span class="lbl">Streak</span></div>
	</div>
	<div class="hist" aria-label="Runs by score">
		{#each stats.hist as n, i (i)}
			<div class="row">
				<span class="range">{HIST_BUCKETS[i][0]}–{HIST_BUCKETS[i][1]}</span>
				<div class="track"><div class="bar ramp-bar" style="width: {(n / peak) * 100}%"></div></div>
				<span class="n">{n}</span>
			</div>
		{/each}
	</div>
</div>

<style>
	.stats {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.heading {
		font-size: var(--text-sm);
		letter-spacing: 3px;
		text-transform: uppercase;
		color: var(--game-sub);
	}

	.tiles {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 8px;
	}

	.tile {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 3px;
		padding: 10px 4px;
		border: 1px solid var(--border-light);
	}

	.num {
		font-size: 24px;
		font-weight: 700;
		line-height: 1;
	}

	.lbl {
		font-size: var(--text-xs);
		letter-spacing: 1.5px;
		text-transform: uppercase;
		color: var(--game-sub);
	}

	.hist {
		display: flex;
		flex-direction: column;
		gap: 5px;
	}

	.row {
		display: grid;
		grid-template-columns: 44px 1fr 24px;
		align-items: center;
		gap: 8px;
		font-size: var(--text-xs);
	}

	.range {
		color: var(--game-sub);
		text-align: right;
	}

	.track {
		height: 12px;
	}

	.bar {
		height: 100%;
		min-width: 2px;
	}

	.n {
		font-weight: 700;
	}
</style>
