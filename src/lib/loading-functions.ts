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
	treeRespCache: Record<string, tt.TreeResponse>;

	constructor(tops: tt.TopsResponse, treeSpecs: tt.TreeSpecs) {
		this.tops = tops;
		this.treeSpecs = treeSpecs;
		this.rootName = '';
		this.prefixText = '';
		this.conf = undefined;
		this.treeResp = undefined;
		this.treeRespCache = {}
	}

	async setTree(i: number, j: number, treeId: number) {
		let rootType = this.tops[i].name as tt.RootType;
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
		let url = tf.treeBeUrl(BE_URL, this.conf, 1)
		if (this.treeRespCache[url] == undefined) {
			this.treeRespCache[url] = await fetch(url).then((res) => res.json());
		}
		this.treeResp = this.treeRespCache[url]
	}

	setRandTree() {
		let i = randN(this.tops.length);
		while (this.tops[i].entities.length === 0) { i = randN(this.tops.length) }
		let jLen = this.tops[i].entities.length
		let j = randN(jLen)
		let rootType = this.tops[i].name as tt.RootType;
		const treeCount = this.treeSpecs.specs[rootType].length;
		let tid = randN(treeCount)
		while (this.treeSpecs.specs[rootType][tid].breakdowns.length < 2) { tid = randN(treeCount) }
		return this.setTree(i, j, tid)
	}

	getTreeSvgProps() {
		if (this.conf == undefined || this.treeResp == undefined) return;
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

export function reconstructLoader(data: {
	tops: tt.TopsResponse,
	treeSpecs: tt.TreeSpecs,
	rootName: string,
	prefixText: string,
	conf: tt.FullTreeConfig | undefined,
	treeResp: tt.TreeResponse | undefined,
	treeRespCache: Record<string, tt.TreeResponse>
}
): TopTreeLoader {
	const loader = new TopTreeLoader(data.tops, data.treeSpecs);
	loader.rootName = data.rootName;
	loader.prefixText = data.prefixText;
	loader.conf = data.conf;
	loader.treeResp = data.treeResp;
	loader.treeRespCache = data.treeRespCache;
	return loader
}
