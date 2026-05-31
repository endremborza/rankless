import { render } from 'svelte/server';
import type { Component } from 'svelte';

// Generic SSR bridge: takes any component plus the loosely-typed props the .svg endpoints
// build (which don't line up with a specific component type) and renders an HTML body string.
export function renderSvgComponent(component: unknown, props: Record<string, unknown>): string {
	return render(component as Component<Record<string, unknown>>, { props }).body;
}
