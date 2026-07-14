import { Database } from 'bun:sqlite';
import { env } from '$env/dynamic/private';
import { DEFAULT_MODERATION, logicalKey, subjectHash } from './ledger-hash';
import type { LedgerKind, LedgerPayload, ModerationState } from '$lib/types/ledger';
import type { EnrichmentEntry, EnrichmentSource, ReviewVerdict } from '$lib/types/review';
import type { EmailConsent, EmailPurposeKey } from '$lib/types/email-consent';
import type { SessionUserData } from './session';

let _db: Database | null = null;

export function getDb(): Database {
	if (_db) return _db;
	const dbPath = env.RANKLESS_DB_PATH ?? 'data/rankless.sqlite';
	_db = new Database(dbPath);
	// Multiple Bun worker processes (blue/green × procs) share this file; without a busy timeout a
	// concurrent writer throws SQLITE_BUSY immediately instead of waiting. Set it *before* the WAL
	// switch so even the first-init race (every worker flipping journal_mode on a fresh file at once)
	// waits on the lock instead of erroring.
	_db.run('PRAGMA busy_timeout = 5000');
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
		CREATE TABLE IF NOT EXISTS sessions (
			token TEXT PRIMARY KEY,
			orcid TEXT NOT NULL,
			name TEXT NOT NULL,
			semantic_id TEXT,
			created_at TEXT NOT NULL DEFAULT (datetime('now')),
			expires_at TEXT NOT NULL
		);
		CREATE TABLE IF NOT EXISTS users (
			orcid TEXT PRIMARY KEY,
			name TEXT,
			semantic_id TEXT,
			first_login_at TEXT NOT NULL DEFAULT (datetime('now')),
			last_login_at TEXT NOT NULL DEFAULT (datetime('now')),
			login_count INTEGER NOT NULL DEFAULT 0
		);
			-- Persistent cache of ORCID → author display name + semantic_id resolved from
			-- the backend (see resolveOrcidProfiles). Scoped by dataset run_id so a rebuild
			-- re-resolves; an empty name is a negative entry (ORCID isn't an author), kept
			-- so repeat loads don't re-query the backend for the same non-author ORCIDs.
			CREATE TABLE IF NOT EXISTS orcid_names (
				orcid TEXT PRIMARY KEY,
				name TEXT NOT NULL,
				semantic_id TEXT,
				run_id TEXT
			);
		CREATE TABLE IF NOT EXISTS email_consents (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			orcid TEXT NOT NULL,
			email TEXT NOT NULL,
			-- legacy, always 'manual' now (kept: deployed DBs already have the NOT NULL column)
			email_source TEXT NOT NULL DEFAULT 'manual',
			purposes TEXT NOT NULL,
			consent_version TEXT NOT NULL,
			granted_at TEXT NOT NULL DEFAULT (datetime('now')),
			withdrawn_at TEXT
		);
		CREATE INDEX IF NOT EXISTS idx_ec_orcid ON email_consents(orcid);
		CREATE INDEX IF NOT EXISTS idx_ec_active ON email_consents(orcid) WHERE withdrawn_at IS NULL;
		-- MCP exploration sessions: index/metadata; the artifacts (report.md,
		-- findings.json, reproduce.md) live in $MCP_SESSIONS_ROOT/<name>/. The
		-- Python worker writes rows here too (via its own sqlite3 on this file).
		CREATE TABLE IF NOT EXISTS mcp_sessions (
			name TEXT PRIMARY KEY,
			orcid TEXT,
			status TEXT NOT NULL DEFAULT 'queued',
			visibility TEXT NOT NULL DEFAULT 'private',
			title TEXT,
			params TEXT NOT NULL,
			meta TEXT,
			error TEXT,
			created_at TEXT NOT NULL DEFAULT (datetime('now')),
			updated_at TEXT NOT NULL DEFAULT (datetime('now'))
		);
		CREATE INDEX IF NOT EXISTS idx_mcp_vis ON mcp_sessions(visibility, status);
		CREATE INDEX IF NOT EXISTS idx_mcp_status ON mcp_sessions(status);
		-- External-metadata cache for ledger review (Crossref/OpenAlex/ORCID). Only this
		-- server writes it (single fetch implementation in enrich.ts); the AI review lane
		-- (pyscripts/review_ledger.py) reads it via its own sqlite3 on this file.
		CREATE TABLE IF NOT EXISTS subject_enrichment (
			source TEXT NOT NULL,
			key TEXT NOT NULL,
			status TEXT NOT NULL,
			data TEXT,
			fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
			PRIMARY KEY (source, key)
		);
		-- AI review verdicts, append-only; written by pyscripts/review_ledger.py (mirrored
		-- DDL there), read here. Keyed by (orcid, kind, subject_hash) — event_id is NOT
		-- stable across boxes (mcp_db.py merge renumbers it). created_at is writer-supplied
		-- UTC ISO so the dedup index stays deterministic across cross-box merges.
		CREATE TABLE IF NOT EXISTS review_verdicts (
			verdict_id INTEGER PRIMARY KEY AUTOINCREMENT,
			orcid TEXT NOT NULL,
			kind TEXT NOT NULL,
			subject_hash TEXT NOT NULL,
			model TEXT NOT NULL,
			verdict TEXT NOT NULL,
			confidence REAL NOT NULL,
			reasoning TEXT NOT NULL,
			checks TEXT,
			created_at TEXT NOT NULL
		);
		CREATE UNIQUE INDEX IF NOT EXISTS idx_rv_dedup
			ON review_verdicts(orcid, kind, subject_hash, model, created_at);
		CREATE INDEX IF NOT EXISTS idx_rv_subject ON review_verdicts(orcid, kind, subject_hash);
	`);
	return _db;
}

export type LedgerEvent = {
	event_id: number;
	key: string;
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
	const kind = r.kind as LedgerKind;
	return {
		event_id: r.event_id,
		key: logicalKey(r.orcid, kind, r.subject_hash),
		orcid: r.orcid,
		kind,
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

export type EventFilter = {
	moderation?: ModerationState;
	kind?: LedgerKind;
	orcid?: string;
};

function eventFilterSql(filter: EventFilter): { where: string; params: (string | number)[] } {
	const clauses: string[] = [];
	const params: (string | number)[] = [];
	if (filter.moderation) {
		clauses.push('moderation = ?');
		params.push(filter.moderation);
	}
	if (filter.kind) {
		clauses.push('kind = ?');
		params.push(filter.kind);
	}
	if (filter.orcid) {
		clauses.push('orcid = ?');
		params.push(filter.orcid);
	}
	return { where: clauses.length ? `WHERE ${clauses.join(' AND ')}` : '', params };
}

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

	// Admin review queue: actor-ordered so claimant groups are contiguous on a page.
	listEventsFiltered(filter: EventFilter, limit: number, offset: number): LedgerEvent[] {
		const { where, params } = eventFilterSql(filter);
		const rows = getDb()
			.prepare(
				`SELECT * FROM ledger_events ${where} ORDER BY orcid ASC, event_id DESC LIMIT ? OFFSET ?`
			)
			.all(...params, limit, offset) as LedgerEventRow[];
		return rows.map(rowToEvent);
	},

	countEventsFiltered(filter: EventFilter): number {
		const { where, params } = eventFilterSql(filter);
		const row = getDb()
			.prepare(`SELECT count(*) AS n FROM ledger_events ${where}`)
			.get(...params) as { n: number };
		return row.n;
	},

	listPendingActors(): { orcid: string; pending: number }[] {
		return getDb()
			.prepare(
				"SELECT orcid, count(*) AS pending FROM ledger_events WHERE moderation = 'pending_review' AND revoked_at IS NULL GROUP BY orcid ORDER BY pending DESC"
			)
			.all() as { orcid: string; pending: number }[];
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

	// One transaction for a bulk decision; returns the ids actually flipped (still pending).
	setModerationBulk(
		event_ids: number[],
		decision: 'accepted' | 'rejected',
		moderator_orcid: string
	): number[] {
		const db = getDb();
		const stmt = db.prepare(
			"UPDATE ledger_events SET moderation = ?, moderated_by = ?, moderated_at = datetime('now') WHERE event_id = ? AND moderation = 'pending_review'"
		);
		const updated: number[] = [];
		db.run('BEGIN');
		try {
			for (const id of event_ids) {
				if (stmt.run(decision, moderator_orcid, id).changes > 0) updated.push(id);
			}
			db.run('COMMIT');
		} catch (e) {
			db.run('ROLLBACK');
			throw e;
		}
		return updated;
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
	},

	// Per-actor ledger activity, so the admin view can surface people who have made a
	// change even if they predate (or never populated) the users table.
	listActorActivity(): { orcid: string; event_count: number; last_event_at: string }[] {
		return getDb()
			.prepare(
				'SELECT orcid, COUNT(*) AS event_count, MAX(created_at) AS last_event_at FROM ledger_events GROUP BY orcid'
			)
			.all() as { orcid: string; event_count: number; last_event_at: string }[];
	},

	// Union of every event logical key ever applied to the data, across all stored pipeline
	// runs — i.e. the requested changes that are now live in the pipeline. Keyed by logical
	// key (not event_id) so it survives the id renumbering that DB merges cause.
	getAllAppliedKeys(): string[] {
		const rows = getDb()
			.prepare('SELECT manifest_json FROM ledger_runs WHERE manifest_json IS NOT NULL')
			.all() as { manifest_json: string }[];
		const keys = new Set<string>();
		for (const r of rows) {
			try {
				const m = JSON.parse(r.manifest_json) as { applied_keys?: string[] };
				for (const k of m.applied_keys ?? []) keys.add(k);
			} catch {
				// ignore a malformed stored manifest
			}
		}
		return [...keys];
	}
};

type EnrichmentRow = {
	source: string;
	key: string;
	status: string;
	data: string | null;
	fetched_at: string;
};

// Cache of plucked external metadata (Crossref/OpenAlex/ORCID) for ledger review.
// Rows are keyed by external id, so they stay valid across cross-box DB merges.
export const EnrichmentDb = {
	get(source: EnrichmentSource, key: string): EnrichmentEntry | null {
		const row = getDb()
			.prepare('SELECT * FROM subject_enrichment WHERE source = ? AND key = ?')
			.get(source, key) as EnrichmentRow | null;
		return row ? rowToEnrichment(row) : null;
	},

	getMany(pairs: { source: EnrichmentSource; key: string }[]): EnrichmentEntry[] {
		const stmt = getDb().prepare('SELECT * FROM subject_enrichment WHERE source = ? AND key = ?');
		const entries: EnrichmentEntry[] = [];
		for (const p of pairs) {
			const row = stmt.get(p.source, p.key) as EnrichmentRow | null;
			if (row) entries.push(rowToEnrichment(row));
		}
		return entries;
	},

	upsert(entry: Omit<EnrichmentEntry, 'fetched_at'>): void {
		getDb()
			.prepare(
				"INSERT OR REPLACE INTO subject_enrichment (source, key, status, data, fetched_at) VALUES (?, ?, ?, ?, datetime('now'))"
			)
			.run(entry.source, entry.key, entry.status, entry.data ? JSON.stringify(entry.data) : null);
	}
};

type VerdictRow = {
	orcid: string;
	kind: string;
	subject_hash: string;
	model: string;
	verdict: string;
	confidence: number;
	reasoning: string;
	checks: string | null;
	created_at: string;
};

// AI review verdicts written by pyscripts/review_ledger.py; read-only here.
export const VerdictDb = {
	listForOrcids(orcids: string[]): ReviewVerdict[] {
		if (orcids.length === 0) return [];
		const placeholders = orcids.map(() => '?').join(', ');
		const rows = getDb()
			.prepare(`SELECT * FROM review_verdicts WHERE orcid IN (${placeholders})`)
			.all(...orcids) as VerdictRow[];
		return rows.map((r) => ({
			orcid: r.orcid,
			kind: r.kind,
			subject_hash: r.subject_hash,
			model: r.model,
			verdict: r.verdict as ReviewVerdict['verdict'],
			confidence: r.confidence,
			reasoning: r.reasoning,
			checks: r.checks ? (JSON.parse(r.checks) as Record<string, unknown>) : null,
			created_at: r.created_at
		}));
	}
};

function rowToEnrichment(r: EnrichmentRow): EnrichmentEntry {
	return {
		source: r.source as EnrichmentSource,
		key: r.key,
		status: r.status as EnrichmentEntry['status'],
		data: r.data ? (JSON.parse(r.data) as EnrichmentEntry['data']) : null,
		fetched_at: r.fetched_at
	};
}

type SessionRow = { orcid: string; name: string; semantic_id: string | null };

// Server-side session store. The cookie carries only an opaque random token; the
// authenticated identity (orcid/name) lives here and is never client-controllable.
export const SessionDb = {
	create(token: string, data: SessionUserData, ttlSeconds: number): void {
		const db = getDb();
		db.prepare("DELETE FROM sessions WHERE expires_at <= datetime('now')").run();
		db.prepare(
			"INSERT INTO sessions (token, orcid, name, semantic_id, expires_at) VALUES (?, ?, ?, ?, datetime('now', ?))"
		).run(token, data.orcid, data.name, data.semanticId ?? null, `+${ttlSeconds} seconds`);
	},

	get(token: string): SessionUserData | null {
		const row = getDb()
			.prepare(
				"SELECT orcid, name, semantic_id FROM sessions WHERE token = ? AND expires_at > datetime('now')"
			)
			.get(token) as SessionRow | null;
		if (!row) return null;
		return { orcid: row.orcid, name: row.name, semanticId: row.semantic_id ?? undefined };
	},

	destroy(token: string): void {
		getDb().prepare('DELETE FROM sessions WHERE token = ?').run(token);
	},

	// ORCIDs with a live (non-expired) session — i.e. currently signed in.
	activeOrcids(): Set<string> {
		const rows = getDb()
			.prepare("SELECT DISTINCT orcid FROM sessions WHERE expires_at > datetime('now')")
			.all() as { orcid: string }[];
		return new Set(rows.map((r) => r.orcid));
	},

	// Most recent session profile (name + semantic_id) per ORCID. Sessions carry these
	// even when a user has no `users` row (e.g. dev-login), so this backfills what the
	// users table lacks. (Bare columns with `MAX(created_at)` yield the newest row's
	// values in SQLite.)
	profilesByOrcid(): { orcid: string; name: string; semantic_id: string | null }[] {
		return getDb()
			.prepare('SELECT orcid, name, semantic_id, MAX(created_at) AS c FROM sessions GROUP BY orcid')
			.all() as { orcid: string; name: string; semantic_id: string | null }[];
	}
};

export type UserRow = {
	orcid: string;
	name: string | null;
	semantic_id: string | null;
	first_login_at: string;
	last_login_at: string;
	login_count: number;
};

// Persistent record of who has signed in (session rows expire and are pruned), so the
// admin view can show logins independently of live sessions.
export const UserDb = {
	recordLogin(data: SessionUserData): void {
		getDb()
			.prepare(
				`INSERT INTO users (orcid, name, semantic_id, login_count)
				 VALUES (?, ?, ?, 1)
				 ON CONFLICT(orcid) DO UPDATE SET
				   name = excluded.name,
				   semantic_id = COALESCE(excluded.semantic_id, users.semantic_id),
				   last_login_at = datetime('now'),
				   login_count = users.login_count + 1`
			)
			.run(data.orcid, data.name, data.semanticId ?? null);
	},

	listUsers(): UserRow[] {
		return getDb().prepare('SELECT * FROM users ORDER BY last_login_at DESC').all() as UserRow[];
	}
};

export type OrcidNameRow = {
	orcid: string;
	name: string;
	semantic_id: string | null;
	run_id: string | null;
};

// Persistent, run-scoped read-through cache for backend ORCID → author profile lookups,
// so the admin view doesn't re-hit the backend on every load (or for known non-authors).
export const OrcidNameDb = {
	getAll(): OrcidNameRow[] {
		return getDb()
			.prepare('SELECT orcid, name, semantic_id, run_id FROM orcid_names')
			.all() as OrcidNameRow[];
	},

	// Upsert resolved profiles (empty name = confirmed non-author) under the given run.
	upsertMany(entries: { orcid: string; name: string; semantic_id: string }[], runId: string): void {
		if (entries.length === 0) return;
		const db = getDb();
		const stmt = db.prepare(
			`INSERT INTO orcid_names (orcid, name, semantic_id, run_id) VALUES (?, ?, ?, ?)
			 ON CONFLICT(orcid) DO UPDATE SET name = excluded.name, semantic_id = excluded.semantic_id, run_id = excluded.run_id`
		);
		db.run('BEGIN');
		try {
			for (const e of entries) stmt.run(e.orcid, e.name, e.semantic_id, runId);
			db.run('COMMIT');
		} catch (err) {
			db.run('ROLLBACK');
			throw err;
		}
	}
};

type ConsentRow = {
	id: number;
	orcid: string;
	email: string;
	email_source: string;
	purposes: string;
	consent_version: string;
	granted_at: string;
	withdrawn_at: string | null;
};

function rowToConsent(r: ConsentRow): EmailConsent {
	return {
		email: r.email,
		purposes: JSON.parse(r.purposes) as EmailPurposeKey[],
		consent_version: r.consent_version,
		granted_at: r.granted_at
	};
}

// Append-only, auditable consent log. The active consent for an ORCID is the latest row
// with withdrawn_at IS NULL; granting again withdraws the prior row and inserts a new one,
// so the full history (what was agreed, when, under which notice version) is preserved.
export const ConsentDb = {
	setConsent(orcid: string, email: string, purposes: EmailPurposeKey[], version: string): void {
		const db = getDb();
		// Withdraw-then-insert must be atomic so a user never ends up with two active rows
		// (or none); a plain BEGIN/COMMIT keeps to the `.run` API used throughout this file.
		db.run('BEGIN');
		try {
			db.prepare(
				"UPDATE email_consents SET withdrawn_at = datetime('now') WHERE orcid = ? AND withdrawn_at IS NULL"
			).run(orcid);
			db.prepare(
				"INSERT INTO email_consents (orcid, email, email_source, purposes, consent_version) VALUES (?, ?, 'manual', ?, ?)"
			).run(orcid, email, JSON.stringify(purposes), version);
			db.run('COMMIT');
		} catch (e) {
			db.run('ROLLBACK');
			throw e;
		}
	},

	withdrawConsent(orcid: string): boolean {
		const info = getDb()
			.prepare(
				"UPDATE email_consents SET withdrawn_at = datetime('now') WHERE orcid = ? AND withdrawn_at IS NULL"
			)
			.run(orcid);
		return info.changes > 0;
	},

	getActiveConsent(orcid: string): EmailConsent | null {
		const row = getDb()
			.prepare(
				'SELECT * FROM email_consents WHERE orcid = ? AND withdrawn_at IS NULL ORDER BY id DESC LIMIT 1'
			)
			.get(orcid) as ConsentRow | null;
		return row ? rowToConsent(row) : null;
	},

	listActiveConsents(): (EmailConsent & { orcid: string })[] {
		const rows = getDb()
			.prepare('SELECT * FROM email_consents WHERE withdrawn_at IS NULL ORDER BY id DESC')
			.all() as ConsentRow[];
		return rows.map((r) => ({ orcid: r.orcid, ...rowToConsent(r) }));
	}
};
