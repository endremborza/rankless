<script lang="ts" context="module">
	export type Bar = {
		height: number; // 0..100, % of plot height
		colorVar: string; // a --color-range-* (or --sel-c) var name
		axisLabel?: string; // label under the bar
		primary?: string; // bold label above the bar top
		secondary?: string; // muted label above the bar top
		tip?: string; // tooltip text on hover
		ghost?: boolean; // faded reference variant (same color, lower opacity)
	};
	export type Tick = {
		pct: number; // 0..100, % of plot height
		label: string; // y-axis label
		ref?: boolean; // the 1× reference line, drawn over the bars
	};
</script>

<script lang="ts">
	import { tick } from 'svelte';

	export let bars: Bar[];
	export let plotHeight = 200;
	export let gap = 14; // gap between bars (between groups when grouped)
	export let groupSize = 1; // bars per visual group; pairs sit tight, groups stay `gap` apart
	export let groupGap = 2; // gap within a group
	export let ticks: Tick[] = []; // gridlines + y-axis labels; empty = no axis
	export let showLabels = true; // render the left label gutter (gridlines always show)
	export let refColorVar = '--hero-c'; // color of the 1× reference line + its label
	export let refLabel = ''; // name pill sitting on the 1× reference line

	$: groups =
		groupSize <= 1
			? bars.map((b) => [b])
			: Array.from({ length: Math.ceil(bars.length / groupSize) }, (_, g) =>
					bars.slice(g * groupSize, g * groupSize + groupSize)
				);
	$: refTick = ticks.find((t) => t.ref);

	let tipText: string | null = null;
	let tipX = 0;
	let tipY = 0;
	let tipBelow = false;
	let tipEl: HTMLDivElement;
	// Anchor the tip centered over the bar, then (after it renders) clamp it into the viewport: nudge
	// horizontally so neither edge spills off-screen, and flip below the bar when there's no room above.
	async function showTip(text: string, e: MouseEvent) {
		const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
		const cx = r.left + r.width / 2;
		tipText = text;
		tipX = cx;
		tipY = r.top;
		tipBelow = false;
		await tick();
		if (!tipEl) return;
		const margin = 8;
		const w = tipEl.offsetWidth;
		const h = tipEl.offsetHeight;
		tipX = Math.min(Math.max(cx, w / 2 + margin), window.innerWidth - w / 2 - margin);
		tipBelow = r.top - h - margin < 0;
		tipY = tipBelow ? r.bottom : r.top;
	}
	function hideTip() {
		tipText = null;
	}
</script>

