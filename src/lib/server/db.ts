import { Database } from 'bun:sqlite';
import { env } from '$env/dynamic/private';
import type { AuthorMergeRequest } from '$lib/tree-types';
import { DEFAULT_MODERATION, subjectHash } from './ledger-hash';
import type { LedgerKind, LedgerPayload, ModerationState } from './ledger-hash';

export { subjectHash } from './ledger-hash';
export type { LedgerKind, LedgerPayload, ModerationState } from './ledger-hash';

let _db: Database | null = null;

export function getDb(): Database {
	if (_db) return _db;
	const dbPath = env.RANKLESS_DB_PATH ?? 'data/rankless.sqlite';
	_db = new Database(dbPath);
	_db.run('PRAGMA journal_mode = WAL');
	_db.run(`
		CREATE TABLE IF NOT EXISTS disowned_papers (
			orcid TEXT NOT NULL,
			wid INTEGER NOT NULL,
			created_at TEXT NOT NULL DEFAULT (datetime('now')),
			PRIMARY KEY (orcid, wid)
		);
		CREATE TABLE IF NOT EXISTS claimed_papers (
			orcid TEXT NOT NULL,
			doi TEXT NOT NULL,
			created_at TEXT NOT NULL DEFAULT (datetime('now')),
			PRIMARY KEY (orcid, doi)
		);
		CREATE TABLE IF NOT EXISTS paper_merges (
			orcid TEXT NOT NULL,
			wid_keep INTEGER NOT NULL,
			wid_drop INTEGER NOT NULL,
			created_at TEXT NOT NULL DEFAULT (datetime('now')),
			PRIMARY KEY (orcid, wid_keep, wid_drop)
		);
		CREATE TABLE IF NOT EXISTS author_merge_requests (
			orcid TEXT NOT NULL,
			my_semantic_id TEXT NOT NULL,
			other_semantic_id TEXT NOT NULL,
			note TEXT,
			created_at TEXT NOT NULL DEFAULT (datetime('now')),
			reviewed INTEGER NOT NULL DEFAULT 0,
			PRIMARY KEY (orcid, other_semantic_id)
		);
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
			first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
			reason TEXT NOT NULL
		);
	`);
	return _db;
}

export const PaperDb = {
	getDisownedWids(orcid: string): number[] {
		const rows = getDb().query('SELECT wid FROM disowned_papers WHERE orcid = ?').all(orcid) as { wid: number }[];
		return rows.map(r => r.wid);
	},

	disownPaper(orcid: string, wid: number): void {
		getDb().query('INSERT OR IGNORE INTO disowned_papers (orcid, wid) VALUES (?, ?)').run(orcid, wid);
	},

	unDisownPaper(orcid: string, wid: number): void {
		getDb().query('DELETE FROM disowned_papers WHERE orcid = ? AND wid = ?').run(orcid, wid);
	},

	getClaimedDois(orcid: string): string[] {
		const rows = getDb().query('SELECT doi FROM claimed_papers WHERE orcid = ?').all(orcid) as { doi: string }[];
		return rows.map((r) => r.doi);
	},

	claimPaper(orcid: string, doi: string): void {
		getDb().query('INSERT OR IGNORE INTO claimed_papers (orcid, doi) VALUES (?, ?)').run(orcid, doi);
	},

	unClaimPaper(orcid: string, doi: string): void {
		getDb().query('DELETE FROM claimed_papers WHERE orcid = ? AND doi = ?').run(orcid, doi);
	},

	getMergedPairs(orcid: string): [number, number][] {
		const rows = getDb()
			.prepare('SELECT wid_keep, wid_drop FROM paper_merges WHERE orcid = ?')
			.all(orcid) as { wid_keep: number; wid_drop: number }[];
		return rows.map((r) => [r.wid_keep, r.wid_drop]);
	},

	mergePapers(orcid: string, widKeep: number, widDrop: number): void {
		getDb()
			.prepare('INSERT OR REPLACE INTO paper_merges (orcid, wid_keep, wid_drop) VALUES (?, ?, ?)')
			.run(orcid, widKeep, widDrop);
	},

	unmergePapers(orcid: string, widKeep: number, widDrop: number): void {
		getDb()
			.prepare('DELETE FROM paper_merges WHERE orcid = ? AND wid_keep = ? AND wid_drop = ?')
			.run(orcid, widKeep, widDrop);
	},

	getAuthorMergeRequests(orcid: string): AuthorMergeRequest[] {
		return getDb()
			.prepare(
				'SELECT other_semantic_id, note, created_at FROM author_merge_requests WHERE orcid = ? AND reviewed = 0 ORDER BY created_at DESC'
			)
			.all(orcid) as AuthorMergeRequest[];
	},

	submitAuthorMergeRequest(
		orcid: string,
		mySemanticId: string,
		otherSemanticId: string,
		note: string | null
	): void {
		getDb()
			.prepare(
				'INSERT OR REPLACE INTO author_merge_requests (orcid, my_semantic_id, other_semantic_id, note) VALUES (?, ?, ?, ?)'
			)
			.run(orcid, mySemanticId, otherSemanticId, note);
	},

	cancelAuthorMergeRequest(orcid: string, otherSemanticId: string): void {
		getDb()
			.prepare(
				'DELETE FROM author_merge_requests WHERE orcid = ? AND other_semantic_id = ? AND reviewed = 0'
			)
			.run(orcid, otherSemanticId);
	}
};

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

	pinOwner(orcid: string, reason: 'login' | 'submitted_event' | 'manual'): void {
		getDb()
			.prepare('INSERT OR IGNORE INTO owner_pins (orcid, reason) VALUES (?, ?)')
			.run(orcid, reason);
	},

	getOwnerPins(): { orcid: string; reason: string; first_seen_at: string }[] {
		return getDb()
			.prepare('SELECT orcid, reason, first_seen_at FROM owner_pins')
			.all() as { orcid: string; reason: string; first_seen_at: string }[];
	}
};
