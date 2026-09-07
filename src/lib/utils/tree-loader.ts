import { writable } from 'svelte/store';
import { BE_REMOTE_URL } from '$lib/constants';
import type { FullTreeConfig, TreeResponse } from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { createStaleGuard } from '$lib/utils/stale-guard';

export type TreeFetch = (conf: FullTreeConfig, shallow?: number) => Promise<TreeResponse>;

export type TreeState = {
	conf: FullTreeConfig | undefined;
	resp: TreeResponse | undefined;
	loading: boolean;
	error: unknown;
};

const backendFetch: TreeFetch = (conf, shallow) => tf.fetchTree(BE_REMOTE_URL, conf, shallow);

// One tree at a time per component: a request superseded by a newer `load` is dropped on arrival, so
// rapid spec/year changes cannot clobber the current tree. `load` resolves to the response only while
// it is still the current one, letting the caller apply it in place; `$state` carries the last applied
// conf/response, the in-flight flag and the last failure.
export function createTreeLoader(fetchTree: TreeFetch = backendFetch) {
	const store = writable<TreeState>({
		conf: undefined,
		resp: undefined,
		loading: false,
		error: undefined
	});
	const claim = createStaleGuard();

	async function load(conf: FullTreeConfig, shallow?: number): Promise<TreeResponse | undefined> {
		const isCurrent = claim();
		store.update((s) => ({ ...s, loading: true, error: undefined }));
		try {
			const resp = await fetchTree(conf, shallow);
			if (!isCurrent()) return undefined;
			store.set({ conf: { ...conf }, resp, loading: false, error: undefined });
			return resp;
		} catch (e) {
			if (!isCurrent()) return undefined;
			console.error('tree fetch failed', e);
			store.update((s) => ({ ...s, loading: false, error: e }));
			return undefined;
		}
	}

	return { subscribe: store.subscribe, load };
}

export type TreeLoader = ReturnType<typeof createTreeLoader>;
