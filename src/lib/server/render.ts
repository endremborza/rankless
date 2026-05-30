type SsrRenderable = { render: (props?: Record<string, unknown>) => { html: string } };

export function renderSvgComponent(component: unknown, props: Record<string, unknown>): string {
	return (component as SsrRenderable).render(props).html;
}
