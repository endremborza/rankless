<script lang="ts">
	import { afterUpdate, onMount } from 'svelte';
	import type { RefTree, Paper, EntityAttsForLinks } from '$lib/tree-types';
	import {
		resolveSourceName,
		getChipAuthors,
		getPaperHighlights,
		isAuthored,
		type PaperHighlight
	} from '$lib/utils/paper-helpers';
	import { computeSeen } from '$lib/utils/dag-builder';
	import { getNobelOaIds } from '$lib/utils/nobel';
	import { pluralize } from '$lib/text-format-util';

	export let dag: RefTree;
	export let paperMap: Record<number, Paper>;
	export let entityAtts: EntityAttsForLinks;
	export let discAuthorNames: Record<string, string>;
	export let authorOaIds: Record<string, number> = {};
	export let sourceAuthorSemId: string | undefined = undefined;
	export let authorName: string = '';

	const HIGHLIGHT_DEFS: Record<string, { label: string; cls: string }> = {
		hit: { label: 'Standout', cls: 'hl-hit' },
		prestigious: { label: 'Prestigious', cls: 'hl-prestigious' },
		nobel: { label: 'Nobel', cls: 'hl-nobel' }
	};

	function badgeLabel(hl: PaperHighlight): string {
		if (hl.key === 'prestigious' && hl.label) return hl.label;
		return HIGHLIGHT_DEFS[hl.key]?.label ?? hl.key;
	}

	function chipMaxW(wid: number): number {
		const len = paperMap[wid]?.name?.length ?? 50;
		return Math.min(380, Math.max(200, 150 + Math.round(len * 2)));
	}

	// --- Nobel ---
	let nobelOaIds: Set<number> = new Set();

	$: pageAuthorDmId = (() => {
		if (!sourceAuthorSemId) return undefined;
		const authors = entityAtts['authors'];
		if (!authors) return undefined;
		for (const [dmId, att] of Object.entries(authors)) {
			if (att.semantic_id === sourceAuthorSemId) return dmId;
		}
		return undefined;
	})();

	$: pageAuthorOaId = pageAuthorDmId ? authorOaIds[pageAuthorDmId] : undefined;
	$: pageAuthorIsNobel = pageAuthorOaId != null && nobelOaIds.has(pageAuthorOaId);

	function hasNobelCoauthor(paper: Paper): boolean {
		if (nobelOaIds.size === 0) return false;
		for (const ship of paper.authorships) {
			if (ship.author[0] !== 'F') continue;
			const dmId = ship.author.slice(1);
			const oaId = authorOaIds[dmId];
			if (oaId == null) continue;
			if (pageAuthorIsNobel && oaId === pageAuthorOaId) continue;
			if (nobelOaIds.has(oaId)) return true;
		}
		return false;
	}

	function getHighlights(paper: Paper): PaperHighlight[] {
		const hl = getPaperHighlights(paper, undefined, entityAtts);
		if (hasNobelCoauthor(paper)) hl.push({ key: 'nobel' });
		return hl;
	}

	// --- state ---
	let hovered: number | undefined;
	let expanded = new Set<number>();

	function toggleExpand(wid: number) {
		expanded.has(wid) ? expanded.delete(wid) : expanded.add(wid);
		expanded = expanded;
	}

	$: seen = computeSeen(dag);

	$: groups = (() => {
		const allWids = Object.keys(seen).map(Number);
		if (!sourceAuthorSemId) return { impacted: allWids, authored: [] as number[] };
		const authored: number[] = [];
		const impacted: number[] = [];
		for (const wid of allWids) {
			const p = paperMap[wid];
			if (p && isAuthored(p, sourceAuthorSemId, entityAtts)) authored.push(wid);
			else impacted.push(wid);
		}
		return { impacted, authored };
	})();

	$: sections = (() => {
		const hasBoth = groups.impacted.length > 0 && groups.authored.length > 0;
		const refLabel = authorName ? `Works of ${authorName} being referenced` : 'Referenced Works';
		if (hasBoth)
			return [
				{ wids: groups.impacted, label: 'Citing Papers' },
				{ wids: groups.authored, label: refLabel }
			];
		return [{ wids: [...groups.impacted, ...groups.authored], label: '' }];
	})();

	$: relatedSet = (() => {
		if (hovered == undefined) return new Set<number>();
		const meta = seen[hovered];
		if (!meta) return new Set<number>();
		const s = new Set<number>();
		const pq = [...meta.parents].filter((p) => p !== 0);
		while (pq.length) {
			const p = pq.pop()!;
			if (s.has(p)) continue;
			s.add(p);
			seen[p]?.parents.forEach((pp) => {
				if (pp !== 0 && !s.has(pp)) pq.push(pp);
			});
		}
		const cq = [...meta.children];
		while (cq.length) {
			const c = cq.pop()!;
			if (s.has(c)) continue;
			s.add(c);
			seen[c]?.children.forEach((cc) => {
				if (!s.has(cc)) cq.push(cc);
			});
		}
		return s;
	})();

	// --- DAG edge computation ---
	type ComputedEdge = { path: string; parentWid: number; childWid: number };

	let containerEl: HTMLDivElement;
	let chipEls: Record<number, HTMLDivElement> = {};
	let edges: ComputedEdge[] = [];

	function computeEdges() {
		if (!containerEl) {
			edges = [];
			return;
		}
		const containerRect = containerEl.getBoundingClientRect();
		const newEdges: ComputedEdge[] = [];

		for (const [widStr, meta] of Object.entries(seen)) {
			const parentWid = Number(widStr);
			const parentEl = chipEls[parentWid];
			if (!parentEl) continue;

			for (const childWid of meta.children) {
				const childEl = chipEls[childWid];
				if (!childEl) continue;

				const pRect = parentEl.getBoundingClientRect();
				const cRect = childEl.getBoundingClientRect();

				const startX = pRect.left + pRect.width / 2 - containerRect.left;
				const startY = pRect.bottom - containerRect.top;
				const endX = cRect.left + cRect.width / 2 - containerRect.left;
				const endY = cRect.top - containerRect.top;

				const rawGap = endY - startY;
				let path: string;
				if (rawGap <= 10) {
					const arcDepth = 18;
					const midX = (startX + endX) / 2;
					const belowY = Math.max(startY, endY) + arcDepth;
					path = `M ${startX} ${startY} Q ${midX} ${belowY}, ${endX} ${endY}`;
				} else {
					const cp1y = startY + rawGap * 0.4;
					const cp2y = endY - rawGap * 0.4;
					path = `M ${startX} ${startY} C ${startX} ${cp1y}, ${endX} ${cp2y}, ${endX} ${endY}`;
				}
				newEdges.push({ path, parentWid: parentWid, childWid });
			}
		}
		edges = newEdges;
	}

	function edgeOpacity(edge: ComputedEdge): number {
		if (hovered == undefined) return 0.06;
		if (
			(edge.parentWid === hovered || relatedSet.has(edge.parentWid)) &&
			(edge.childWid === hovered || relatedSet.has(edge.childWid))
		)
			return 0.5;
		return 0.02;
	}

	let resizeObserver: ResizeObserver | undefined;

	onMount(() => {
		resizeObserver = new ResizeObserver(() => computeEdges());
		if (containerEl) resizeObserver.observe(containerEl);
		getNobelOaIds().then((ids) => (nobelOaIds = ids));
		return () => resizeObserver?.disconnect();
	});

	afterUpdate(() => computeEdges());
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<div class="impact-dag" bind:this={containerEl}>
	<svg class="edge-overlay" aria-hidden="true">
		{#each edges as edge}
			<path
				d={edge.path}
				stroke="currentColor"
				stroke-width="1.2"
				fill="none"
				opacity={edgeOpacity(edge)}
			/>
		{/each}
	</svg>
	{#each sections as section}
		<div class="level-section">
			{#if section.label}
				<h4 class="level-label">{section.label}</h4>
			{/if}
			<div class="chips">
				{#each section.wids as wid}
					{@const paper = paperMap[wid]}
					{@const isHovered = hovered === wid}
					{@const isRelated = relatedSet.has(wid)}
					{@const dimmed = hovered != undefined && !isHovered && !isRelated}
					{@const highlights = paper ? getHighlights(paper) : []}
					{@const isExpanded = expanded.has(wid)}
					<div
						class="chip"
						class:is-hovered={isHovered}
						class:is-related={isRelated}
						class:dimmed
						style="max-width: {chipMaxW(wid)}px"
						bind:this={chipEls[wid]}
						on:click={() => toggleExpand(wid)}
						on:mouseover={() => {
							hovered = wid;
						}}
						on:mouseleave={() => {
							hovered = undefined;
						}}
					>
						<div class="chip-title" class:clamp={!isExpanded}>
							{#if isExpanded && paper?.doi}
								<a href="https://doi.org/{paper.doi}" target="_blank" rel="noopener"
									>{paper?.name ?? '(unknown)'}</a
								>
							{:else}
								{paper?.name ?? '(unknown)'}
							{/if}
						</div>
						<div class="chip-sub">
							<span>{paper?.year}</span>
							{#each highlights as hl}
								{#if HIGHLIGHT_DEFS[hl.key]}
									<span class="badge {HIGHLIGHT_DEFS[hl.key].cls}">{badgeLabel(hl)}</span>
								{/if}
							{/each}
						</div>
						{#if isExpanded && paper}
							{@const source = resolveSourceName(paper.source, entityAtts)}
							{@const sourceSemId = entityAtts.sources?.[String(paper.source)]?.semantic_id}
							{@const authors = getChipAuthors(paper, entityAtts, discAuthorNames, 3)}
							<div class="chip-details">
								<span>{paper.citations} citations</span>
								{#if source}
									<span class="sep">·</span>
									{#if sourceSemId}
										<a href="/sources/{sourceSemId}">{source}</a>
									{:else}
										<span class="source-name">{source}</span>
									{/if}
								{/if}
								{#if authors.length > 0}
									<div class="chip-authors">
										{#each authors as author, ai}
											{#if ai > 0},&nbsp;{/if}
											{#if author.url}
												<a href={author.url}>{author.name}</a>
											{:else}
												{author.name}
											{/if}
										{/each}
										{#if paper.authorships.length > authors.length}
											&nbsp;et al.
										{/if}
									</div>
								{:else if paper.authorships.length > 0}
									<div class="chip-authors">{pluralize('author', paper.authorships.length)}</div>
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{/each}
</div>

<style>
	.impact-dag {
		display: flex;
		flex-direction: column;
		position: relative;
		gap: 12px;
	}

	.edge-overlay {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		pointer-events: none;
		overflow: visible;
		color: var(--color-text);
	}

	.level-section {
		display: flex;
		flex-direction: column;
		gap: 6px;
		position: relative;
	}

	.level-label {
		margin: 0;
		font-size: 0.85rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		opacity: 0.5;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		padding-bottom: 2px;
	}

	.chip {
		padding: 6px 10px;
		font-size: 0.78rem;
		line-height: 1.3;
		border-radius: 4px;
		border: 1px solid rgba(var(--color-range-15), 0.15);
		background: rgba(var(--color-range-15), 0.03);
		flex: 1 0 160px;
		cursor: pointer;
		transition: border-color 160ms, background-color 160ms, opacity 160ms;
		position: relative;
	}

	.chip.dimmed {
		opacity: 0.35;
	}

	.chip.is-hovered {
		border-color: var(--color-theme-blue);
		background: rgba(var(--color-range-15), 0.08);
		box-shadow: 0 0 0 1px var(--color-theme-blue);
	}

	.chip.is-related {
		border-color: var(--color-theme-blue);
		background: rgba(var(--color-range-15), 0.06);
	}

	.chip-title {
		font-weight: 600;
		line-height: 1.2;
	}

	.chip-title.clamp {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.chip-title a {
		color: inherit;
		text-decoration: none;
	}

	.chip-title a:hover {
		text-decoration: underline;
	}

	.chip-sub {
		display: flex;
		align-items: center;
		gap: 4px;
		font-size: 0.65rem;
	}

	.chip-details {
		font-size: 0.65rem;
		opacity: 0.7;
		margin-top: 4px;
		padding-top: 4px;
		border-top: 1px solid rgba(var(--color-range-15), 0.1);
	}

	.chip-details a {
		color: inherit;
		text-decoration: none;
	}

	.chip-details a:hover {
		text-decoration: underline;
	}

	.source-name {
		font-style: italic;
	}

	.chip-authors {
		margin-top: 2px;
	}

	.badge {
		display: inline-block;
		padding: 1px 5px;
		border-radius: 3px;
		font-size: 0.55rem;
		font-weight: 700;
		letter-spacing: 0.03em;
		text-transform: uppercase;
	}

	.hl-hit {
		background: var(--badge-hit-bg);
		color: var(--badge-hit-text);
	}

	.hl-prestigious {
		background: var(--badge-prestigious-bg);
		color: var(--badge-prestigious-text);
	}

	.hl-nobel {
		background: var(--badge-award-bg);
		color: var(--badge-award-text);
	}

	@media (min-width: 1200px) {
		.chip {
			padding: 8px 12px;
			font-size: 1.15rem;
			flex-basis: 300px;
		}

		.chip-sub {
			font-size: 0.9rem;
		}

		.badge {
			font-size: 0.8rem;
			padding: 1px 6px;
		}

		.chip-details {
			font-size: 0.82rem;
		}
		.level-label {
			font-size: 1.15rem;
		}
	}

	.sep {
		margin: 0 3px;
	}
</style>
