<script lang="ts">
	import { SEMANTIC_CONF, eTypeFromBdDesc, prettifyRoot, semantify } from '$lib/text-format-util';
	import { getBreakdownOptions, getDefaultYear, toLinkWithParams } from '$lib/tree-functions';
	import type { RootType, TreeSpecs } from '$lib/tree-types';

	export let name: string;
	export let semanticId: string;
	export let rootType: RootType;
	export let treeSpecs: TreeSpecs;

	function getSem(treeId: number, rootType: RootType, treeSpecs: TreeSpecs) {
		let bops = getBreakdownOptions(treeSpecs, rootType);
		let bop = '';
		for (const [k, v] of Object.entries(bops)) {
			if (v.treeSpecs.includes(treeId)) {
				bop = k;
				break;
			}
		}
		let suff = semantify(bop, rootType, [], 0);
		let pref = '';
		if (suff.startsWith('are')) {
			pref = 'impacted by ';
			suff = '';
		} else {
			suff = ' are ' + suff;
		}

		let ent = prettifyRoot(eTypeFromBdDesc(bop));
		return { ent, suff, pref };
	}

	// $: treeId = Math.floor(Math.random() * treeSpecs.specs[rootType].length);
	let treeId = 0;
	$: conf = { year: getDefaultYear(rootType), treeId, semanticId, rootType };

	$: href = toLinkWithParams(conf, {});
	$: sem = getSem(treeId, rootType, treeSpecs);
	$: pref = SEMANTIC_CONF[rootType].start;
</script>

<a {href}>Breakdown of academic impact, for {pref.toLowerCase()} <b>{name}</b></a>
