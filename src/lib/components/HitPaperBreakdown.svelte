<script lang="ts">
	import { BE_REMOTE_URL } from '$lib/constants';
	import type { TreeResponse, NamedNode, AttributeLabels, TreeSpec } from '$lib/tree-types';
	import { urlFriendlify, flatFromResp } from '$lib/tree-functions';
	import TileTreeMap from './TileTreeMap.svelte';

	export let semanticId: string;
	export let treeId = 0;
	export let isSpec = false;
	export let treeSpec: TreeSpec | undefined = undefined;
	export let aspectRatio: number = 3;

	let treeData: NamedNode | null = null;
	let loading = false;
	let entityLabel = '';
	let width = 400;

	$: loadBreakdown(semanticId, treeId, isSpec);
	$: height = width / aspectRatio;

	async function loadBreakdown(semId: string, tid: number, spec: boolean) {
		if (!semId) return;
		loading = true;
		treeData = null;
		entityLabel = '';
		try {
			const resp: TreeResponse = await fetch(
				`${BE_REMOTE_URL}/trees/hit-papers/${urlFriendlify(semId)}?tid=${tid}&year=0&shallow=1`
			)
				.then((r) => r.json())
				.catch(() => null);
			if (!resp?.tree) return;
			treeData = buildNamedNode(resp, spec);
		} finally {
			loading = false;
		}
	}

	function inferEntityType(childIds: string[], atts: AttributeLabels): string | null {
		if (!childIds.length) return null;
		const firstId = childIds[0];
		for (const [etype, typeAtts] of Object.entries(atts)) {
			if ((typeAtts as Record<string, unknown>)[firstId] !== undefined) return etype;
		}
		return null;
	}

	function buildNamedNode(resp: TreeResponse, spec: boolean): NamedNode | null {
		const { tree, atts } = resp;
		const childEntries = Object.entries(tree.children ?? {});
		if (!childEntries.length) return null;
		const childIds = childEntries.map(([id]) => id);
		const etype = inferEntityType(childIds, atts);
		const typeAtts = etype ? (atts[etype as keyof typeof atts] ?? {}) : {};
		entityLabel = etype ?? '';

		if (spec && treeSpec) {
			const flat = flatFromResp(resp, true, treeSpec);
			if (flat) {
				const children: Record<string, NamedNode> = {};
				for (const [id, { w }] of Object.entries(flat)) {
					const name = (typeAtts as Record<string, { name: string }>)[id]?.name ?? id;
					children[id] = { weight: w, name };
				}
				const totalW = Object.values(children).reduce((s, c) => s + c.weight, 0);
				return { weight: totalW, name: '', children };
			}
		}

		const children: Record<string, NamedNode> = {};
		for (const [id, child] of childEntries) {
			const name = (typeAtts as Record<string, { name: string }>)[id]?.name ?? id;
			children[id] = { weight: child.linkCount, name };
		}
		return { weight: tree.linkCount, name: '', children };
	}
</script>

{#if loading}
	<div class="breakdown-loading">loading...</div>
{:else if treeData}
	<div class="breakdown">
		{#if entityLabel}
			<span class="breakdown-label">citing {entityLabel}</span>
		{/if}
		<svg viewBox="0 0 {width} {height}" class="breakdown-svg">
			<TileTreeMap data={treeData} {width} {height} maxPad={3} showText />
		</svg>
	</div>
{/if}

<style>
	.breakdown {
		display: flex;
		flex-direction: column;
		gap: 4px;
		flex: 1;
		min-height: 0;
	}

	.breakdown-label {
		font-size: var(--text-xs);
		opacity: 0.45;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.breakdown-svg {
		width: 100%;
		flex: 1;
		min-height: 0;
		border-radius: 2px;
		overflow: hidden;
	}

	.breakdown-loading {
		font-size: var(--text-xs);
		opacity: 0.35;
		padding: 6px 0;
	}
</style>
