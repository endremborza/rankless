import { TREE_SPECS, type TopResult } from '$lib/wire/rankless_server/responses';
import type { TreeResponse, TreeSpec } from '$lib/wire/rankless_trees/io';
import { BE_URL } from '$lib/constants';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { SEMANTIC_CONF } from '$lib/text-format-util';
import { randN } from './util';

export async function loadTops(fetchFn: typeof fetch = fetch): Promise<TopResult[]> {
	return fetchFn(`${BE_URL}/tops`).then((res) => res.json());
}

export class TopTreeLoader {
	tops: TopResult[];
	rootName: string;
	prefixText: string;
	conf: tt.FullTreeConfig | undefined;
	treeResp: TreeResponse | undefined;
	treeRespCache: Record<string, TreeResponse>;

	constructor(tops: TopResult[]) {
		this.tops = tops;
		this.rootName = '';
		this.prefixText = '';
		this.conf = undefined;
		this.treeResp = undefined;
		this.treeRespCache = {};
	}

	async setTree(i: number, j: number, treeId: number, fetchFn: typeof fetch = fetch) {
		const rootType = this.tops[i].name as tt.RootType;
		this.rootName = this.tops[i].entities[j].name;
		this.prefixText = SEMANTIC_CONF[rootType]?.start || '';
		const year = tf.getDefaultYear(rootType);
		this.conf = {
			semanticId: this.tops[i].entities[j].semanticId,
			year,
			treeId,
			rootType,
			wide: false
		};
		const url = tf.treeBeUrl(BE_URL, this.conf, 1);
		if (this.treeRespCache[url] == undefined) {
			this.treeRespCache[url] = await fetchFn(url).then((res) => res.json());
		}
		this.treeResp = this.treeRespCache[url];
	}

	setRandTree(fetchFn: typeof fetch = fetch) {
		let i = randN(this.tops.length);
		while (this.tops[i].entities.length === 0) {
			i = randN(this.tops.length);
		}
		const jLen = this.tops[i].entities.length;
		const j = randN(jLen);
		const rootType = this.tops[i].name as tt.RootType;
		const treeCount = TREE_SPECS.specs[rootType].length;
		let tid = randN(treeCount);
		while (TREE_SPECS.specs[rootType][tid].breakdowns.length < 2) {
			tid = randN(treeCount);
		}
		return this.setTree(i, j, tid, fetchFn);
	}

	getTreeSvgProps() {
		if (this.conf == undefined || this.treeResp == undefined) return;
		const { tree, atts } = this.treeResp;
		const rootType = this.conf.rootType as tt.RootType;
		const treeSpec: TreeSpec = TREE_SPECS.specs[rootType][this.conf.treeId];
		return { treeSpec, tree, attributeLabels: atts, rootName: this.rootName };
	}
}

export async function getTopTreeLoader(fetchFn: typeof fetch = fetch): Promise<TopTreeLoader> {
	return new TopTreeLoader(await loadTops(fetchFn));
}

export function reconstructLoader(data: {
	tops: TopResult[];
	rootName: string;
	prefixText: string;
	conf: tt.FullTreeConfig | undefined;
	treeResp: TreeResponse | undefined;
	treeRespCache: Record<string, TreeResponse>;
}): TopTreeLoader {
	const loader = new TopTreeLoader(data.tops);
	loader.rootName = data.rootName;
	loader.prefixText = data.prefixText;
	loader.conf = data.conf;
	loader.treeResp = data.treeResp;
	loader.treeRespCache = data.treeRespCache;
	return loader;
}
