import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { LedgerDb } from '$lib/server/db';
import type { LedgerKind, LedgerPayload } from '$lib/types/ledger';
import {
	resolveWorkSubject,
	resolveAuthorSubject,
	assertAuthoredAny,
	canonicalDoi,
	ResolveError
} from '$lib/server/id_resolver';

type PayloadInput = Record<string, unknown>;

function requireNumber(val: unknown, name: string): number | undefined {
	if (val === undefined || val === null) return undefined;
	if (typeof val !== 'number') throw new ResolveError(`${name} must be a number`, 400);
	return val;
}

function requireString(val: unknown, name: string): string | undefined {
	if (val === undefined || val === null) return undefined;
	if (typeof val !== 'string') throw new ResolveError(`${name} must be a string`, 400);
	return val;
}

function requireObject(val: unknown, name: string): PayloadInput {
	if (!val || typeof val !== 'object' || Array.isArray(val)) {
		throw new ResolveError(`${name} must be an object`, 400);
	}
	return val as PayloadInput;
}

async function buildPayload(
	kind: LedgerKind,
	input: PayloadInput,
	orcid: string
): Promise<LedgerPayload> {
	switch (kind) {
		case 'disown_paper': {
			const work = await resolveWorkSubject({
				wid: requireNumber(input.wid, 'wid'),
				oa_id: requireNumber(input.oa_id, 'oa_id'),
				doi: requireString(input.doi, 'doi'),
				display_title: requireString(input.display_title, 'display_title'),
				display_year: requireNumber(input.display_year, 'display_year')
			});
			return { kind, work };
		}
		case 'claim_paper': {
			const rawDoi = requireString(input.doi, 'doi');
			const work = await resolveWorkSubject({
				wid: requireNumber(input.wid, 'wid'),
				oa_id: requireNumber(input.oa_id, 'oa_id'),
				doi: rawDoi ? canonicalDoi(rawDoi) : undefined,
				display_title: requireString(input.display_title, 'display_title'),
				display_year: requireNumber(input.display_year, 'display_year')
			});
			return { kind, work };
		}
		case 'merge_papers': {
			const keepInput = requireObject(input.keep, 'keep');
			const dropInput = requireObject(input.drop, 'drop');
			const [keep, drop] = await Promise.all([
				resolveWorkSubject({
					wid: requireNumber(keepInput.wid, 'keep.wid'),
					oa_id: requireNumber(keepInput.oa_id, 'keep.oa_id'),
					doi: requireString(keepInput.doi, 'keep.doi')
				}),
				resolveWorkSubject({
					wid: requireNumber(dropInput.wid, 'drop.wid'),
					oa_id: requireNumber(dropInput.oa_id, 'drop.oa_id'),
					doi: requireString(dropInput.doi, 'drop.doi')
				})
			]);
			await assertAuthoredAny(orcid, [keep.dm_id_at_creation, drop.dm_id_at_creation]);
			return { kind, keep, drop };
		}
		case 'merge_authors': {
			const dropInput = requireObject(input.drop, 'drop');
			const [keep, drop] = await Promise.all([
				// keep is forced to the caller's own ORCID; a client-supplied semantic_id must not be
				// able to make a victim's profile the surviving side of the merge.
				resolveAuthorSubject({ orcid }),
				resolveAuthorSubject({
					semantic_id: requireString(dropInput.semantic_id, 'drop.semantic_id'),
					orcid: requireString(dropInput.orcid, 'drop.orcid'),
					oa_id: requireNumber(dropInput.oa_id, 'drop.oa_id'),
					dm_id: requireNumber(dropInput.dm_id, 'drop.dm_id'),
					display_name: requireString(dropInput.display_name, 'drop.display_name')
				})
			]);
			const note = requireString(input.note, 'note');
			return note?.trim() ? { kind, keep, drop, note: note.trim() } : { kind, keep, drop };
		}
		case 'revoke': {
			const target_event_id = requireNumber(input.target_event_id, 'target_event_id');
			if (target_event_id === undefined) throw new ResolveError('target_event_id is required', 400);
			// Resolve the client's local event_id to the target's merge-stable logical key now,
			// so the stored payload never depends on a renumberable id. Also the ownership gate.
			const target = LedgerDb.getEvent(target_event_id);
			if (!target || target.orcid !== orcid) {
				throw new ResolveError('Target event not found', 404);
			}
			const reason = requireString(input.reason, 'reason');
			return reason?.trim()
				? { kind, target_key: target.key, reason: reason.trim() }
				: { kind, target_key: target.key };
		}
		default:
			throw new ResolveError(`unsupported kind: ${kind}`, 400);
	}
}

export async function POST({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const body = await request.json();
	const { kind, ...payloadInput } = body as { kind: LedgerKind } & PayloadInput;
	if (!kind) return json({ error: 'kind is required' }, { status: 400 });

	try {
		const payload = await buildPayload(kind, payloadInput, locals.user.orcid);
		const result = LedgerDb.createEvent(locals.user.orcid, payload);
		return json({ event_id: result.event_id, existing: result.existing });
	} catch (e) {
		if (e instanceof ResolveError) return json({ error: e.message }, { status: e.status });
		throw e;
	}
}

export function GET({ locals }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	return json(LedgerDb.getEventsForOrcid(locals.user.orcid));
}
