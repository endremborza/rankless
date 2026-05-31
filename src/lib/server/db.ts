import { Database } from 'bun:sqlite';
import { env } from '$env/dynamic/private';
import { DEFAULT_MODERATION, subjectHash } from './ledger-hash';
import type { LedgerKind, LedgerPayload, ModerationState } from '$lib/types/ledger';

let _db: Database | null = null;

export function getDb(): Database {
	if (_db) return _db;
	const dbPath = env.RANKLESS_DB_PATH ?? 'data/rankless.sqlite';
	_db = new Database(dbPath);
	_db.run('PRAGMA journal_mode = WAL');
	_db.run(`
		CREATE TABLE IF NOT EXISTS ledger_events (
			event_id INTEGER PRIMARY KEY AUTOINCREMENT,
			orcid TEXT NOT NULL,
			kind TEXT NOT NULL,
			payload TEXT NOT NULL,
			subject_hash TEXT NOT NULL,
			created_at TEXT NOT NULL DEFAULT (datetime('now')),
			revoked_at TEXT,
			moderation TEXT NOT NULL DEFAULT 'auto_ok',
			moderated_by TEXT,
			moderated_at TEXT
		);
		CREATE INDEX IF NOT EXISTS idx_le_orcid ON ledger_events(orcid);
		CREATE INDEX IF NOT EXISTS idx_le_kind ON ledger_events(kind);
		CREATE INDEX IF NOT EXISTS idx_le_moderation ON ledger_events(moderation);
		CREATE UNIQUE INDEX IF NOT EXISTS idx_le_dedup
			ON ledger_events(orcid, kind, subject_hash)
			WHERE revoked_at IS NULL;
		CREATE TABLE IF NOT EXISTS ledger_runs (
			run_id TEXT PRIMARY KEY,
			snapshot_at TEXT NOT NULL,
			manifest_at TEXT,
			manifest_json TEXT
		);
		CREATE TABLE IF NOT EXISTS owner_pins (
			orcid TEXT PRIMARY KEY,
			first_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
		);
	`);
	return _db;
}

export type LedgerEvent = {
	event_id: number;
	orcid: string;
	kind: LedgerKind;
	payload: LedgerPayload;
	subject_hash: string;
	created_at: string;
	revoked_at: string | null;
	moderation: ModerationState;
	moderated_by: string | null;
	moderated_at: string | null;
};

type LedgerEventRow = {
	event_id: number;
	orcid: string;
	kind: string;
	payload: string;
	subject_hash: string;
	created_at: string;
	revoked_at: string | null;
	moderation: string;
	moderated_by: string | null;
	moderated_at: string | null;
};

function rowToEvent(r: LedgerEventRow): LedgerEvent {
	return {
		event_id: r.event_id,
		orcid: r.orcid,
		kind: r.kind as LedgerKind,
		payload: JSON.parse(r.payload),
		subject_hash: r.subject_hash,
		created_at: r.created_at,
		revoked_at: r.revoked_at,
		moderation: r.moderation as ModerationState,
		moderated_by: r.moderated_by,
		moderated_at: r.moderated_at
	};
}

export type CreateEventResult = { event_id: number; existing: boolean };