<div class="chart">
	{#if ticks.length}
		<!-- gutter stays even without labels so side-by-side charts keep equal plot widths -->
		<div class="y-axis" style="height: {plotHeight}px;">
			{#if showLabels}
				{#each ticks as t}
					{#if !(t.ref && refLabel)}
						<span
							class="y-label"
							class:ref={t.ref}
							style="bottom: {t.pct.toFixed(2)}%; {t.ref
								? `color: rgba(var(${refColorVar}), 0.95);`
								: ''}">{t.label}</span
						>
					{/if}
				{/each}
			{/if}
		</div>
	{/if}
	<div class="bars" style="height: {plotHeight}px; gap: {gap}px;">
		{#each ticks as t}
			<div
				class="gridline"
				class:ref={t.ref}
				style="bottom: {t.pct.toFixed(2)}%; {t.ref
					? `border-top-color: rgba(var(${refColorVar}), 0.6);`
					: ''}"
			></div>
		{/each}
		{#if refLabel && refTick}
			<span
				class="ref-pill"
				style="bottom: {refTick.pct.toFixed(2)}%; color: rgba(var({refColorVar}), 1);"
				>{refLabel}</span
			>
		{/if}
		{#each groups as group}
			<div class="bar-group" style="gap: {groupGap}px;">
				{#each group as bar}
					<div
						class="bar-slot"
						role="presentation"
						on:mouseenter={bar.tip ? (e) => showTip(bar.tip ?? '', e) : undefined}
						on:mouseleave={bar.tip ? hideTip : undefined}
					>
						{#if bar.primary || bar.secondary}
							<span class="bar-value" style="bottom: {bar.height.toFixed(2)}%;">
								{#if bar.primary}<span class="bv-primary">{bar.primary}</span>{/if}
								{#if bar.secondary}<span class="bv-secondary">{bar.secondary}</span>{/if}
							</span>
						{/if}
						<div
							class="bar"
							class:ghost={bar.ghost}
							style="height: {bar.height.toFixed(2)}%; --sf-c: var({bar.colorVar});"
						></div>
						{#if bar.axisLabel}
							<span class="bar-label">{bar.axisLabel}</span>
						{/if}
					</div>
				{/each}
			</div>
		{/each}
	</div>
</div>

{#if tipText !== null}
	<div
		class="peer-tooltip"
		class:below={tipBelow}
		bind:this={tipEl}
		style="left:{tipX}px; top:{tipY}px;"
	>
		{tipText}
	</div>
{/if}

<style>
	.chart {
		display: flex;
		align-items: flex-end;
		gap: 6px;
	}

	.y-axis {
		position: relative;
		width: 26px;
		flex-shrink: 0;
	}

	.y-label {
		position: absolute;
		right: 0;
		transform: translateY(50%);
		font-size: var(--text-xs);
		font-variant-numeric: tabular-nums;
		line-height: 1;
		opacity: 0.5;
		white-space: nowrap;
	}

	.y-label.ref {
		opacity: 1;
		font-weight: 600;
	}

	.bars {
		flex: 1;
		display: flex;
		align-items: end;
		position: relative;
	}

	.bar-group {
		flex: 1;
		min-width: 0;
		height: 100%;
		display: flex;
		align-items: end;
	}

	.gridline {
		position: absolute;
		left: 0;
		right: 0;
		height: 0;
		border-top: 1px solid rgba(var(--color-range-30), 0.14);
		pointer-events: none;
		z-index: 0;
	}

	.gridline.ref {
		border-top-style: dashed;
		z-index: 2;
	}

	.bar-slot {
		flex: 1;
		min-width: 0;
		position: relative;
		z-index: 1;
		height: 100%;
		display: flex;
		flex-direction: column;
		justify-content: end;
		align-items: stretch;
	}

	.bar {
		width: 100%;
		background: rgba(var(--sf-c), 0.75);
		min-height: 1px;
		transition: background 0.12s;
	}

	/* hero reference bars: faded fill with full-opacity 45° hatching (--hero-hatch supplied by host;
	   its currentColor resolves against this color) */
	.bar.ghost {
		color: rgba(var(--sf-c), 1);
		background-color: rgba(var(--sf-c), 0.22);
		background-image: var(--hero-hatch);
	}

	.bar-slot:hover .bar {
		background: rgba(var(--sf-c), 1);
	}

	.bar-slot:hover .bar.ghost {
		background-color: rgba(var(--sf-c), 0.4);
		background-image: var(--hero-hatch);
	}

	.ref-pill {
		position: absolute;
		right: 0;
		margin-bottom: 1px;
		padding: 0 5px;
		font-size: var(--text-xs);
		font-weight: 600;
		line-height: 1.4;
		white-space: nowrap;
		background: var(--text-bg, #fff);
		z-index: 3;
		pointer-events: none;
	}

	.bar-label {
		position: absolute;
		bottom: -18px;
		left: 0;
		right: 0;
		text-align: center;
		font-size: var(--text-xs);
		font-weight: 600;
		letter-spacing: 0.02em;
		opacity: 0.6;
		white-space: nowrap;
	}

	.bar-value {
		position: absolute;
		left: 0;
		right: 0;
		text-align: center;
		font-size: var(--text-xs);
		font-variant-numeric: tabular-nums;
		line-height: 1.1;
		pointer-events: none;
		transform: translateY(-100%);
		padding-bottom: 2px;
		z-index: 1;
	}

	.bv-primary {
		display: block;
		font-weight: 600;
	}

	.bv-secondary {
		display: block;
		opacity: 0.6;
		font-size: 0.85em;
	}

	.peer-tooltip {
		position: fixed;
		transform: translateX(-50%) translateY(calc(-100% - 8px));
		background: #222;
		color: #fff;
		padding: 6px 9px;
		font-size: var(--text-xs);
		line-height: 1.35;
		white-space: pre-line;
		text-align: left;
		width: max-content;
		max-width: 260px;
		z-index: 100;
		pointer-events: none;
	}

	.peer-tooltip.below {
		transform: translateX(-50%) translateY(8px);
	}
</style>
