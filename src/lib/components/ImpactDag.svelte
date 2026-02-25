<script lang="ts">
	import type { RefTree } from '$lib/tree-types';

	export let dag: RefTree;
	export let nameMap: Record<string, string>;
	export let doiMap: Record<string, string>;
	export let hitWids: number[];

	type NodeMeta = { level: number; parents: Set<number>; children: Set<number> };
	type SeenMap = Record<number, NodeMeta>;

	function build(node: RefTree, seen: SeenMap, depth: number, parent: number) {
		if (node === 'Leaf') return;
		for (const key of Object.keys(node.Node).map(Number)) {
			if (seen[key] == undefined || seen[key].level > depth) {
				seen[key] = { level: depth, parents: new Set(), children: new Set() };
			}
			if (depth === seen[key].level) {
				seen[key].parents.add(parent);
				if (parent !== 0) {
					(seen[parent] ??= { level: depth - 1, parents: new Set(), children: new Set() }).children.add(key);
				}
			}
			build(node.Node[key], seen, depth + 1, key);
		}
	}

	function computeSeen(t: RefTree): SeenMap {
		const seen: SeenMap = {};
		build(t, seen, 0, 0);
		// backfill children from parents
		for (const [kStr, meta] of Object.entries(seen)) {
			const k = Number(kStr);
			for (const p of meta.parents) {
				if (p !== 0 && seen[p]) seen[p].children.add(k);
			}
		}
		return seen;
	}

	function getLevels(seen: SeenMap): number[][] {
		const levels: number[][] = [];
		for (const [k, v] of Object.entries(seen)) {
			const d = v.level;
			if (!levels[d]) levels[d] = [];
			levels[d].push(Number(k));
		}
		return levels;
	}

	const hitSet = new Set(hitWids);

	const levelLabels = [
		'High-Impact Papers Citing This Author',
		"Author's Papers",
		"Author's Papers (Once Removed)",
		"Author's Papers",
	];

	let hovered: number | undefined;

	$: seen = computeSeen(dag);
	$: levels = getLevels(seen);
	$: relatedSet = (() => {
		if (hovered == undefined) return new Set<number>();
		const meta = seen[hovered];
		if (!meta) return new Set<number>();
		const s = new Set<number>();
		meta.parents.forEach((p) => { if (p !== 0) s.add(p); });
		meta.children.forEach((c) => s.add(c));
		return s;
	})();
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<div class="impact-dag">
	<div class="legend">
		<span class="dot hit" />
		<span class="legend-label">High-impact citing paper</span>
		<span class="dot author" />
		<span class="legend-label">Author's work</span>
	</div>

	{#each levels as level, i}
		<div class="level-section">
			<h4 class="level-label">{levelLabels[i] ?? "Author's Papers"}</h4>
			<div class="chips">
				{#each level as wid}
					{@const isHit = hitSet.has(wid)}
					{@const isHovered = hovered === wid}
					{@const isRelated = relatedSet.has(wid)}
					{@const title = nameMap[wid] ?? nameMap[String(wid)] ?? '(unknown)'}
					{@const doi = doiMap[wid] ?? doiMap[String(wid)]}
					<div
						class="chip"
						class:hit={isHit}
						class:author={!isHit}
						class:is-hovered={isHovered}
						class:is-related={isRelated}
						on:mouseover={() => { hovered = wid; }}
						on:mouseleave={() => { hovered = undefined; }}
					>
						{#if doi}
							<a href="https://doi.org/{doi}" target="_blank" rel="noopener">{title}</a>
						{:else}
							<span>{title}</span>
						{/if}
					</div>
				{/each}
			</div>
		</div>
		{#if i < levels.length - 1}
			<div class="connector" aria-hidden="true">↓</div>
		{/if}
	{/each}
</div>

<style>
	.impact-dag {
		display: flex;
		flex-direction: column;
		gap: 0;
	}

	.legend {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 20px;
		font-size: 0.75rem;
		opacity: 0.75;
	}

	.dot {
		display: inline-block;
		width: 10px;
		height: 10px;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.dot.hit {
		background: rgba(var(--color-range-80), 1);
	}

	.dot.author {
		background: var(--color-theme-blue);
	}

	.legend-label {
		margin-right: 12px;
	}

	.level-section {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.level-label {
		margin: 0;
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		opacity: 0.55;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
		padding-bottom: 4px;
	}

	.chip {
		padding: 7px 11px;
		font-size: 0.75rem;
		line-height: 1.35;
		border-radius: 3px;
		border: 1.5px solid transparent;
		flex: 1 0 160px;
		max-width: 300px;
		box-sizing: border-box;
		transition: border-color 160ms, background-color 160ms, opacity 160ms;
		cursor: default;
	}

	.chip a {
		text-decoration: none;
		color: inherit;
	}

	.chip a:hover {
		text-decoration: underline;
	}

	.chip.hit {
		background-color: rgba(var(--color-range-80), 0.1);
		border-color: rgba(var(--color-range-80), 0.4);
	}

	.chip.author {
		background-color: rgba(var(--color-range-15), 0.08);
		border-color: rgba(var(--color-range-15), 0.25);
	}

	.chip.is-hovered {
		border-color: var(--color-theme-blue);
		box-shadow: 0 0 0 1px var(--color-theme-blue);
	}

	.chip.hit.is-hovered {
		border-color: rgba(var(--color-range-80), 1);
		box-shadow: 0 0 0 1px rgba(var(--color-range-80), 1);
	}

	.chip.is-related {
		border-color: var(--color-theme-blue);
		background-color: rgba(var(--color-range-15), 0.2);
	}

	.chip.hit.is-related {
		border-color: rgba(var(--color-range-80), 1);
		background-color: rgba(var(--color-range-80), 0.2);
	}

	.connector {
		text-align: center;
		font-size: 1.2rem;
		opacity: 0.3;
		margin: 6px 0;
		user-select: none;
	}
</style>
