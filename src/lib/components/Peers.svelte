<script lang="ts">
	import type { EntityPeersResp, LadderData, PeerEntry, SearchResult } from '$lib/tree-types';
	import {
		abbrSfName,
		sfColorVar,
		standingLabel,
		standingPhrase,
		tierLabels,
		citStandingTier,
		ratioBarHeight,
		SUBFIELD_COLOR_VARS
	} from '$lib/peers-utils';
	import { formatNumber } from '$lib/text-format-util';
	import { urlFriendlify } from '$lib/tree-functions';
	import { BE_REMOTE_URL, LATEST_YEAR } from '$lib/constants';
	import { onMount } from 'svelte';
	import BarChart, { type Bar } from '$lib/components/BarChart.svelte';
	import PeerSearch from '$lib/components/PeerSearch.svelte';

	export let data: EntityPeersResp;
	export let rootType = 'authors';

	const DEFAULT_FIELD_N = 5;
	const MIN_FIELD_N = 2;
	const MAX_FIELD_N = SUBFIELD_COLOR_VARS.length;
	// The hero's 1× line sits at this height in both detail charts, so the dashed baseline lines up
	// across them regardless of each chart's own spread (see ratioBarHeight).
	const BASELINE_PCT = 38;

	// `sel` holds positions into data.topSubfields (sorted by hero citations desc). Default = top 5;
	// the user can toggle MIN..MAX to change the comparison basis. Reset when the hero changes.
	let sel: number[] = [];
	let selHeroId = '';
	// User-swapped peers, keyed by grid slot. Each entry overrides data.peers[slot] in `displayPeers`.
	let overrides: Record<number, PeerEntry> = {};
	$: if (data.hero.semanticId !== selHeroId) {
		selHeroId = data.hero.semanticId;
		sel = data.topSubfields.slice(0, DEFAULT_FIELD_N).map((_, i) => i);
		overrides = {};
	}
	$: selPos = [...sel].sort((a, b) => a - b);
	$: displayPeers = data.peers.map((p, i) => overrides[i] ?? p);

	// A swapped-in entity's citations come ordered by its own top subfields, so realign them to the
	// current hero's topSubfields by subfield dmId (0 where the entity has none in that subfield).
	async function swapPeer(result: SearchResult) {
		const slot = selectedIdx;
		try {
			const resp: EntityPeersResp | null = await fetch(
				`${BE_REMOTE_URL}/peers/${rootType}/${urlFriendlify(result.semanticId)}`
			).then((r) => (r.ok ? r.json() : null));
			if (!resp) return;
			const byDmId = new Map<number, number>();
			resp.topSubfields.forEach((sf, i) => byDmId.set(sf.dmId, resp.hero.subfieldCitations[i] ?? 0));
			const aligned: PeerEntry = {
				...resp.hero,
				subfieldCitations: data.topSubfields.map((sf) => byDmId.get(sf.dmId) ?? 0)
			};
			overrides = { ...overrides, [slot]: aligned };
		} catch (e) {
			console.error('swap peer failed', e);
		}
	}
	function restorePeer(slot: number) {
		const { [slot]: _, ...rest } = overrides;
		overrides = rest;
	}

	function toggleSf(pos: number) {
		if (sel.includes(pos)) {
			if (sel.length > MIN_FIELD_N) sel = sel.filter((p) => p !== pos);
		} else if (sel.length < MAX_FIELD_N) {
			sel = [...sel, pos];
		}
	}

	// Breakpoint ladder is the same across all heroes of a root type, so load it once and cache it;
	// hero standings are derived on the client from the raw citation counts (mirrors the backend).
	const ladderCache = new Map<string, Promise<LadderData | null>>();
	function loadLadder(rt: string): Promise<LadderData | null> {
		let p = ladderCache.get(rt);
		if (!p) {
			p = fetch(`${BE_REMOTE_URL}/ladder/${rt}`)
				.then((r) => (r.ok ? r.json() : null))
				.catch(() => null);
			ladderCache.set(rt, p);
		}
		return p;
	}

	let mounted = false;
	let ladder: LadderData | null = null;
	let labels: string[] = [];
	onMount(() => {
		mounted = true;
	});
	$: if (mounted && rootType) {
		loadLadder(rootType).then((l) => {
			ladder = l;
			labels = l ? tierLabels(l.pctBands, l.absRanks) : [];
		});
	}
	$: heroTiers = data.topSubfields.map((sf, pos) =>
		ladder
			? citStandingTier(ladder.ladder[sf.dmId] ?? [], data.hero.subfieldCitations[pos] ?? 0)
			: 0
	);

	$: heroSf = selPos.map((si) => Math.max(1, data.hero.subfieldCitations[si] ?? 0));
	$: peerSfRatios = displayPeers.map((p) =>
		selPos.map((si, k) => (p.subfieldCitations[si] ?? 0) / heroSf[k])
	);
	$: maxSfRatio = Math.max(1.5, ...peerSfRatios.flat());
	$: peerSfMax = Math.max(
		1,
		...displayPeers.flatMap((p) => selPos.map((si) => p.subfieldCitations[si] ?? 0))
	);

	// Trim trailing incomplete years (current year has no/partial data → hero count 0).
	$: nYears = (() => {
		const yc = data.hero.yearlyCites;
		let i = yc.length - 1;
		while (i > 0 && (yc[i] ?? 0) === 0) i--;
		return i + 1;
	})();
	$: years = Array.from(
		{ length: nYears },
		(_, i) => LATEST_YEAR - (data.hero.yearlyCites.length - 1) + i
	);
	$: heroYearly = data.hero.yearlyCites.map((v) => Math.max(1, v));
	$: peerYearRatios = displayPeers.map((p) => p.yearlyCites.map((v, y) => v / (heroYearly[y] ?? 1)));
	$: maxYearRatio = Math.max(1.5, ...peerYearRatios.flatMap((r) => r.slice(0, nYears)));

	let selectedIdx = 0;
	$: if (selectedIdx >= displayPeers.length) selectedIdx = 0;
	$: selectedPeer = displayPeers[selectedIdx];

	$: miniBars = displayPeers.map((peer, pi) =>
		selPos.map((si, k): Bar => {
			const val = peer.subfieldCitations[si] ?? 0;
			return {
				height: (val / peerSfMax) * 100,
				colorVar: sfColorVar(k),
				tip: `${data.topSubfields[si].name} · ${formatNumber(val)} (×${peerSfRatios[pi][k].toFixed(
					2
				)})`
			};
		})
	);
	$: detailSfBars = selPos.map((si, k): Bar => {
		const sf = data.topSubfields[si];
		const val = selectedPeer.subfieldCitations[si] ?? 0;
		const ratio = peerSfRatios[selectedIdx][k];
		return {
			height: ratioBarHeight(ratio, maxSfRatio, BASELINE_PCT),
			colorVar: sfColorVar(k),
			axisLabel: abbrSfName(sf.name),
			primary: `×${ratio.toFixed(1)}`,
			secondary: formatNumber(val),
			tip: `${sf.name} · ${formatNumber(val)} (×${ratio.toFixed(2)})`
		};
	});
	$: detailYearBars = years.map((yr, yi): Bar => {
		const ratio = peerYearRatios[selectedIdx][yi];
		const val = selectedPeer.yearlyCites[yi] ?? 0;
		return {
			height: ratioBarHeight(ratio, maxYearRatio, BASELINE_PCT),
			colorVar: '--sel-c',
			axisLabel: String(yr),
			tip: `${yr} · ${formatNumber(val)} (×${ratio.toFixed(2)})`
		};
	});

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
		<div class="hero-col">
			<div class="hero-name">{data.hero.name}</div>
			<details class="field-dd">
				<summary>Comparison fields: {selPos.length} of {data.topSubfields.length}</summary>
				<div class="field-dd-panel">
					{#each data.topSubfields as sf, pos}
						{@const cites = data.hero.subfieldCitations[pos] ?? 0}
						{@const label = standingLabel(heroTiers[pos], labels)}
						<label class="field-opt" class:checked={sel.includes(pos)}>
							<input
								type="checkbox"
								checked={sel.includes(pos)}
								disabled={sel.includes(pos) ? sel.length <= MIN_FIELD_N : sel.length >= MAX_FIELD_N}
								on:change={() => toggleSf(pos)}
							/>
							<span class="fo-name">{sf.name}</span>
							<span class="fo-cites">{formatNumber(cites)}</span>
							{#if label}
								<span
									class="fo-badge"
									title={standingPhrase(heroTiers[pos], labels, rootType, sf.name) ?? ''}
									>{label}</span
								>
							{/if}
						</label>
					{/each}
				</div>
			</details>
		</div>
		<ul class="field-legend">
			{#each selPos as si, k}
				{@const label = standingLabel(heroTiers[si], labels)}
				<li class="fl-row">
					<span class="fl-swatch" style="--sf-c: var({sfColorVar(k)});" />
					<span class="fl-name">{data.topSubfields[si].name}</span>
					{#if label}
						<span
							class="fl-badge"
							title={standingPhrase(heroTiers[si], labels, rootType, data.topSubfields[si].name) ??
								''}>{label}</span
						>
					{/if}
					<span class="fl-cites">{formatNumber(data.hero.subfieldCitations[si] ?? 0)}</span>
				</li>
			{/each}
		</ul>
	</div>

	<div class="peer-add">
		<span class="peer-add-label">Replace <b>{selectedPeer?.name}</b> with:</span>
		<PeerSearch
			{rootType}
			placeholder="Search {rootType} to compare…"
			excludeSemanticId={data.hero.semanticId}
			on:select={(e) => swapPeer(e.detail)}
		/>
	</div>

	<div class="peer-grid">
		{#each displayPeers as peer, pi}
			<div
				class="peer-card"
				class:selected={pi === selectedIdx}
				class:custom={!!overrides[pi]}
				role="button"
				tabindex="0"
				aria-pressed={pi === selectedIdx}
				on:click={() => selectPeer(pi)}
				on:keydown={(e) => onCardKey(e, pi)}
			>
				{#if overrides[pi]}
					<button
						type="button"
						class="peer-restore"
						title="Restore original peer"
						on:click|stopPropagation={() => restorePeer(pi)}>×</button
					>
				{/if}
				<div class="peer-head">
					<span class="peer-name">{peer.name}</span>
					{#if peer.country}
						<span class="country-tag">{peer.country}</span>
					{/if}
				</div>
				<BarChart bars={miniBars[pi]} plotHeight={64} gap={4} />
			</div>
		{/each}
	</div>

	<div class="detail-panel">
		<div class="detail-header">
			<span class="detail-name">{selectedPeer.name}</span>
			{#if selectedPeer.country}
				<span class="country-tag">{selectedPeer.country}</span>
			{/if}
			<a class="profile-link" href="/{rootType}/{selectedPeer.semanticId}">View profile →</a>
		</div>
		<div class="detail-grid">
			<div class="detail-col">
				<div class="col-title">Citations per field, relative to {data.hero.name}</div>
				<div class="rel-chart">
					<BarChart
						bars={detailSfBars}
						plotHeight={200}
						gap={14}
						baselinePct={BASELINE_PCT}
						baselineLabel={`${data.hero.name} · 1×`}
					/>
				</div>
			</div>

			<div class="detail-col">
				<div class="col-title">Citations per year, relative to {data.hero.name}</div>
				<div class="rel-chart">
					<BarChart
						bars={detailYearBars}
						plotHeight={180}
						gap={6}
						baselinePct={BASELINE_PCT}
						baselineLabel={`${data.hero.name} · 1×`}
					/>
				</div>
			</div>
		</div>
	</div>
</div>

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
		align-items: flex-start;
		gap: 22px;
		padding: 14px 18px;
		border: 1px solid rgba(var(--color-range-30), 0.18);
		background: var(--peer-track-bg);
	}

	.hero-col {
		display: flex;
		flex-direction: column;
		gap: 8px;
		flex-shrink: 0;
		min-width: 0;
		max-width: 40%;
	}

	.hero-name {
		font-weight: 700;
		font-size: var(--text-lg);
		color: rgba(var(--hero-c), 1);
	}

	.field-dd {
		font-size: var(--text-xs);
		position: relative;
	}

	.field-dd > summary {
		cursor: pointer;
		opacity: 0.7;
		user-select: none;
		width: fit-content;
	}

	.field-dd > summary:hover {
		opacity: 1;
	}

	.field-dd-panel {
		position: absolute;
		z-index: 20;
		margin-top: 6px;
		max-height: 320px;
		overflow-y: auto;
		min-width: 280px;
		padding: 6px;
		background: var(--text-bg, #fff);
		border: 1px solid rgba(var(--color-range-30), 0.35);
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
	}

	.field-opt {
		display: flex;
		align-items: center;
		gap: 8px;
		padding: 4px 6px;
		cursor: pointer;
	}

	.field-opt:hover {
		background: rgba(var(--sel-c), 0.08);
	}

	.field-opt.checked {
		background: rgba(var(--sel-c), 0.06);
	}

	.fo-name {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.fo-cites {
		font-variant-numeric: tabular-nums;
		opacity: 0.6;
		flex-shrink: 0;
	}

	.fo-badge,
	.fl-badge {
		flex-shrink: 0;
		font-size: var(--text-xs);
		font-weight: 600;
		padding: 0 5px;
		color: rgba(var(--sel-c), 1);
		background: rgba(var(--sel-c), 0.12);
		white-space: nowrap;
	}

	.field-legend {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 4px;
		flex: 1;
		min-width: 0;
	}

	.fl-row {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.fl-swatch {
		width: 11px;
		height: 11px;
		flex-shrink: 0;
		background: rgba(var(--sf-c), 0.85);
	}

	.fl-name {
		flex: 1;
		min-width: 0;
		font-size: var(--text-sm);
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.fl-cites {
		font-size: var(--text-xs);
		font-variant-numeric: tabular-nums;
		opacity: 0.6;
		flex-shrink: 0;
	}

	.peer-add {
		display: flex;
		align-items: center;
		gap: 12px;
	}

	.peer-add-label {
		font-size: var(--text-sm);
		opacity: 0.7;
		white-space: nowrap;
		flex-shrink: 0;
	}

	.peer-add-label b {
		color: rgba(var(--sel-c), 1);
	}

	.peer-grid {
		display: grid;
		grid-template-columns: repeat(5, minmax(0, 1fr));
		gap: 10px;
	}

	.peer-card {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 10px 12px;
		border: 1px solid rgba(var(--color-range-30), 0.15);
		background: var(--peer-track-bg);
		cursor: pointer;
		transition: border-color 0.12s, background 0.12s;
	}

	.peer-card:hover {
		border-color: rgba(var(--sel-c), 0.45);
	}

	.peer-card.custom {
		border-style: dashed;
		border-color: rgba(var(--sel-c), 0.55);
	}

	.peer-restore {
		position: absolute;
		top: 2px;
		right: 4px;
		padding: 0 4px;
		font-size: var(--text-base);
		line-height: 1;
		color: rgba(var(--color-range-30), 0.7);
		background: none;
		border: none;
		cursor: pointer;
	}

	.peer-restore:hover {
		color: rgba(var(--sel-c), 1);
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

	.peer-name {
		font-size: var(--text-sm);
		font-weight: 600;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.peer-card.selected .peer-name {
		color: rgba(var(--sel-c), 1);
	}

	.country-tag {
		font-size: var(--text-xs);
		opacity: 0.55;
		margin-top: 1px;
	}

	.detail-panel {
		display: flex;
		flex-direction: column;
		gap: 14px;
		padding: 18px;
		border: 1px solid rgba(var(--color-range-30), 0.15);
		background: var(--peer-track-bg);
	}

	.detail-header {
		display: flex;
		align-items: baseline;
		gap: 10px;
		min-height: 22px;
		flex-wrap: wrap;
	}

	.detail-name {
		font-weight: 700;
		font-size: var(--text-base);
		color: rgba(var(--sel-c), 1);
	}

	.profile-link {
		margin-left: auto;
		font-size: var(--text-sm);
		font-weight: 600;
		color: rgba(var(--sel-c), 1);
		text-decoration: none;
		white-space: nowrap;
	}

	.profile-link:hover {
		text-decoration: underline;
	}

	.detail-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 24px;
	}

	.detail-col {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding-bottom: 24px;
		min-width: 0;
	}

	.col-title {
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		opacity: 0.6;
	}

	/* headroom above the plot for the value labels that sit on top of the tallest bars */
	.rel-chart {
		margin-top: 30px;
	}

	@media (max-width: 900px) {
		.peer-grid {
			grid-template-columns: repeat(3, minmax(0, 1fr));
		}
		.detail-grid {
			grid-template-columns: 1fr;
		}
		.hero-strip {
			flex-direction: column;
			align-items: stretch;
			gap: 10px;
		}
		.hero-col {
			max-width: none;
		}
		.peer-add {
			flex-direction: column;
			align-items: stretch;
			gap: 6px;
		}
	}

	@media (max-width: 540px) {
		.peer-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
</style>
