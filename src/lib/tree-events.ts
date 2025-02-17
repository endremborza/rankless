import type { InteractionKind, TreeInteractionEvent, PathInTree } from '$lib/tree-types';

import type { EventDispatcher } from 'svelte';

export type EventMap = { ti: TreeInteractionEvent };
type Dispatcher = EventDispatcher<EventMap>;

export function treeInteract(
	dispatch: Dispatcher,
	action: InteractionKind,
	path: PathInTree,
	x: number,
	y: number
) {
	return () => {
		dispatch('ti', {
			path,
			action,
			topLeftCorner: { x, y }
		});
	};
}
