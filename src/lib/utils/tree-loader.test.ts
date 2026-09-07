import { describe, it, expect, vi } from 'vitest';
import { get } from 'svelte/store';
import type { FullTreeConfig, TreeResponse } from '$lib/tree-types';
import { createTreeLoader } from './tree-loader';

type Deferred = {
	promise: Promise<TreeResponse>;
	resolve: (r: TreeResponse) => void;
	reject: (e: unknown) => void;
};

function deferred(): Deferred {
	let resolve!: Deferred['resolve'];
	let reject!: Deferred['reject'];
	const promise = new Promise<TreeResponse>((res, rej) => {
		resolve = res;
		reject = rej;
	});
	return { promise, resolve, reject };
}

function conf(treeId: number): FullTreeConfig {
	return { year: 2000, treeId, rootType: 'authors', semanticId: 'a', wide: false };
}

function resp(tag: string): TreeResponse {
	return { tree: { name: tag }, atts: {}, shallowed: false } as unknown as TreeResponse;
}

function setup() {
	const calls: Deferred[] = [];
	const fetchTree = vi.fn(() => {
		const d = deferred();
		calls.push(d);
		return d.promise;
	});
	vi.spyOn(console, 'error').mockImplementation(() => {});
	return { loader: createTreeLoader(fetchTree), calls, fetchTree };
}

describe('createTreeLoader', () => {
	it('drops a superseded response that arrives after the current one', async () => {
		const { loader, calls, fetchTree } = setup();
		const first = loader.load(conf(1), 0);
		const second = loader.load(conf(2));
		expect(fetchTree).toHaveBeenNthCalledWith(1, conf(1), 0);
		expect(get(loader).loading).toBe(true);

		calls[1].resolve(resp('second'));
		expect(await second).toEqual(resp('second'));
		expect(get(loader)).toMatchObject({ conf: conf(2), resp: resp('second'), loading: false });

		calls[0].resolve(resp('first'));
		expect(await first).toBeUndefined();
		expect(get(loader).resp).toEqual(resp('second'));
	});

	it('stays in flight until the current fetch lands', async () => {
		const { loader, calls } = setup();
		const first = loader.load(conf(1));
		const second = loader.load(conf(2));

		calls[0].resolve(resp('first'));
		expect(await first).toBeUndefined();
		expect(get(loader)).toMatchObject({ resp: undefined, loading: true });

		calls[1].resolve(resp('second'));
		expect(await second).toEqual(resp('second'));
		expect(get(loader)).toMatchObject({ resp: resp('second'), loading: false });
	});

	it('keeps the previous tree when the current fetch fails', async () => {
		const { loader, calls } = setup();
		const first = loader.load(conf(1));
		calls[0].resolve(resp('first'));
		await first;

		const failing = loader.load(conf(2));
		calls[1].reject(new Error('boom'));
		expect(await failing).toBeUndefined();
		expect(get(loader)).toMatchObject({ conf: conf(1), resp: resp('first'), loading: false });
		expect(get(loader).error).toBeInstanceOf(Error);

		const stale = loader.load(conf(3));
		const current = loader.load(conf(4));
		calls[2].reject(new Error('late'));
		expect(await stale).toBeUndefined();
		expect(get(loader)).toMatchObject({ loading: true, error: undefined });
		calls[3].resolve(resp('fourth'));
		await current;
		expect(get(loader)).toMatchObject({ resp: resp('fourth'), loading: false });
	});
});
