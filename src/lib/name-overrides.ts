import type { View, AttributeLabels, EntityPeersResp } from '$lib/tree-types';

// Manual display-name fixes for entities whose OpenAlex `display_name` is stored in the wrong
// script/language (e.g. Elinor Ostrom is held upstream as "Элинор Остром"). Keyed by the exact
// backend string so `fixName` can be dropped in at any render site without needing the entity's
// id. Drop an entry once OpenAlex corrects the source name.
const NAME_OVERRIDES: Record<string, string> = {
	'Элинор Остром': 'Elinor Ostrom',
	'Albert-Ĺaszló Barabási': 'Albert-László Barabási'
};

export function fixName(name: string): string {
	return NAME_OVERRIDES[name] ?? name;
}

// Rewrite every name a View surfaces: the entity itself, its hero "leader"/co-author relations
// (which also feed the co-authorship network), and its "similar entities" list.
export function fixViewNames(view: View): void {
	view.name = fixName(view.name);
	for (const rels of Object.values(view.relations ?? {})) {
		for (const r of rels ?? []) r.name = fixName(r.name);
	}
	for (const s of view.similars ?? []) s.name = fixName(s.name);
}

// Tree node labels — e.g. an institution or country broken down by its authors.
export function fixAttNames(atts: AttributeLabels): void {
	for (const labels of Object.values(atts ?? {})) {
		for (const label of Object.values(labels)) label.name = fixName(label.name);
	}
}

// Peer-comparison names (the hero and each peer entry).
export function fixPeerNames(peers: EntityPeersResp): void {
	peers.hero.name = fixName(peers.hero.name);
	for (const p of peers.peers) p.name = fixName(p.name);
}
