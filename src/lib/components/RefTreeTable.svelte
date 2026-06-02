<script lang="ts">
	import type { RefTree } from '$lib/tree-types';

	export let tree: RefTree;
	export let nameMap: Record<number, string>;
	export let doiMap: Record<number, string>;
	export let relWorks: number[];

	type SeenEntry = { level: number; parents: Set<number> };
	type Seen = Record<number, SeenEntry>;

	function filler(node: RefTree, seen: Seen, depth: number, parent: number) {
		if (node === 'Leaf') return;
		for (const key of Object.keys(node.Node).map(Number)) {
			const existing = seen[key];
			if (existing == undefined || existing.level > depth) {
				seen[key] = { level: depth, parents: new Set() };
			}
			if (depth == seen[key].level) {
				seen[key].parents.add(parent);
			}
			filler(node.Node[key], seen, depth + 1, key);
		}
	}

	function getSeen(t: RefTree): Seen {
		const seen: Seen = {};
		filler(t, seen, 0, 0);
		return seen;
	}

	function getLevels(seen: Seen): { k: number }[][] {
		const levels: { k: number }[][] = [];
		for (const [k, v] of Object.entries(seen)) {
			const d = v.level;
			if (levels[d] == undefined) levels[d] = [];
			levels[d].push({ k: Number(k) });
		}
		return levels;
	}

	function getClass(k: number, rel: number[], hl: Set<number>): string {
		const classes = [];
		if (rel.includes(k)) classes.push('relevant');
		if (hl.has(k)) classes.push('highlighted');
		return classes.join(' ');
	}

	const levelDescs = [
		'Directly Cited',
		'Cited by Directly Cited',
		'Cited by Above',
		'Cited by Above'
	];

	let highlighted: number | undefined;
	$: seen = getSeen(tree);
	$: levels = getLevels(seen);
	$: highlightSet =
		(highlighted != undefined ? seen[highlighted]?.parents : undefined) || new Set<number>();
</script>

<!-- svelte-ignore a11y_mouse_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
{#each levels as level, i (i)}
	<h4>{levelDescs[i] ?? 'Cited by Above'}</h4>
	<div class="level">
		{#each level as { k }, __i (__i)}
			<div
				class="paper {getClass(k, relWorks, highlightSet)}"
				on:mouseover={() => {
					highlighted = k;
				}}
				on:mouseleave={() => {
					highlighted = undefined;
				}}
			>
				{#if doiMap[k] != undefined}
					<a href="https://doi.org/{doiMap[k]}">{nameMap[k]}</a>
				{:else}
					<span>{nameMap[k]}</span>
				{/if}
			</div>
		{/each}
	</div>
{/each}

<style>
	.level {
		margin-bottom: 20px;
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		padding: 4px;
		border-bottom: solid 1px var(--color-theme-blue);
	}

	.paper {
		border: solid transparent 1px;
		max-width: 280px;
		font-size: var(--text-sm);
		padding: 6px;
		flex: 1 0 200px;
		box-sizing: border-box;
		transition: background-color 200ms;
	}

	.relevant {
		background-color: rgba(var(--color-range-15), 0.25);
	}

	.highlighted {
		border-color: var(--color-theme-blue);
	}

	h4 {
		margin: 12px 0 4px;
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		opacity: 0.6;
	}
</style>
