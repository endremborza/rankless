
import type { InteractionKind, TreeInteractionEvent, IndexEvent, PathInTree } from '$lib/tree-types';

import { createEventDispatcher, type EventDispatcher } from 'svelte';

type EventMap = { 'ti': TreeInteractionEvent, 'ce': IndexEvent };
type Dispatcher = EventDispatcher<EventMap>;


export function getDispatch() {
    return createEventDispatcher<EventMap>();
}


export function treeInteract(dispatch: Dispatcher, action: InteractionKind, path: PathInTree, x: number, y: number) {
    return () => {
        dispatch('ti', {
            path,
            action,
            topLeftCorner: { x, y }
        });
    };
}

export function expandThis(dispatch: Dispatcher, ind: number) {
    return () => {
        dispatch('ce', { ind });
    };
}

