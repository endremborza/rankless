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
	import { dev, version } from '$app/environment';
	import { onMount } from 'svelte';
	import { afterNavigate } from '$app/navigation';
	import BarChart, { type Bar, type Tick } from '$lib/components/BarChart.svelte';
	import PeerSearch from '$lib/components/PeerSearch.svelte';

	export let data: EntityPeersResp;
	export let rootType = 'authors';

	const DEFAULT_FIELD_N = 5;
	const MIN_FIELD_N = 2;
	const MAX_FIELD_N = SUBFIELD_COLOR_VARS.length;
	// The peer's 1× line sits at this height; below it scales linearly into 0, above it up to the
	// chart's max ratio (see ratioBarHeight). Same value + scale in both charts ⇒ the line aligns.
	const BASELINE_PCT = 38;
	// Below this hero/peer ratio the gap reads as ~1× — the minor label shows the raw counts instead of
	// the hero's alone — and it floors each chart's scale so a near-tie still leaves baseline headroom.
	const CLOSE_RATIO = 1.5;
	const DETAIL_PLOT_H = 200;

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
			resp.topSubfields.forEach((sf, i) =>
				byDmId.set(sf.dmId, resp.hero.subfieldCitations[i] ?? 0)
			);
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
	// The endpoint carries a 24h browser cache. In prod, `?v=version` (a per-build stamp) busts it
	// on each deploy so a regenerated ladder takes effect immediately. In dev, a per-fetch timestamp
	// always bypasses the cache, so a `make -B` rebuild shows up without restarting `bun run dev`.
	const ladderCache = new Map<string, Promise<LadderData | null>>();
	function loadLadder(rt: string): Promise<LadderData | null> {
		let p = ladderCache.get(rt);
		if (!p) {
			const bust = dev ? Date.now() : version;
			p = fetch(`${BE_REMOTE_URL}/ladder/${rt}?v=${bust}`)
				.then((r) => (r.ok ? r.json() : null))
				.catch(() => null);
			ladderCache.set(rt, p);
		}
		return p;
	}

	function refreshLadder() {
		loadLadder(rootType).then((l) => {
			ladder = l;
			labels = l ? tierLabels(l.pctBands) : [];
		});
	}

	let ladder: LadderData | null = null;
	let labels: string[] = [];
	// The two detail charts only share a scale + axis side by side; once stacked (≤900px) each is on its
	// own. Matches the .detail-grid media query so the JS scale and the CSS layout flip together.
	let wide = true;
	onMount(() => {
		refreshLadder();
		const mq = window.matchMedia('(min-width: 901px)');
		wide = mq.matches;
		const onChange = (e: MediaQueryListEvent) => (wide = e.matches);
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});
	afterNavigate(() => refreshLadder());
	$: heroTiers = data.topSubfields.map((sf, pos) =>
		ladder
			? citStandingTier(ladder.ladder[sf.dmId] ?? [], data.hero.subfieldCitations[pos] ?? 0)
			: 0
	);

	$: heroSf = selPos.map((si) => Math.max(1, data.hero.subfieldCitations[si] ?? 0));
	// Peer-relative-to-hero, for the grid mini-bars' hover tips (each peer measured against the hero).
	$: peerSfRatios = displayPeers.map((p) =>
		selPos.map((si, k) => (p.subfieldCitations[si] ?? 0) / heroSf[k])
	);
	// Mini-chart scale, shared across cards so they stay comparable; spans both peer and hero bars.
	$: miniMax = Math.max(
		1,
		...heroSf,
		...displayPeers.flatMap((p) => selPos.map((si) => p.subfieldCitations[si] ?? 0))
	);
	// Detail charts flip the frame: the hero is the bar, each peer its own 1× reference. Per-peer rows;
	// the selected peer drives the scale (computed below, after the selection). A peer with no citations
	// in a slot has no finite multiplier → Infinity (drawn as ×∞, clamped to the top, off the scale).
	$: heroSfRatios = displayPeers.map((p) =>
		selPos.map((si, k) => {
			const pv = p.subfieldCitations[si] ?? 0;
			return pv > 0 ? heroSf[k] / pv : Infinity;
		})
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
	$: heroYearRatios = displayPeers.map((p) =>
		p.yearlyCites.map((v, y) => (v > 0 ? (heroYearly[y] ?? 1) / v : Infinity))
	);

	let selectedIdx = 0;
	$: if (selectedIdx >= displayPeers.length) selectedIdx = 0;
	$: selectedPeer = displayPeers[selectedIdx];

	// Scale = the selected peer's largest ratio, so the tallest bar always reaches the top and switching
	// peers rescales both charts. Side by side they share one top (the larger of the two) so bars, ticks
	// and the 1× line align; stacked, each uses its own. The shared axis labels live on the left chart.
	$: maxSfRatio = chartMax(heroSfRatios[selectedIdx] ?? []);
	$: maxYearRatio = chartMax((heroYearRatios[selectedIdx] ?? []).slice(0, nYears));
	$: sharedMax = Math.max(maxSfRatio, maxYearRatio);
	$: sfScale = wide ? sharedMax : maxSfRatio;
	$: yearScale = wide ? sharedMax : maxYearRatio;
	$: sfTicks = buildTicks(sfScale);
	$: yearTicks = buildTicks(yearScale);

	// Each subfield is a tight pair: the peer (solid) beside the hero (ghost), same color. The hero bars
	// repeat across every card, giving a fixed silhouette to read each peer against.
	$: miniBars = displayPeers.map((peer, pi) =>
		selPos.flatMap((si, k): Bar[] => {
			const sf = data.topSubfields[si];
			const peerVal = peer.subfieldCitations[si] ?? 0;
			const heroVal = data.hero.subfieldCitations[si] ?? 0;
			const cv = sfColorVar(k);
			return [
				{
					height: (peerVal / miniMax) * 100,
					colorVar: cv,
					tip: `${sf.name} · ${peer.name} ${formatNumber(peerVal)} (×${peerSfRatios[pi][k].toFixed(
						2
					)} of ${data.hero.name})`
				},
				{
					height: (heroVal / miniMax) * 100,
					colorVar: cv,
					ghost: true,
					tip: `${sf.name} · ${data.hero.name} ${formatNumber(heroVal)}`
				}
			];
		})
	);
	$: detailSfBars = selPos.map((si, k): Bar => {
		const sf = data.topSubfields[si];
		const heroVal = data.hero.subfieldCitations[si] ?? 0;
		const peerVal = selectedPeer.subfieldCitations[si] ?? 0;
		const mult = multLabel(heroVal, peerVal);
		const ratio = Math.min(heroSfRatios[selectedIdx][k], sfScale);
		return {
			height: ratioBarHeight(ratio, sfScale, BASELINE_PCT),
			colorVar: sfColorVar(k),
			axisLabel: abbrSfName(sf.name),
			primary: mult,
			secondary: fracLabel(heroVal, peerVal),
			tip: relTip(sf.name, heroVal, peerVal)
		};
	});
	$: detailYearBars = years.map((yr, yi): Bar => {
		const heroVal = data.hero.yearlyCites[yi] ?? 0;
		const peerVal = selectedPeer.yearlyCites[yi] ?? 0;
		const ratio = Math.min(heroYearRatios[selectedIdx][yi], yearScale);
		return {
			height: ratioBarHeight(ratio, yearScale, BASELINE_PCT),
			colorVar: '--hero-c',
			axisLabel: String(yr),
			tip: relTip(String(yr), heroVal, peerVal)
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

	// Multi-line hover tip framing the hero against the selected peer for one slice (a subfield or a
	// year): each side's raw count, then the ratio spelled out as hero / peer = ×N so the bar's
	// multiplier is legible without decoding the chart.
	function relTip(context: string, heroVal: number, peerVal: number): string {
		const h = formatNumber(heroVal);
		const p = formatNumber(peerVal);
		return `${context}\n${data.hero.name}: ${h}\n${
			selectedPeer.name
		}: ${p}\n${h} / ${p} = ${multLabel(heroVal, peerVal)}`;
	}
	// Bold bar label: how many times the hero's count covers the peer's; "×∞" when the peer has none.
	function multLabel(heroVal: number, peerVal: number): string {
		if (peerVal === 0) return heroVal > 0 ? '×∞' : '×1';
		const r = heroVal / peerVal;
		return r >= 10 ? `×${Math.round(r)}` : `×${r.toFixed(1)}`;
	}
	// Minor label: raw "hero/peer" counts while the two stay within CLOSE_RATIO (there the ×N reads as
	// ~1× and says little); past that the multiplier carries the gap, so just show the hero's count.
	function fracLabel(heroVal: number, peerVal: number): string {
		if (peerVal === 0) return `${formatNumber(heroVal, 0)}/0`;
		return `${formatNumber(heroVal, 0)}/${formatNumber(peerVal, 0)}`;
	}

	// A chart's raw scale: the largest real multiplier among the bars, floored at CLOSE_RATIO so a
	// near-tie keeps baseline headroom. ×∞ slices (a peer with no citations in a slot, common in a
	// peer's pre-career years) carry no finite ratio, so they're dropped here and clamped to the top in
	// the bar — but a real, large gap now sets the top honestly instead of pinning to a fixed ceiling.
	function chartMax(ratios: number[]): number {
		return Math.max(CLOSE_RATIO, ...ratios.filter((r) => Number.isFinite(r)));
	}
	// A "nice" gridline step (1/2/5 × 10ⁿ) sized for ~5 steps regardless of range, so a 3× axis and a
	// 60× axis both stay legible.
	function niceStep(scale: number): number {
		const raw = scale / 5;
		const pow = Math.pow(10, Math.floor(Math.log10(raw)));
		const norm = raw / pow;
		const m = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10;
		return m * pow;
	}
	// Ticks for a chart topping out at `scale`: 0, 0.5×, 1× (the reference), nice round steps, then the
	// exact max so the tallest bar reaches the top. A round step within half a step of the top is skipped
	// so it can't crowd the max.
	function buildTicks(scale: number): Tick[] {
		const step = niceStep(scale);
		const vals = [0, 0.5, 1];
		for (let r = Math.ceil((1 + 1e-9) / step) * step; r <= scale - step * 0.5 + 1e-9; r += step)
			vals.push(r);
		vals.push(scale);
		return vals.map((r) => ({
			pct: ratioBarHeight(r, scale, BASELINE_PCT),
			label: r === 0 ? '0' : Number.isInteger(r) ? `${r}×` : `${r.toFixed(1)}×`,
			ref: r === 1
		}));
	}
</script>

<div class="peers-block">
	<div class="hero-strip">
		<div class="hero-col">
			<div class="hero-name">{data.hero.name}</div>
			<details class="field-dd">
				<summary>Comparison fields: {selPos.length} of {data.topSubfields.length}</summary>
				<div class="field-dd-panel">
					{#each data.topSubfields as sf, pos (pos)}
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
			{#each selPos as si, k (k)}
				{@const label = standingLabel(heroTiers[si], labels)}
				<li class="fl-row">
					<span class="fl-swatch" style="--sf-c: var({sfColorVar(k)});"></span>
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
		{#each displayPeers as peer, pi (pi)}
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
				<BarChart bars={miniBars[pi]} plotHeight={64} gap={7} groupSize={2} groupGap={1} />
			</div>
		{/each}
	</div>

	<div class="detail-panel">
		<div class="detail-header">
			<span class="detail-title">
				<span class="dt-hero">{data.hero.name}</span>
				<span class="dt-rel">relative to</span>
				<span class="dt-peer">{selectedPeer.name}</span>
			</span>
			{#if selectedPeer.country}
				<span class="country-tag">{selectedPeer.country}</span>
			{/if}
			<a class="profile-link" href="/{rootType}/{selectedPeer.semanticId}"
				>{selectedPeer.name}'s profile →</a
			>
		</div>
		<div class="detail-grid">
			<div class="detail-col">
				<div class="col-title">Citations per field</div>
				<div class="rel-chart">
					<BarChart
						bars={detailSfBars}
						plotHeight={DETAIL_PLOT_H}
						gap={14}
						ticks={sfTicks}
						refColorVar="--sel-c"
						refLabel={`${selectedPeer.name} · 1×`}
					/>
				</div>
			</div>

			<div class="detail-col">
				<div class="col-title">Citations per year</div>
				<div class="rel-chart">
					<BarChart
						bars={detailYearBars}
						plotHeight={DETAIL_PLOT_H}
						gap={6}
						ticks={yearTicks}
						showLabels={!wide}
						refColorVar="--sel-c"
						refLabel={wide ? '' : `${selectedPeer.name} · 1×`}
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
		/* hero fill: full-opacity 45° lines over a faded base. Uses currentColor (not var(--sf-c)) so the
		   line color resolves per element where applied — a nested var() would resolve here, undefined. */
		--hero-hatch: repeating-linear-gradient(
			45deg,
			currentColor 0,
			currentColor 1.5px,
			transparent 1.5px,
			transparent 6px
		);
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
		width: 14px;
		height: 18px;
		flex-shrink: 0;
		color: rgba(var(--sf-c), 1);
		background-color: rgba(var(--sf-c), 0.22);
		background-image: var(--hero-hatch);
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
		transition:
			border-color 0.12s,
			background 0.12s;
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

	.detail-title {
		font-weight: 700;
		font-size: var(--text-base);
	}

	.dt-hero {
		color: rgba(var(--hero-c), 1);
	}

	.dt-rel {
		font-weight: 400;
		font-size: var(--text-sm);
		opacity: 0.55;
	}

	.dt-peer {
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

	/* headroom above the plot for the two-line value labels (×N + count) that sit on top of the tallest
	   bars, so they clear the column title */
	.rel-chart {
		margin-top: 46px;
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
