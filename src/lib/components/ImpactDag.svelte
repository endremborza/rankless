<script lang="ts">
	import type { RefTree, Paper, EntityAttsForLinks } from '$lib/tree-types';
	import { resolveSourceName, getChipAuthors, getPaperHighlights } from '$lib/utils/paper-helpers';

	export let dag: RefTree;
	export let paperMap: Record<number, Paper>;
	export let entityAtts: EntityAttsForLinks;
	export let discAuthorNames: Record<string, string>;
	export let sourceAuthorSemId: string | undefined = undefined;

	const HIGHLIGHT_DEFS: Record<string, { label: string; cls: string }> = {
		authored: { label: 'Authored', cls: 'hl-authored' },
		hit: { label: 'High Impact', cls: 'hl-hit' },
		science: { label: 'Science', cls: 'hl-science' },
		nature: { label: 'Nature', cls: 'hl-nature' }
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
					seen[p].children.add(Number(Object.keys(seen).find((k) => seen[Number(k)] === meta)));
			}
		}
		return seen;
	}

	function getLevels(seen: SeenMap): number[][] {
		const levels: number[][] = [];
		for (const [k, v] of Object.entries(seen)) {
			if (!levels[v.level]) levels[v.level] = [];
			levels[v.level].push(Number(k));
		}
		return levels;
	}

	function levelLabel(i: number, total: number): string {
		if (total === 1) return 'Papers in the Citation Network';
		if (i === 0) return 'High-Impact Citing Papers';
		if (i === total - 1) return 'Referenced Works';
		return 'Citation Chain';
	}

	let hovered: number | undefined;
	let expanded = new Set<number>();

	function toggleExpand(wid: number) {
		expanded.has(wid) ? expanded.delete(wid) : expanded.add(wid);
		expanded = expanded;
	}

	$: seen = computeSeen(dag);
	$: levels = getLevels(seen);
	$: relatedSet = (() => {
		if (hovered == undefined) return new Set<number>();
		const meta = seen[hovered];
		if (!meta) return new Set<number>();
		const s = new Set<number>();
		meta.parents.forEach((p) => {
			if (p !== 0) s.add(p);
		});
		meta.children.forEach((c) => s.add(c));
		return s;
	})();

	$: activeHighlightKeys = (() => {
		const keys = new Set<string>();
		for (const wids of levels)
			for (const wid of wids) {
				const p = paperMap[wid];
				if (!p) continue;
				for (const h of getPaperHighlights(p, sourceAuthorSemId, entityAtts))
					if (HIGHLIGHT_DEFS[h]) keys.add(h);
			}
		return keys;
	})();
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<div class="impact-dag">
	{#if activeHighlightKeys.size > 0}
		<div class="legend">
			{#each [...activeHighlightKeys] as key}
				{@const def = HIGHLIGHT_DEFS[key]}
				<span class="legend-badge {def.cls}">{def.label}</span>
			{/each}
		</div>
	{/if}

	{#each levels as level, i}
		<div class="level-section">
			<h4 class="level-label">{levelLabel(i, levels.length)}</h4>
			<div class="chips">
				{#each level as wid}
					{@const paper = paperMap[wid]}
					{@const isHovered = hovered === wid}
					{@const isRelated = relatedSet.has(wid)}
					{@const dimmed = hovered != undefined && !isHovered && !isRelated}
					{@const highlights = paper
						? getPaperHighlights(paper, sourceAuthorSemId, entityAtts)
						: []}
					{@const isExpanded = expanded.has(wid)}
					<div
						class="chip"
						class:is-hovered={isHovered}
						class:is-related={isRelated}
						class:dimmed
						on:click={() => toggleExpand(wid)}
						on:mouseover={() => {
							hovered = wid;
						}}
						on:mouseleave={() => {
							hovered = undefined;
						}}
					>
						<div class="chip-title" class:truncate={!isExpanded}>
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
								{@const def = HIGHLIGHT_DEFS[hl]}
								{#if def}<span class="badge {def.cls}">{def.label}</span>{/if}
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
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
		{#if i < levels.length - 1}
			<div class="connector" aria-hidden="true">
				<svg width="20" height="20" viewBox="0 0 20 20">
					<path
						d="M10 2 L10 14 M6 10 L10 14 L14 10"
						stroke="currentColor"
						stroke-width="1.5"
						fill="none"
						opacity="0.4"
					/>
				</svg>
			</div>
		{/if}
	{/each}
</div>

<style>
	.impact-dag {
		display: flex;
		flex-direction: column;
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-bottom: 12px;
	}

	.legend-badge {
		padding: 2px 8px;
		border-radius: 3px;
		font-size: 0.6rem;
		font-weight: 600;
		letter-spacing: 0.03em;
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
		flex: 1 0 220px;
		max-width: 380px;
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

	.chip-title.truncate {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
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

	.hl-authored {
		background: rgba(80, 140, 220, 0.15);
		color: rgb(80, 140, 220);
	}

	.hl-hit {
		background: rgba(var(--color-range-80), 0.15);
		color: rgba(var(--color-range-80), 1);
	}

	.hl-science {
		background: rgba(200, 50, 50, 0.15);
		color: rgb(180, 40, 40);
	}

	.hl-nature {
		background: rgba(40, 160, 80, 0.15);
		color: rgb(40, 140, 70);
	}

	.connector {
		display: flex;
		justify-content: center;
		margin: 4px 0;
		color: var(--color-text);
	}

	.sep {
		margin: 0 3px;
	}
</style>
