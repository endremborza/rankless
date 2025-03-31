import type * as tt from '$lib/tree-types';
import { BE_URL } from '$lib/constants';

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

