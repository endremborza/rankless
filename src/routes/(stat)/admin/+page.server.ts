import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { isAdmin } from '$lib/server/admin';
import { ConsentDb, LedgerDb, OrcidNameDb, SessionDb, UserDb } from '$lib/server/db';
import { resolveOrcidProfiles } from '$lib/server/id_resolver';
import { readManifest } from '$lib/server/manifest';
import type { EmailConsent } from '$lib/types/email-consent';

export const load: PageServerLoad = async ({ locals }) => {
	// 404 (not 403) so the page's existence stays hidden from non-admins.
	if (!isAdmin(locals.user?.orcid)) error(404, 'Not found');

	const manifest = readManifest();
	const applied = new Set(LedgerDb.getAllAppliedKeys());
	for (const k of manifest.applied_keys) applied.add(k);

	const online = SessionDb.activeOrcids();
	const consents = ConsentDb.listActiveConsents();
	const consentByOrcid = new Map<string, EmailConsent>(consents.map((c) => [c.orcid, c]));
	const activity = LedgerDb.listActorActivity();
	const activityByOrcid = new Map(activity.map((a) => [a.orcid, a]));
	const users = UserDb.listUsers();
	const userByOrcid = new Map(users.map((u) => [u.orcid, u]));

	// Everyone who has ever done anything: signed in (now or in the past), granted email
	// consent, or made a ledger change. A ledger actor or a consenter predating the users
	// table may have no users row, so the login fields fall back to null.
	const allOrcids = new Set<string>([
		...online,
		...users.map((u) => u.orcid),
		...consents.map((c) => c.orcid),
		...activity.map((a) => a.orcid)
	]);

	// Resolve a display name + semantic_id (for a profile link) for every actor. Priority:
	// what they logged in with (users table) → a session → the backend author index. The
	// last one is what surfaces ledger-only actors (someone who acted but never logged in
	// here). A name and its semantic_id always travel together, from one source.
	const nameByOrcid = new Map<string, string>();
	const semByOrcid = new Map<string, string>();
	const note = (orcid: string, name: string | null, sem: string | null) => {
		if (name && sem && !nameByOrcid.has(orcid)) {
			nameByOrcid.set(orcid, name);
			semByOrcid.set(orcid, sem);
		} else if (name && !nameByOrcid.has(orcid)) {
			nameByOrcid.set(orcid, name);
		}
	};
	for (const u of users) note(u.orcid, u.name, u.semantic_id);
	for (const s of SessionDb.profilesByOrcid()) note(s.orcid, s.name, s.semantic_id);

	// Backend lookups go through a persistent, run-scoped SQLite cache: only actors not
	// yet resolved under the current dataset run hit the backend, and the results (incl.
	// '' = confirmed non-author) are cached, so steady-state loads make no backend calls.
	// A dataset rebuild bumps run_id, which re-resolves everyone once. We fetch whenever we
	// still lack a *name* (a linkable semantic_id rides along when the backend has one).
	const runId = manifest.run_id;
	const cache = new Map(OrcidNameDb.getAll().map((r) => [r.orcid, r]));
	const toFetch: string[] = [];
	for (const orcid of allOrcids) {
		if (nameByOrcid.has(orcid)) continue;
		const cached = cache.get(orcid);
		if (cached && cached.run_id === runId) note(orcid, cached.name, cached.semantic_id);
		else toFetch.push(orcid);
	}
	if (toFetch.length > 0) {
		const fetched = await resolveOrcidProfiles(toFetch);
		OrcidNameDb.upsertMany(
			[...fetched].map(([orcid, p]) => ({ orcid, name: p.name, semantic_id: p.semanticId })),
			runId
		);
		for (const [orcid, p] of fetched) note(orcid, p.name, p.semanticId);
	}

	const userRows = [...allOrcids].map((orcid) => {
		const u = userByOrcid.get(orcid);
		const act = activityByOrcid.get(orcid);
		const consent = consentByOrcid.get(orcid) ?? null;
		// Datetime strings are lexicographically ordered, so max = most recent.
		const lastSeen =
			[u?.last_login_at, act?.last_event_at, consent?.granted_at]
				.filter((t): t is string => !!t)
				.sort()
				.at(-1) ?? '';
		return {
			orcid,
			name: nameByOrcid.get(orcid) ?? null,
			semantic_id: semByOrcid.get(orcid) ?? null,
			last_login_at: u?.last_login_at ?? null,
			login_count: u?.login_count ?? 0,
			event_count: act?.event_count ?? 0,
			online: online.has(orcid),
			last_seen: lastSeen,
			consent
		};
	});

	// Currently-online users first, then most-recently-active.
	userRows.sort((a, b) =>
		a.online !== b.online ? (a.online ? -1 : 1) : b.last_seen.localeCompare(a.last_seen)
	);

	return {
		events: LedgerDb.listAllEvents(),
		applied: [...applied],
		skipped: manifest.skipped,
		currentRunId: manifest.run_id,
		users: userRows,
		names: Object.fromEntries(
			[...nameByOrcid].map(([orcid, name]) => [
				orcid,
				{ name, semanticId: semByOrcid.get(orcid) ?? '' }
			])
		) as Record<string, { name: string; semanticId: string }>
	};
};
