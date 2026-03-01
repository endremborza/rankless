import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';

export function authedPaperAction<T>(
	extract: (body: Record<string, unknown>) => T | null,
	action: (orcid: string, value: T) => void
) {
	return async ({ locals, request }: RequestEvent) => {
		if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
		const body = await request.json();
		const value = extract(body);
		if (value === null) return json({ error: 'Invalid input' }, { status: 400 });
		action(locals.user.orcid, value);
		return json({ ok: true });
	};
}
