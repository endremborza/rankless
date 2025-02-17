import type { AttributeLabels } from './tree-types';

const AS_PATH = 'attribute-statics';
const LOCAL = false;
const LOCAL_LINK = 'http://0.0.0.0:8000';
export const STORE_URL = LOCAL
	? LOCAL_LINK
	: 'https://tmp-borza-public-cyx.s3.amazonaws.com/quercus-basis-v2024-06-26';

export function handleStore<T, R>(endPoint: string, fun: (o: T) => R) {
	let headers = { 'ngrok-skip-browser-warning': '1' };
	// let headers = {}
	return fetch(`${STORE_URL}/${endPoint.replace('+', '%2B')}.json.gz`, { headers }).then((res) => {
		return res
			.json()
			.then((jsv) => {
				return fun(jsv);
			})
			.catch((e) => {
				console.error('error ar', endPoint, e);
			});
	});
}

export function handleLabels(fun: (o: AttributeLabels) => void) {
	handleStore(AS_PATH, fun);
}
