<script lang="ts">
	import type { EntityPeersResp } from '$lib/tree-types';
	import {
		abbrSfName,
		sparkLinePath,
		globalCitesMax,
		sfMaxes,
		SUBFIELD_COLOR_VARS
	} from '$lib/peers-utils';

	export let data: EntityPeersResp;

	$: heroSfTotal = data.topSubfields.reduce(
		(acc, _, i) => acc + (data.hero.subfieldCitations[i] ?? 0),
		0
	);
	$: sfMaxArr = sfMaxes(data);
	$: citesMax = globalCitesMax(data);
	$: yearSpan = Math.max(1, (data.hero.yearlyCites.length || 1) - 1);

	let selectedIdx = 0;
	$: if (selectedIdx >= data.peers.length) selectedIdx = 0;
	$: selectedPeer = data.peers[selectedIdx];

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

	function selectPeer(idx: number) {
		selectedIdx = idx;
	}
	function onCardKey(e: KeyboardEvent, idx: number) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			selectedIdx = idx;
		}
	}
</script>

<div class="peers-block">
	<div class="hero-strip">
		<div class="hero-name">{data.hero.name}</div>
		<div class="hero-bar" role="presentation">
			{#each data.topSubfields as sf, si}
				{@const val = data.hero.subfieldCitations[si] ?? 0}
				{@const pct = heroSfTotal > 0 ? (val / heroSfTotal) * 100 : 0}
				{#if pct > 0}
					<div
						class="hero-seg"
						style="flex: {pct.toFixed(3)}; --sf-c: var({SUBFIELD_COLOR_VARS[si]});"
						on:mouseenter={(e) => showTip(`${sf.name} · ${val.toLocaleString()}`, e)}
						on:mouseleave={hideTip}
						role="presentation"
					>
						<span class="seg-label">{abbrSfName(sf.name)}</span>
					</div>
				{/if}
			{/each}
		</div>
	</div>

	<div class="peer-grid">
		{#each data.peers as peer, pi}
			<div
				class="peer-card"
				class:selected={pi === selectedIdx}
				role="button"
				tabindex="0"
				aria-pressed={pi === selectedIdx}
				on:click={() => selectPeer(pi)}
				on:keydown={(e) => onCardKey(e, pi)}
			>
				<div class="peer-head">
					<a class="peer-link" href="/authors/{peer.semanticId}" on:click|stopPropagation>
						{peer.name}
					</a>
					{#if peer.country}
						<span class="country-tag">{peer.country}</span>
					{/if}
				</div>
				<div class="bars mini">
					{#each data.topSubfields as sf, si}
						{@const val = peer.subfieldCitations[si] ?? 0}
						{@const h = (val / sfMaxArr[si]) * 100}
						<div
							class="bar-slot"
							on:mouseenter={(e) => showTip(`${sf.name} · ${val.toLocaleString()}`, e)}
							on:mouseleave={hideTip}
							role="presentation"
						>
							<div
								class="bar"
								style="height: {h.toFixed(2)}%; --sf-c: var({SUBFIELD_COLOR_VARS[si]});"
							/>
						</div>
					{/each}
				</div>
			</div>
		{/each}
	</div>

	<div class="detail-panel">
		<div class="detail-bars">
			<div class="detail-title">
				<a class="detail-link" href="/authors/{selectedPeer.semanticId}">{selectedPeer.name}</a>
				{#if selectedPeer.country}
					<span class="country-tag">{selectedPeer.country}</span>
				{/if}
			</div>
			<div class="bars big">
				{#each data.topSubfields as sf, si}
					{@const val = selectedPeer.subfieldCitations[si] ?? 0}
					{@const h = (val / sfMaxArr[si]) * 100}
					<div
						class="bar-slot"
						on:mouseenter={(e) => showTip(`${sf.name} · ${val.toLocaleString()}`, e)}
						on:mouseleave={hideTip}
						role="presentation"
					>
						<div
							class="bar"
							style="height: {h.toFixed(2)}%; --sf-c: var({SUBFIELD_COLOR_VARS[si]});"
						/>
						<span class="bar-label">{abbrSfName(sf.name)}</span>
					</div>
				{/each}
			</div>
		</div>

		<div class="detail-spark">
			<div class="spark-title">
				Citations per year
				<span class="legend">
					<span class="leg leg-others" /> peers
					<span class="leg leg-hero" />
					{data.hero.name}
					<span class="leg leg-selected" />
					{selectedPeer.name}
				</span>
			</div>
			<svg viewBox="0 0 {yearSpan} 1" class="ribbon" preserveAspectRatio="none">
				{#each data.peers as peer, pi}
					{#if pi !== selectedIdx}
						<path d={sparkLinePath(peer.yearlyCites, citesMax)} class="ribbon-other" />
					{/if}
				{/each}
				<path d={sparkLinePath(data.hero.yearlyCites, citesMax)} class="ribbon-hero" />
				<path d={sparkLinePath(selectedPeer.yearlyCites, citesMax)} class="ribbon-selected" />
			</svg>
		</div>
	</div>
</div>

{#if tipText !== null}
	<div class="peer-tooltip" style="left:{tipX}px; top:{tipY}px;">{tipText}</div>
{/if}

<style>
	.peers-block {
		--hero-c: var(--color-range-40);
		--sel-c: var(--color-range-15);
		--peer-track-bg: rgba(var(--color-range-25), 0.04);
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.hero-strip {
		display: flex;
		align-items: center;
		gap: 18px;
		padding: 14px 18px;
		border: 1px solid rgba(var(--color-range-30), 0.18);
		border-radius: 6px;
		background: var(--peer-track-bg);
	}

	.hero-name {
		font-weight: 700;
		font-size: var(--text-lg);
		color: rgba(var(--hero-c), 1);
		white-space: nowrap;
		flex-shrink: 0;
	}

	.hero-bar {
		flex: 1;
		display: flex;
		height: 22px;
		border-radius: 3px;
		overflow: hidden;
	}

	.hero-seg {
		min-width: 0;
		position: relative;
		background: rgba(var(--sf-c), 0.7);
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: default;
		transition: background 0.12s;
	}

	.hero-seg:hover {
		background: rgba(var(--sf-c), 0.95);
	}

	.seg-label {
		font-size: var(--text-xs);
		font-weight: 600;
		letter-spacing: 0.04em;
		color: rgba(255, 255, 255, 0.92);
		text-shadow: 0 0 2px rgba(0, 0, 0, 0.35);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: clip;
	}

	.peer-grid {
		display: grid;
		grid-template-columns: repeat(5, minmax(0, 1fr));
		gap: 10px;
	}

	.peer-card {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 10px 12px;
		border: 1px solid rgba(var(--color-range-30), 0.15);
		border-radius: 4px;
		background: var(--peer-track-bg);
		cursor: pointer;
		transition: border-color 0.12s, background 0.12s, transform 0.12s;
	}

	.peer-card:hover {
		border-color: rgba(var(--sel-c), 0.45);
	}

	.peer-card.selected {
		border-color: rgba(var(--sel-c), 1);
		border-width: 2px;
		padding: 9px 11px;
		background: rgba(var(--sel-c), 0.06);
	}

	.peer-head {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.peer-link {
		font-size: var(--text-sm);
		font-weight: 600;
		color: inherit;
		text-decoration: none;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.peer-card.selected .peer-link {
		color: rgba(var(--sel-c), 1);
	}

	.peer-link:hover {
		text-decoration: underline;
	}

	.country-tag {
		font-size: var(--text-xs);
		opacity: 0.55;
		margin-top: 1px;
	}

	.bars {
		display: grid;
		grid-template-columns: repeat(5, minmax(0, 1fr));
		gap: 4px;
		align-items: end;
	}

	.bars.mini {
		height: 44px;
	}

	.bars.big {
		height: 180px;
		gap: 10px;
		padding-top: 6px;
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
		border-radius: 2px 2px 0 0;
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
		letter-spacing: 0.04em;
		opacity: 0.6;
		white-space: nowrap;
	}

	.detail-panel {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 24px;
		padding: 18px;
		border: 1px solid rgba(var(--color-range-30), 0.15);
		border-radius: 6px;
		background: var(--peer-track-bg);
	}

	.detail-bars {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding-bottom: 22px;
	}

	.detail-title {
		display: flex;
		align-items: baseline;
		gap: 8px;
		min-height: 22px;
	}

	.detail-link {
		font-weight: 700;
		font-size: var(--text-base);
		color: rgba(var(--sel-c), 1);
		text-decoration: none;
	}

	.detail-link:hover {
		text-decoration: underline;
	}

	.detail-spark {
		display: flex;
		flex-direction: column;
		gap: 8px;
		min-height: 0;
	}

	.spark-title {
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		opacity: 0.6;
		display: flex;
		gap: 14px;
		align-items: center;
		flex-wrap: wrap;
	}

	.legend {
		display: inline-flex;
		gap: 10px;
		align-items: center;
		text-transform: none;
		letter-spacing: 0;
		font-size: var(--text-xs);
	}

	.leg {
		display: inline-block;
		width: 18px;
		height: 2px;
		vertical-align: middle;
		margin-right: 4px;
	}

	.leg-others {
		background: rgba(var(--color-range-30), 0.35);
	}

	.leg-hero {
		background: rgba(var(--hero-c), 1);
		height: 3px;
	}

	.leg-selected {
		background: rgba(var(--sel-c), 1);
		height: 3px;
	}

	.ribbon {
		width: 100%;
		height: 180px;
		display: block;
		overflow: visible;
	}

	.ribbon-other {
		fill: none;
		stroke: rgba(var(--color-range-30), 0.28);
		stroke-width: 0.04;
		stroke-linejoin: round;
		stroke-linecap: round;
	}

	.ribbon-hero {
		fill: none;
		stroke: rgba(var(--hero-c), 0.95);
		stroke-width: 0.07;
		stroke-linejoin: round;
		stroke-linecap: round;
	}

	.ribbon-selected {
		fill: none;
		stroke: rgba(var(--sel-c), 1);
		stroke-width: 0.07;
		stroke-linejoin: round;
		stroke-linecap: round;
	}

	.peer-tooltip {
		position: fixed;
		transform: translateX(-50%) translateY(calc(-100% - 8px));
		background: #222;
		color: #fff;
		padding: 5px 9px;
		border-radius: 4px;
		font-size: var(--text-xs);
		white-space: nowrap;
		z-index: 100;
		pointer-events: none;
	}

	@media (max-width: 900px) {
		.peer-grid {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
		.detail-panel {
			grid-template-columns: 1fr;
		}
		.hero-strip {
			flex-direction: column;
			align-items: stretch;
			gap: 10px;
		}
		.hero-name {
			text-align: center;
		}
	}

	@media (max-width: 540px) {
		.peer-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
</style>
