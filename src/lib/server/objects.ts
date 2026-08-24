// Unified MCP object store: payload-free index rows in `mcp_objects` addressing
// immutable zstd bundles (`data/mcp-objects/<run>.jsonl.zst`), written by
// pyscripts (object_store.py and the explore workflows) and moved between boxes
// by the user-DB handoff + artifact-dir copy. Bundles are immutable, so
// decompressed bundles are cached per process without invalidation. Index rows
// and bundles travel by different mechanisms, so a row whose bundle hasn't
// arrived yet is a designed possibility: its payload reads as null.

import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { env } from '$env/dynamic/private';
import { getDb } from './db';
import { OBJECTS_CURRENT_SQL, OBJECTS_SCHEMA } from './objects-schema';
import type { McpObject, ObjectKind, ObjectStatus } from '$lib/types/objects';

const BUNDLE_RE = /^[a-zA-Z0-9][a-zA-Z0-9._-]*$/;

type Row = {
	id: number;
	kind: string;
	obj_key: string;
	bundle: string;
	line: number;
	gen_at: string;
	etype: string | null;
	sem_id: string | null;
	title: string | null;
	status: string;
	status_note: string | null;
	created_at: string;
	updated_at: string;
};

let ensured = false;
const bundleCache = new Map<string, unknown[]>();
const warnedBundles = new Set<string>();

export function objectsRoot(): string {
	return env.MCP_OBJECTS_ROOT ?? 'data/mcp-objects';
}

export function listObjects(opts: {
	kinds?: ObjectKind[];
	statuses?: ObjectStatus[];
}): McpObject[] {
	const conds: string[] = [];
	const params: string[] = [];
	if (opts.kinds?.length) {
		conds.push(`kind IN (${opts.kinds.map(() => '?').join(',')})`);
		params.push(...opts.kinds);
	}
	if (opts.statuses?.length) {
		conds.push(`status IN (${opts.statuses.map(() => '?').join(',')})`);
		params.push(...opts.statuses);
	}
	const where = conds.length ? ` WHERE ${conds.join(' AND ')}` : '';
	const rows = db()
		.prepare(`SELECT * FROM mcp_objects${where} ORDER BY kind, obj_key, gen_at DESC`)
		.all(...params) as Row[];
	return rows.map(rowToObject);
}

// Latest non-rejected version per logical key — what consumers play/present.
// Rows whose bundle is missing on this box are dropped (and logged), so
// consumers never see a null payload; the review list keeps them visible.
export function currentObjects(kind: ObjectKind): McpObject[] {
	const rows = db().prepare(OBJECTS_CURRENT_SQL).all(kind) as Row[];
	return rows.map(rowToObject).filter((o) => o.payload !== null);
}

export function setObjectStatus(id: number, status: ObjectStatus, note: string | null): boolean {
	const res = db()
		.prepare(
			"UPDATE mcp_objects SET status = ?, status_note = ?, updated_at = datetime('now') WHERE id = ?"
		)
		.run(status, note, id);
	return res.changes > 0;
}

function db() {
	const d = getDb();
	if (!ensured) {
		d.run(OBJECTS_SCHEMA);
		// CREATE IF NOT EXISTS never extends an existing table; added columns
		// need an explicit migration for DBs created under the older schema.
		const cols = d.prepare("SELECT name FROM pragma_table_info('mcp_objects')").all() as {
			name: string;
		}[];
		if (!cols.some((c) => c.name === 'status_note'))
			d.run('ALTER TABLE mcp_objects ADD COLUMN status_note TEXT');
		ensured = true;
	}
	return d;
}

function readBundle(name: string): unknown[] {
	const cached = bundleCache.get(name);
	if (cached) return cached;
	if (!BUNDLE_RE.test(name)) return [];
	const root = resolve(objectsRoot());
	const path = resolve(join(root, `${name}.jsonl.zst`));
	if (!path.startsWith(root + '/') || !existsSync(path)) {
		if (!warnedBundles.has(name)) {
			warnedBundles.add(name);
			console.error(`[objects] bundle ${name} referenced by mcp_objects but missing on disk`);
		}
		return [];
	}
	const raw = Buffer.from(Bun.zstdDecompressSync(readFileSync(path))).toString('utf-8');
	const lines = raw
		.split('\n')
		.filter((l) => l.trim())
		.map((l) => JSON.parse(l) as unknown);
	bundleCache.set(name, lines);
	return lines;
}

function rowToObject(r: Row): McpObject {
	const entry = readBundle(r.bundle)[r.line] as { payload?: unknown } | undefined;
	return {
		id: r.id,
		kind: r.kind as ObjectKind,
		objKey: r.obj_key,
		bundle: r.bundle,
		line: r.line,
		genAt: r.gen_at,
		etype: r.etype,
		semId: r.sem_id,
		title: r.title,
		status: r.status as ObjectStatus,
		statusNote: r.status_note,
		payload: entry?.payload ?? null,
		createdAt: r.created_at,
		updatedAt: r.updated_at
	};
}
