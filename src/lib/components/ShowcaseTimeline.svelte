<script lang="ts">
	import type { ShowcaseTimeline } from '$lib/types/showcase';
	import { makeTicks } from '$lib/utils/author-timeline';

	export let data: ShowcaseTimeline;

	$: domain = { lo: data.yearLo, hi: data.yearHi, span: Math.max(1, data.yearHi - data.yearLo) };
	$: ticks = makeTicks(domain, 5);
	// Closes over reactive `domain`, so it must stay a `$:`-reassigned function (legacy mode).
	$: pctOf = (year: number) => ((year - domain.lo) / domain.span) * 100;

	const markSize = (n: number) => Math.min(13, 6 + (n - 1) * 2.5);
</script>

<div class="tl">
	<div class="tl-axis tl-grid">
		<div></div>
		<div class="tl-axis-track">
			{#each ticks as t (t)}
				<span class="tl-tick" style="left:{pctOf(t)}%">{t}</span>
			{/each}
		</div>
	</div>

	<div class="tl-body">
		<div class="tl-gridlines" aria-hidden="true">
			{#each ticks as t (t)}
				<span class="tl-grid-line" style="left:{pctOf(t)}%"></span>
			{/each}
		</div>

		{#each data.rows as row (row.name)}
			<div class="tl-row tl-grid">
				<div class="tl-name" title={row.name}>{row.name}</div>
				<div class="tl-track">
					<div
						class="tl-bar"
						style="left:{pctOf(row.firstYear)}%; width:{pctOf(row.lastYear) -
							pctOf(row.firstYear)}%"
					></div>
					{#each row.marks as m (m.year)}
						<span
							class="tl-mark"
							class:hit={m.hit}
							style="left:{pctOf(m.year)}%; width:{markSize(m.n)}px; height:{markSize(m.n)}px"
							title="{m.n} shared paper{m.n === 1 ? '' : 's'} in {m.year}{m.hit
								? ' · includes a hit paper'
								: ''}"
						></span>
					{/each}
				</div>
			</div>
		{/each}
	</div>

	<div class="tl-legend">
		<span class="tl-lg"><i class="tl-sw tl-sw-mark"></i>Shared papers</span>
		<span class="tl-lg"><i class="tl-sw tl-sw-hit"></i>Includes a hit paper</span>
		<span class="tl-lg"><i class="tl-sw tl-sw-bar"></i>Collaboration span</span>
	</div>
</div>

<style>
	.tl {
		--accent: var(--color-theme-blue, #3b82f6);
		--tl-mark: rgb(var(--color-range-35));
		--tl-bar: rgba(var(--color-range-40), 0.45);
		--hair: rgba(var(--color-range-15), 0.12);
		--name-w: clamp(76px, 30%, 150px);
		display: flex;
		flex-direction: column;
		gap: 10px;
	}

	@media (prefers-color-scheme: dark) {
		.tl {
			--tl-mark: rgb(var(--color-range-80));
			--tl-bar: rgba(var(--color-range-90), 0.3);
		}
	}

	.tl-grid {
		display: grid;
		grid-template-columns: var(--name-w) 1fr;
		align-items: center;
		column-gap: 10px;
	}

	.tl-axis-track {
		position: relative;
		height: 14px;
	}

	.tl-tick {
		position: absolute;
		bottom: 0;
		transform: translateX(-50%);
		font-size: var(--text-xs);
		font-variant-numeric: tabular-nums;
		opacity: 0.5;
		white-space: nowrap;
	}

	.tl-body {
		position: relative;
	}

	.tl-gridlines {
		position: absolute;
		left: var(--name-w);
		right: 0;
		top: 0;
		bottom: 0;
		margin-left: 10px;
		pointer-events: none;
	}

	.tl-grid-line {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 1px;
		transform: translateX(-50%);
		background: var(--hair);
	}

	.tl-row {
		min-height: 26px;
		border-bottom: 1px solid var(--hair);
	}

	.tl-name {
		font-size: var(--text-xs);
		line-height: 1.2;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		text-align: right;
		opacity: 0.85;
	}

	.tl-track {
		position: relative;
		height: 100%;
		min-height: 24px;
	}

	.tl-bar {
		position: absolute;
		top: 50%;
		height: 3px;
		min-width: 2px;
		transform: translateY(-50%);
		border-radius: 2px;
		background: var(--tl-bar);
	}

	.tl-mark {
		position: absolute;
		top: 50%;
		transform: translate(-50%, -50%);
		border-radius: 50%;
		background: var(--tl-mark);
	}

	.tl-mark.hit {
		background: var(--accent);
		box-shadow: 0 0 0 2px rgba(var(--color-range-40), 0.25);
	}

	.tl-legend {
		display: flex;
		flex-wrap: wrap;
		gap: 6px 18px;
		font-size: var(--text-xs);
		opacity: 0.85;
	}

	.tl-lg {
		display: inline-flex;
		align-items: center;
		gap: 7px;
	}

	.tl-sw {
		flex-shrink: 0;
	}

	.tl-sw-mark,
	.tl-sw-hit {
		width: 11px;
		height: 11px;
		border-radius: 50%;
		background: var(--tl-mark);
	}

	.tl-sw-hit {
		background: var(--accent);
	}

	.tl-sw-bar {
		width: 20px;
		height: 3px;
		border-radius: 2px;
		background: var(--tl-bar);
	}
</style>