export const LedgerDb = {
	createEvent(orcid: string, payload: LedgerPayload): CreateEventResult {
		const hash = subjectHash(payload);
		const moderation = DEFAULT_MODERATION[payload.kind];
		const existing = getDb()
			.prepare(
				'SELECT event_id FROM ledger_events WHERE orcid = ? AND kind = ? AND subject_hash = ? AND revoked_at IS NULL'
			)
			.get(orcid, payload.kind, hash) as { event_id: number } | null;
		if (existing) return { event_id: existing.event_id, existing: true };
		const info = getDb()
			.prepare(
				'INSERT INTO ledger_events (orcid, kind, payload, subject_hash, moderation) VALUES (?, ?, ?, ?, ?)'
			)
			.run(orcid, payload.kind, JSON.stringify(payload), hash, moderation);
		return { event_id: Number(info.lastInsertRowid), existing: false };
	},

	getEventsForOrcid(orcid: string): LedgerEvent[] {
		const rows = getDb()
			.prepare('SELECT * FROM ledger_events WHERE orcid = ? ORDER BY event_id DESC')
			.all(orcid) as LedgerEventRow[];
		return rows.map(rowToEvent);
	},

	getEvent(event_id: number): LedgerEvent | null {
		const row = getDb()
			.prepare('SELECT * FROM ledger_events WHERE event_id = ?')
			.get(event_id) as LedgerEventRow | null;
		return row ? rowToEvent(row) : null;
	},

	revokePending(orcid: string, event_id: number): boolean {
		const info = getDb()
			.prepare(
				"UPDATE ledger_events SET revoked_at = datetime('now') WHERE event_id = ? AND orcid = ? AND revoked_at IS NULL"
			)
			.run(event_id, orcid);
		return info.changes > 0;
	},

	editPending(orcid: string, event_id: number, payload: LedgerPayload): boolean {
		const existing = LedgerDb.getEvent(event_id);
		if (!existing || existing.orcid !== orcid || existing.revoked_at !== null) return false;
		if (existing.kind !== payload.kind) return false;
		const hash = subjectHash(payload);
		const info = getDb()
			.prepare(
				'UPDATE ledger_events SET payload = ?, subject_hash = ? WHERE event_id = ? AND orcid = ? AND revoked_at IS NULL'
			)
			.run(JSON.stringify(payload), hash, event_id, orcid);
		return info.changes > 0;
	},

	setModeration(
		event_id: number,
		decision: 'accepted' | 'rejected',
		moderator_orcid: string
	): boolean {
		const info = getDb()
			.prepare(
				"UPDATE ledger_events SET moderation = ?, moderated_by = ?, moderated_at = datetime('now') WHERE event_id = ? AND moderation = 'pending_review'"
			)
			.run(decision, moderator_orcid, event_id);
		return info.changes > 0;
	},

	pinOwner(orcid: string): void {
		getDb().prepare('INSERT OR IGNORE INTO owner_pins (orcid) VALUES (?)').run(orcid);
	},

	getOwnerPins(): { orcid: string; first_seen_at: string }[] {
		return getDb().prepare('SELECT orcid, first_seen_at FROM owner_pins').all() as {
			orcid: string;
			first_seen_at: string;
		}[];
	},

	findPendingByPayload(
		orcid: string,
		kind: LedgerKind,
		jsonPath: string,
		value: string | number | null
	): number | null {
		const row = getDb()
			.prepare(
				'SELECT event_id FROM ledger_events WHERE orcid = ? AND kind = ? AND revoked_at IS NULL AND json_extract(payload, ?) = ?'
			)
			.get(orcid, kind, jsonPath, value) as { event_id: number } | null;
		return row?.event_id ?? null;
	},

	findMergePapersPending(orcid: string, widKeep: number, widDrop: number): number | null {
		const row = getDb()
			.prepare(
				"SELECT event_id FROM ledger_events WHERE orcid = ? AND kind = 'merge_papers' AND revoked_at IS NULL AND json_extract(payload, '$.keep.dm_id_at_creation') = ? AND json_extract(payload, '$.drop.dm_id_at_creation') = ?"
			)
			.get(orcid, widKeep, widDrop) as { event_id: number } | null;
		return row?.event_id ?? null;
	},

	upsertRun(runId: string, snapshotAt: string, manifestJson: string): void {
		getDb()
			.prepare(
				"INSERT OR IGNORE INTO ledger_runs (run_id, snapshot_at, manifest_at, manifest_json) VALUES (?, ?, datetime('now'), ?)"
			)
			.run(runId, snapshotAt, manifestJson);
	}
};
