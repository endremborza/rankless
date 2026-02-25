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

	export let dag: RefTree;
	export let paperMap: Record<number, Paper>;
	export let entityAtts: EntityAttsForLinks;
	export let discAuthorNames: Record<string, string>;
	export let sourceAuthorSemId: string | undefined = undefined;

	const HIGHLIGHT_DEFS: Record<string, { label: string; cls: string }> = {
		hit: { label: 'High Impact', cls: 'hl-hit' },
		prestigious: { label: 'Prestigious', cls: 'hl-prestigious' }
	};

	type NodeMeta = { level: number; parents: Set<number>; children: Set<number> };
	type SeenMap = Record<number, NodeMeta>;

	function build(node: RefTree, seen: SeenMap, depth: number, parent: number) {
		if (node === 'Leaf') return;
		for (const key of Object.keys(node.Node).map(Number)) {
			if (seen[key] == undefined || seen[key].level > depth)
				seen[key] = { level: depth, parents: new Set(), children: new Set() };
			if (depth === seen[key].level) {
				seen[key].parents.add(parent);
				if (parent !== 0)
					(seen[parent] ??= {
						level: depth - 1,
						parents: new Set(),
						children: new Set()
					}).children.add(key);
			}
			build(node.Node[key], seen, depth + 1, key);
		}
	}

	function computeSeen(t: RefTree): SeenMap {
		const seen: SeenMap = {};
		build(t, seen, 0, 0);
		for (const [, meta] of Object.entries(seen)) {
			for (const p of meta.parents) {
				if (p !== 0 && seen[p])
					seen[p].children.add(
						Number(Object.keys(seen).find((k) => seen[Number(k)] === meta))
					);
			}
		}
		return seen;
	}

	function badgeLabel(hl: PaperHighlight): string {
		if (hl.key === 'prestigious' && hl.label) return hl.label;
		return HIGHLIGHT_DEFS[hl.key]?.label ?? hl.key;
	}

	function chipMaxW(wid: number): number {
		const len = paperMap[wid]?.name?.length ?? 50;
		return Math.min(280, Math.max(170, 130 + Math.round(len * 1.8)));
	}

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
		if (hasBoth)
			return [
				{ wids: groups.impacted, label: 'Citing Papers' },
				{ wids: groups.authored, label: 'Referenced Works' }
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
	let edgeSvgEl: SVGSVGElement;

	const GAP_HEIGHT = 28;

	function computeEdges() {
		if (
			!containerEl ||
			!edgeSvgEl ||
			groups.impacted.length === 0 ||
			groups.authored.length === 0
		) {
			edges = [];
			return;
		}
		const svgRect = edgeSvgEl.getBoundingClientRect();
		const newEdges: ComputedEdge[] = [];
		const authoredSet = new Set(groups.authored);

		for (const impWid of groups.impacted) {
			const el = chipEls[impWid];
			if (!el) continue;
			const pRect = el.getBoundingClientRect();
			const startX = pRect.left + pRect.width / 2 - svgRect.left;
			const startY = pRect.bottom - svgRect.top;

			const children = seen[impWid]?.children;
			if (!children) continue;
			for (const childWid of children) {
				if (!authoredSet.has(childWid)) continue;
				const childEl = chipEls[childWid];
				if (!childEl) continue;
				const cRect = childEl.getBoundingClientRect();
				const endX = cRect.left + cRect.width / 2 - svgRect.left;
				const endY = cRect.top - svgRect.top;

				const gap = endY - startY;
				const cp1y = startY + gap * 0.4;
				const cp2y = endY - gap * 0.4;
				newEdges.push({
					path: `M ${startX} ${startY} C ${startX} ${cp1y}, ${endX} ${cp2y}, ${endX} ${endY}`,
					parentWid: impWid,
					childWid
				});
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
		return () => resizeObserver?.disconnect();
	});

	afterUpdate(() => computeEdges());
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<div class="impact-dag" bind:this={containerEl}>
	{#each sections as section, si}
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
					{@const highlights = paper
						? getPaperHighlights(paper, undefined, entityAtts)
						: []}
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
									<span class="badge {HIGHLIGHT_DEFS[hl.key].cls}"
										>{badgeLabel(hl)}</span
									>
								{/if}
							{/each}
						</div>
						{#if isExpanded && paper}
							{@const source = resolveSourceName(paper.source, entityAtts)}
							{@const sourceSemId =
								entityAtts.sources?.[String(paper.source)]?.semantic_id}
							{@const authors = getChipAuthors(
								paper,
								entityAtts,
								discAuthorNames,
								3
							)}
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
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
		{#if si === 0 && sections.length > 1}
			<svg
				class="edge-svg"
				bind:this={edgeSvgEl}
				style="height: {GAP_HEIGHT}px"
				aria-hidden="true"
			>
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
		{/if}
	{/each}
</div>

<style>
	.impact-dag {
		display: flex;
		flex-direction: column;
		position: relative;
	}

	.level-section {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.level-label {
		margin: 0;
		font-size: 0.65rem;
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
		padding: 4px 8px;
		font-size: 0.72rem;
		line-height: 1.3;
		border-radius: 4px;
		border: 1px solid rgba(var(--color-range-15), 0.15);
		background: rgba(var(--color-range-15), 0.03);
		flex: 1 0 130px;
		cursor: pointer;
		transition: border-color 160ms, background-color 160ms, opacity 160ms;
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
		font-size: 0.6rem;
		opacity: 0.6;
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
		padding: 0px 5px;
		border-radius: 3px;
		font-size: 0.5rem;
		font-weight: 600;
		letter-spacing: 0.03em;
		text-transform: uppercase;
	}

	.hl-hit {
		background: rgba(var(--color-range-80), 0.15);
		color: rgba(var(--color-range-80), 1);
	}

	.hl-prestigious {
		background: rgba(120, 80, 180, 0.15);
		color: rgb(120, 80, 180);
	}

	.edge-svg {
		width: 100%;
		overflow: visible;
		color: var(--color-text);
	}

	.sep {
		margin: 0 3px;
	}
</style>
