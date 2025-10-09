<script lang="ts">
	import type { RefTree } from '$lib/tree-types';
	export let tree: RefTree;
	export let nameMap: Record<number, string>;
	export let doiMap: Record<number, string>;
	export let relWorks: number[];

	type Seen = Record<number, { level: number; parents: Set<number> }>;

	function filler(node: RefTree, seen: Seen, depth: number, parent: number) {
		if (node === 'Leaf') return;
		for (const key of Object.keys(node.Node).map(Number)) {
			let seen_v = seen[key];
			if (seen_v == undefined || seen_v.level > depth) {
				seen[key] = {
					level: depth,
					parents: new Set()
				};
			}
			if (depth == seen[key].level) {
				seen[key].parents.add(parent);
			}
			filler(node.Node[key], seen, depth + 1, key);
		}
	}
	function getSeen(tree: RefTree) {
		let seen: Seen = {};
		filler(tree, seen, 0, 0);
		return seen;
	}
	function getLevels(seen: Seen) {
		let levels: { k: number }[][] = [];
		for (const [k, v] of Object.entries(seen)) {
			let d = v.level;
			if (levels[d] == undefined) levels[d] = [];
			levels[d].push({ k: parseInt(k) });
		}
		return levels;
	}
	function getClass(k: number, relWorks: number[], highlightSet: Set<number>) {
		let classes = [];
		let ki = k;
		if (relWorks.includes(ki)) classes.push('relevant');
		if (highlightSet.has(ki)) classes.push('highlighted');
		return classes.join(' ');
	}
	$: seen = getSeen(tree);
	$: levels = getLevels(seen);
	$: highlightSet = seen[highlighted || 0]?.parents || new Set();
	let highlighted: undefined | number;
	console.log(tree);
</script>

<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
{#each levels as level}
	<div class="level">
		{#each level as { k }}
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
		box-sizing: border-box;
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		padding: 4px;
		border-bottom: solid pink 1px;
	}

	.paper {
		border: solid transparent 1px;
		max-width: 280px;
		font-size: 0.6rem;
		padding: 4px;
		flex: 1 0 200px;
		vertical-align: middle;
		box-sizing: border-box;
	}

	.relevant {
		background-color: var(--text-bg-3);
	}

	.highlighted {
		border-color: var(--accent-text);
	}
</style>
