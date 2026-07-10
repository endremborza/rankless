// Exploration-session store: a metadata index in SQLite (mcp_sessions), with the
// heavy artifacts (report.md, reproduce.md, findings.json) on disk under
// $MCP_SESSIONS_ROOT/<name>/. The Python worker writes the same table + dirs.

import { existsSync, readFileSync, rmSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { env } from '$env/dynamic/private';
import { getDb } from './db';
import type { McpSession, SessionFindings, SessionParams, SessionVisibility } from '$lib/types/mcp';

type Row = {
	name: string;
	orcid: string | null;
	status: string;
	visibility: string;
	title: string | null;
	params: string;
	meta: string | null;
	error: string | null;
	created_at: string;
	updated_at: string;
};

const NAME_RE = /^[a-zA-Z0-9][a-zA-Z0-9._-]*$/;
const ARTIFACTS = new Set(['report.md', 'reproduce.md', 'findings.json']);

export function sessionsRoot(): string {
	return env.MCP_SESSIONS_ROOT ?? 'data/mcp-sessions';
}

export function isValidName(name: string): boolean {
	return NAME_RE.test(name);
}

export function listSessions(opts: { publicOnly?: boolean } = {}): McpSession[] {
	const where = opts.publicOnly ? "WHERE visibility = 'public' AND status = 'done'" : '';
	const rows = getDb()
		.prepare(`SELECT * FROM mcp_sessions ${where} ORDER BY created_at DESC`)
		.all() as Row[];
	return rows.map(rowToSession);
}

export function getSession(name: string): McpSession | null {
	const row = getDb().prepare('SELECT * FROM mcp_sessions WHERE name = ?').get(name) as
		| Row
		| undefined;
	return row ? rowToSession(row) : null;
}

export function createSession(input: {
	name: string;
	orcid: string;
	params: SessionParams;
	visibility: SessionVisibility;
}): void {
	getDb()
		.prepare(
			`INSERT INTO mcp_sessions (name, orcid, status, visibility, title, params)
			 VALUES (?, ?, 'queued', ?, ?, ?)`
		)
		.run(
			input.name,
			input.orcid,
			input.visibility,
			sessionTitle(input.params),
			JSON.stringify(input.params)
		);
}

export function setVisibility(name: string, visibility: SessionVisibility): void {
	getDb()
		.prepare("UPDATE mcp_sessions SET visibility = ?, updated_at = datetime('now') WHERE name = ?")
		.run(visibility, name);
}

export function deleteSession(name: string): void {
	getDb().prepare('DELETE FROM mcp_sessions WHERE name = ?').run(name);
	if (isValidName(name)) {
		rmSync(join(sessionsRoot(), name), { recursive: true, force: true });
	}
}

// findings.json for a session, or null if the run hasn't produced it yet.
export function readFindings(name: string): SessionFindings | null {
	const raw = readArtifact(name, 'findings.json');
	if (raw === null) return null;
	try {
		return JSON.parse(raw) as SessionFindings;
	} catch {
		return null;
	}
}

// Raw text of one whitelisted artifact file inside the session dir.
export function readArtifact(name: string, file: string): string | null {
	if (!isValidName(name) || !ARTIFACTS.has(file)) return null;
	const root = resolve(sessionsRoot());
	const path = resolve(join(root, name, file));
	if (!path.startsWith(root + '/') || !existsSync(path)) return null;
	return readFileSync(path, 'utf-8');
}

function rowToSession(r: Row): McpSession {
	return {
		name: r.name,
		orcid: r.orcid,
		status: r.status as McpSession['status'],
		visibility: r.visibility as SessionVisibility,
		title: r.title,
		params: JSON.parse(r.params) as SessionParams,
		meta: r.meta ? JSON.parse(r.meta) : null,
		error: r.error,
		createdAt: r.created_at,
		updatedAt: r.updated_at
	};
}

function sessionTitle(p: SessionParams): string {
	if (p.investigate) return `Deepening ${p.investigate}`;
	if (p.subject) return p.subject;
	if (p.question) return p.question;
	return `${p.foci.join(', ')} on ${p.backend}`;
}
