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
import { listObjects, setObjectStatus } from '$lib/server/objects';
import { GENERATIONS, isGenerationParams, isGenerationType, runName } from '$lib/mcp-util';
import type { SessionParams, SessionVisibility } from '$lib/types/mcp';
import type { ObjectStatus } from '$lib/types/objects';

const OBJECT_STATUSES: ObjectStatus[] = ['new', 'approved', 'rejected'];

const FOCI = ['share', 'query', 'data-issue'];

function requireAdmin(locals: App.Locals): void {
	if (!isAdmin(locals.user?.orcid)) error(403, 'Admins only');
}

// One page for everyone: the public sees public, finished sessions and approved
// findings/stories; admins see everything plus the queue/edit/review controls
// (gated per-action below). Game cards never show publicly — they'd spoil the
// game.
export const load: PageServerLoad = ({ locals }) => {
	const admin = isAdmin(locals.user?.orcid);
	return {
		sessions: listSessions({ publicOnly: !admin }),
		objects: admin
			? listObjects({})
			: listObjects({ kinds: ['finding', 'impact-story'], statuses: ['approved'] })
	};
};

export const actions: Actions = {
	create: async ({ request, locals }) => {
		requireAdmin(locals);
		const form = await request.formData();
		const backend = String(form.get('backend') ?? 'live');
		if (backend !== 'local' && backend !== 'live' && !backend.startsWith('http'))
			return fail(400, { message: 'Backend must be local, live, or an http(s) URL.' });

		let params: SessionParams;
		const type = String(form.get('type') ?? 'deep');
		if (isGenerationType(type)) {
			const etype = String(form.get('etype') ?? 'institutions');
			const count = Number(form.get('count') ?? 24);
			if (!GENERATIONS[type].etypes.includes(etype))
				return fail(400, { message: `Bad entity type for ${type}.` });
			if (!Number.isInteger(count) || count < 1 || count > 100)
				return fail(400, { message: 'Count must be 1-100.' });
			params = { type, backend, etype, count, model: str(form.get('model')) };
		} else {
			const foci = form
				.getAll('foci')
				.map(String)
				.filter((f) => FOCI.includes(f));
			if (!foci.length) return fail(400, { message: 'Pick at least one focus.' });
			params = {
				backend,
				foci,
				subject: str(form.get('subject')),
				question: str(form.get('question')),
				investigate: str(form.get('investigate')),
				model: str(form.get('model')),
				suggestEndpoints: form.get('suggestEndpoints') !== 'off'
			};
		}
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
	},

	objectStatus: async ({ request, locals }) => {
		requireAdmin(locals);
		const form = await request.formData();
		const id = Number(form.get('id'));
		const status = String(form.get('status')) as ObjectStatus;
		const note = str(form.get('note'));
		if (!Number.isInteger(id) || !OBJECT_STATUSES.includes(status))
			return fail(400, { message: 'Bad object review input.' });
		if (status === 'rejected' && !note)
			return fail(400, { message: 'Rejecting needs a reason (kept for later review).' });
		if (!setObjectStatus(id, status, note)) return fail(404, { message: 'No such object.' });
		return { reviewed: id };
	}
};

function str(v: FormDataEntryValue | null): string | null {
	const s = v ? String(v).trim() : '';
	return s || null;
}

// Standard run name (<workflow>-<scope>-<UTC stamp>); a deep run's scope is a
// slug of its subject/question.
function genName(p: SessionParams): string {
	if (isGenerationParams(p)) return runName(p.type, p.etype);
	const base = (p.subject || p.question || p.investigate || p.foci.join('-'))
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, '-')
		.replace(/^-+|-+$/g, '')
		.slice(0, 40);
	return runName('deep', base || 'run');
}
