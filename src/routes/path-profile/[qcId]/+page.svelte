<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';

	import PathLevelInfoBox from '$lib/components/PathLevelInfoBox.svelte';
	import { pathStrToPath } from '$lib/tree-functions';
	import type {
		AttributeLabels,
		PathInTree,
		QcSpec,
		SpecBaseOptions,
		WeightedNode
	} from '$lib/tree-types';
	import { handleStore, mainPreload } from '$lib/tree-loading';

	let attributeLabels: AttributeLabels;
	let qcSpec: QcSpec;
	let specBaselineOptions: SpecBaseOptions;
	let weightedRoot: WeightedNode;

	let selectedPath: PathInTree;
	let rootId: string | null;

	onMount(() => {
		mainPreload().then(([aLabels, allQcSpecs, baseOptions]) => {
			attributeLabels = aLabels;
			specBaselineOptions = baseOptions;
			qcSpec = allQcSpecs[$page.params.qcId];
		});
		rootId = $page.url.searchParams.get('r');

		if (rootId != null) {
			handleStore(`qc-builds/${$page.params.qcId}/${rootId}`, (obj: WeightedNode) => {
				weightedRoot = obj;
			});
		}
		selectedPath = pathStrToPath($page.url.searchParams.get('p') || '');
	});
</script>

{#if selectedPath != undefined && rootId != undefined && qcSpec != undefined && weightedRoot != undefined && specBaselineOptions != undefined && attributeLabels != undefined}
	<PathLevelInfoBox
		path={selectedPath}
		{weightedRoot}
		{specBaselineOptions}
		{attributeLabels}
		{qcSpec}
		{rootId}
		levelOfDetail={1}
	/>
{/if}
