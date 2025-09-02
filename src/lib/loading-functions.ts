import { BE_URL } from '$lib/constants';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { SEMANTIC_CONF } from '$lib/text-format-util';
import { randN } from './util';


export async function loadSpecs(): Promise<tt.TreeSpecs> {
	return fetch(`${BE_URL}/specs`)
		.then((res) => res.json())
		.then((specs: tt.TreeSpecs) => {
			//possible quick fixes in specs
			for (let nonSpecRt of ['sources', 'subfields']) {
				for (let i = 0; i < specs.specs[nonSpecRt as tt.RootType].length; i++) {
					specs.specs[nonSpecRt as tt.RootType][i].defaultIsSpec = false;
				}
			}
			return specs
		});
}


export async function loadTops(): Promise<tt.TopsResponse> { return fetch(`${BE_URL}/tops`).then((res) => res.json()); }


export class TopTreeLoader {
	tops: tt.TopsResponse;
	treeSpecs: tt.TreeSpecs;
	rootName: string;
	prefixText: string;
	conf: tt.FullTreeConfig | undefined;
	treeResp: tt.TreeResponse | undefined;
	treeRespCache: Record<string, tt.TreeResponse>
	cachedIdxs: [number, number][];

	constructor(tops: tt.TopsResponse, treeSpecs: tt.TreeSpecs) {
		this.tops = tops;
		this.treeSpecs = treeSpecs;
		this.rootName = '';
		this.prefixText = '';
		this.conf = undefined;
		this.treeResp = undefined;
		this.treeRespCache = {}
		this.cachedIdxs = []
	}

	async setTree(ri: number, rj: number) {
		let i = ri % this.tops.length
		let jLen = this.tops[i].entities.length
		if (jLen == 0) return
		let j = rj % jLen;
		let rootType = this.tops[i].name as tt.RootType;
		this.rootName = this.tops[i].entities[j].name;
		this.prefixText = SEMANTIC_CONF[rootType]?.start || '';
		const year = tf.getDefaultYear(rootType);
		const treeCount = this.treeSpecs.specs[rootType].length;
		this.conf = {
			semanticId: this.tops[i].entities[j].semanticId,
			year,
			treeId: Math.floor(Math.random() * treeCount),
			rootType,
			wide: false
		};
		let url = tf.treeBeUrl(BE_URL, this.conf, 1)
		if (this.treeRespCache[url] == undefined) {
			this.treeRespCache[url] = await fetch(url).then((res) => res.json());
			this.cachedIdxs.push([i, j]);
		}
		this.treeResp = this.treeRespCache[url]
	}

	setRandTree() {
		return this.setTree(randN(this.tops.length), randN(10000))
	}

	getTreeSvgProps() {
		while (this.conf == undefined || this.treeResp == undefined) this.setRandTree();
		const { tree, atts } = this.treeResp;
		let rootType = this.conf.rootType as tt.RootType;
		let treeSpec: tt.TreeSpec = this.treeSpecs.specs[rootType][this.conf.treeId];
		return { treeSpec, tree, attributeLabels: atts, rootName: this.rootName };

	}
}

export async function getTopTreeLoader(): Promise<TopTreeLoader> {
	const treeSpecs = await loadSpecs();
	const tops = await loadTops();
	const loader = new TopTreeLoader(tops, treeSpecs);
	return loader
}

export function reconstructLoader(treeSpecs: tt.TreeSpecs, tops: tt.TopsResponse, cache: Record<string, tt.TreeResponse>): TopTreeLoader {
	const loader = new TopTreeLoader(tops, treeSpecs);
	loader.treeRespCache = cache
	return loader
}
