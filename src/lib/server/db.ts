import Database from 'better-sqlite3';
import { env } from '$env/dynamic/private';
import type { AuthorMergeRequest } from '$lib/tree-types';

let _db: Database.Database | null = null;

function getDb(): Database.Database {
	if (_db) return _db;
	const dbPath = env.RANKLESS_DB_PATH ?? 'data/rankless.sqlite';
	_db = new Database(dbPath);
	_db.pragma('journal_mode = WAL');
	_db.exec(`
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
	`);
	return _db;
}

export const PaperDb = {
	getDisownedWids(orcid: string): number[] {
		const rows = getDb().prepare('SELECT wid FROM disowned_papers WHERE orcid = ?').all(orcid) as { wid: number }[];
		return rows.map(r => r.wid);
	},

	disownPaper(orcid: string, wid: number): void {
		getDb().prepare('INSERT OR IGNORE INTO disowned_papers (orcid, wid) VALUES (?, ?)').run(orcid, wid);
	},

	unDisownPaper(orcid: string, wid: number): void {
		getDb().prepare('DELETE FROM disowned_papers WHERE orcid = ? AND wid = ?').run(orcid, wid);
	},

	getClaimedDois(orcid: string): string[] {
		const rows = getDb().prepare('SELECT doi FROM claimed_papers WHERE orcid = ?').all(orcid) as { doi: string }[];
		return rows.map((r) => r.doi);
	},

	claimPaper(orcid: string, doi: string): void {
		getDb().prepare('INSERT OR IGNORE INTO claimed_papers (orcid, doi) VALUES (?, ?)').run(orcid, doi);
	},

	unClaimPaper(orcid: string, doi: string): void {
		getDb().prepare('DELETE FROM claimed_papers WHERE orcid = ? AND doi = ?').run(orcid, doi);
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
