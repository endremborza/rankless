<script lang="ts" context="module">
	export type Bar = {
		height: number; // 0..100, % of plot height
		colorVar: string; // a --color-range-* (or --sel-c) var name
		axisLabel?: string; // label under the bar
		primary?: string; // bold label above the bar top
		secondary?: string; // muted label above the bar top
		tip?: string; // tooltip text on hover
	};
</script>

<script lang="ts">
	export let bars: Bar[];
	export let plotHeight = 200;
	export let gap = 14;
	export let baselinePct: number | null = null;
	export let baselineLabel: string | null = null;

	let tipText: string | null = null;
	let tipX = 0;
	let tipY = 0;
	function showTip(text: string, e: MouseEvent) {
		const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
		tipText = text;
		tipX = r.left + r.width / 2;
		tipY = r.top;
	}
	function hideTip() {
		tipText = null;
	}
</script>

<div class="bars" style="height: {plotHeight}px; gap: {gap}px;">
	{#if baselinePct !== null}
		<div class="baseline" style="bottom: {baselinePct}%;">
			{#if baselineLabel}
				<span class="baseline-label">{baselineLabel}</span>
			{/if}
		</div>
	{/if}
	{#each bars as bar}
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
			<div class="bar" style="height: {bar.height.toFixed(2)}%; --sf-c: var({bar.colorVar});" />
			{#if bar.axisLabel}
				<span class="bar-label">{bar.axisLabel}</span>
			{/if}
		</div>
	{/each}
</div>

{#if tipText !== null}
	<div class="peer-tooltip" style="left:{tipX}px; top:{tipY}px;">{tipText}</div>
{/if}

<style>
	.bars {
		display: grid;
		grid-auto-flow: column;
		grid-auto-columns: minmax(0, 1fr);
		align-items: end;
		position: relative;
	}

	.baseline {
		position: absolute;
		left: 0;
		right: 0;
		height: 0;
		border-top: 1px dashed rgba(var(--hero-c), 0.6);
		pointer-events: none;
		z-index: 2;
	}

	.baseline-label {
		position: absolute;
		right: 0;
		top: -14px;
		font-size: var(--text-xs);
		color: rgba(var(--hero-c), 0.85);
		background: var(--text-bg, transparent);
		padding: 0 4px;
		white-space: nowrap;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.bar-slot {
		position: relative;
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

	.bar-slot:hover .bar {
		background: rgba(var(--sf-c), 1);
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
		padding: 5px 9px;
		font-size: var(--text-xs);
		white-space: nowrap;
		z-index: 100;
		pointer-events: none;
	}
</style>
