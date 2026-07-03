import { error, fail } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { isAdmin } from '$lib/server/admin';
import {
	createSession,
	deleteSession,
	isValidName,
	listSessions,
	setVisibility
} from '$lib/server/mcp-sessions';
import type { SessionParams, SessionVisibility } from '$lib/types/mcp';

const FOCI = ['share', 'query', 'data-issue'];

function requireAdmin(locals: App.Locals): void {
	if (!isAdmin(locals.user?.orcid)) error(403, 'Admins only');
}

// One page for everyone: the public sees public, finished sessions; admins see
// all of them plus the queue/edit controls (gated per-action below).
export const load: PageServerLoad = ({ locals }) => ({
	sessions: listSessions({ publicOnly: !isAdmin(locals.user?.orcid) })
});

export const actions: Actions = {
	create: async ({ request, locals }) => {
		requireAdmin(locals);
		const form = await request.formData();
		const backend = String(form.get('backend') ?? 'live');
		const foci = form
			.getAll('foci')
			.map(String)
			.filter((f) => FOCI.includes(f));
		if (!foci.length) return fail(400, { message: 'Pick at least one focus.' });
		if (backend !== 'local' && backend !== 'live' && !backend.startsWith('http'))
			return fail(400, { message: 'Backend must be local, live, or an http(s) URL.' });

		const params: SessionParams = {
			backend,
			foci,
			subject: str(form.get('subject')),
			question: str(form.get('question')),
			investigate: str(form.get('investigate')),
			model: str(form.get('model')),
			suggestEndpoints: form.get('suggestEndpoints') !== 'off'
		};
		const name = genName(params);
		createSession({
			name,
			orcid: locals.user!.orcid,
			params,
			visibility: (form.get('visibility') as SessionVisibility) ?? 'private'
		});
		return { created: name };
	},

	visibility: async ({ request, locals }) => {
		requireAdmin(locals);
		const form = await request.formData();
		const name = String(form.get('name') ?? '');
		const visibility = form.get('visibility') === 'public' ? 'public' : 'private';
		if (!isValidName(name)) return fail(400, { message: 'Bad session name.' });
		setVisibility(name, visibility);
		return { updated: name };
	},

	delete: async ({ request, locals }) => {
		requireAdmin(locals);
		const name = String((await request.formData()).get('name') ?? '');
		if (!isValidName(name)) return fail(400, { message: 'Bad session name.' });
		deleteSession(name);
		return { deleted: name };
	}
};

function str(v: FormDataEntryValue | null): string | null {
	const s = v ? String(v).trim() : '';
	return s || null;
}

// Slug from the round's subject/question + a short unique suffix.
function genName(p: SessionParams): string {
	const base = (p.subject || p.question || p.investigate || p.foci.join('-'))
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '')
		.slice(0, 40);
	const suffix = Date.now().toString(36).slice(-5);
	return `${base || 'run'}-${suffix}`;
}
