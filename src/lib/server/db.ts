import Database from 'better-sqlite3';
import { env } from '$env/dynamic/private';

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
		return rows.map(r => r.doi);
	},

	claimPaper(orcid: string, doi: string): void {
		getDb().prepare('INSERT OR IGNORE INTO claimed_papers (orcid, doi) VALUES (?, ?)').run(orcid, doi);
	},

	unClaimPaper(orcid: string, doi: string): void {
		getDb().prepare('DELETE FROM claimed_papers WHERE orcid = ? AND doi = ?').run(orcid, doi);
	}
};
