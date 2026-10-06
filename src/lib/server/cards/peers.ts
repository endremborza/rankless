import type { EntityPeersResp } from '$lib/wire/rankless_server/responses';
import { error } from '@sveltejs/kit';
import type { ShowcasePeers } from '$lib/types/showcase';
import { BE_URL, LATEST_YEAR } from '$lib/constants';
import { encodeSemanticId } from '$lib/tree-functions';
import { fixName } from '$lib/name-overrides';
import { htmlToText } from '$lib/utils/paper-helpers';
import PeersCard from '$lib/components/cards/PeersCard.svelte';
import { beJson, CARD_SPEC, idsParam, intParam, type CardKind } from './kind';

const P = CARD_SPEC.peers.params;

// The entity against one of its peers (`hl`, default the closest): citations in its top `n`
// fields and per year, side by side.
export const peers: CardKind = {
	component: PeersCard,
	async load({ rootType, semanticId, params, view, fetch }) {
		if (!view) error(404, 'no such card');
		const n = intParam(params, 'n', P.n.default, 1, P.n.max);
		const [hl] = idsParam(params, 'hl', P.hl.max);
		const resp = await beJson<EntityPeersResp>(
			fetch,
			`${BE_URL}/peers/${rootType}/${encodeSemanticId(semanticId)}`
		);
		const peer = hl ? resp.peers.find((p) => p.semanticId === hl) : resp.peers[0];
		if (!peer) error(404, 'no such peer');
		const props: ShowcasePeers = {
			heroName: displayName(resp.hero.name),
			peerName: displayName(peer.name),
			peerCountry: rootType === 'countries' ? null : peer.country,
			subfields: resp.topSubfields.slice(0, n).map((sf, i) => ({
				name: sf.name,
				hero: resp.hero.subfieldCitations[i] ?? 0,
				peer: peer.subfieldCitations[i] ?? 0
			})),
			yearFrom: LATEST_YEAR - (resp.hero.yearlyCites.length - 1),
			heroYearly: resp.hero.yearlyCites,
			peerYearly: peer.yearlyCites
		};
		return { props, caption: peersCaption(props.subfields.length) };
	}
};

function peersCaption(nFields: number): string {
	const fields = nFields === 1 ? 'top field' : `top ${nFields} fields`;
	return `Citations in the ${fields} and per year, against a peer of similar size and profile`;
}

function displayName(name: string): string {
	return htmlToText(fixName(name));
}
