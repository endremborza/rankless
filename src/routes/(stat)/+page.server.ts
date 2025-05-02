import type { PageServerLoad } from './$types';
import { BE_URL } from '$lib/constants';
import type { TopsResponse } from '$lib/tree-types';
import { loadSpecs } from '$lib/loading-functions';
import { SEMANTIC_CONF } from '$lib/text-format-util';
import { getDefaultYear, treeBeUrl } from '$lib/tree-functions';

export const load: PageServerLoad = async () => {

	const treeSpecs = await loadSpecs();

	const tops: TopsResponse = await fetch(`${BE_URL}/tops`)
		.then((res) => res.json())
		.then((c) => c);

	let rootType = tops[0].name;
	let rootName =
		SEMANTIC_CONF[rootType]?.start || '';
	let year = getDefaultYear(rootType);
	let treeCount = treeSpecs.specs[rootType].length;
	let conf = {
		semanticId: tops[0].entities[0].semanticId,
		year,
		treeId: Math.floor(Math.random() * treeCount),
		rootType
	};

	const treeResp = await
		fetch(treeBeUrl(BE_URL, conf, 1))
			.then((res) => res.json());

	return { tops, treeSpecs, conf, treeResp, rootName };
};

export const ssr = true;
