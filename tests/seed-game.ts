// Seeds a fixture game-card bundle when the target store holds none, so the
// game e2e spec has cards to play against. Run via the playwright webServer
// command (bun), before build + preview; the playwright configs point
// RANKLESS_DB_PATH / MCP_OBJECTS_ROOT at a scratch dir so fixtures never touch
// the real store. Bundle layout must stay identical to pyscripts/object_store.py.
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { Database } from 'bun:sqlite';

import { OBJECTS_SCHEMA } from '../src/lib/server/objects-schema';

const BUNDLE = 'seed-game-fixture';
const ROOT = process.env.MCP_OBJECTS_ROOT ?? 'data/mcp-objects';
const DB_PATH = process.env.RANKLESS_DB_PATH ?? 'data/rankless.sqlite';

mkdirSync(dirname(DB_PATH), { recursive: true });
const db = new Database(DB_PATH);
db.run('PRAGMA busy_timeout = 5000');
db.run('PRAGMA journal_mode = WAL');
db.run(OBJECTS_SCHEMA);

const have = db.prepare("SELECT count(*) AS n FROM mcp_objects WHERE kind = 'game-card'").get() as {
	n: number;
};
if (have.n === 0) {
	const cards = (
		[
			['fixture-a', 'Fixture University A', 47.5, 19.05],
			['fixture-b', 'Fixture Institute B', -33.9, 151.2]
		] as const
	).map(([semId, name, lat, lon]) => ({
		kind: 'game-card',
		obj_key: `institutions|${semId}`,
		etype: 'institutions',
		sem_id: semId,
		title: name,
		payload: {
			semId,
			name,
			cc: 'HU',
			lat,
			lon,
			papers: 1,
			citations: 1,
			clues: Array.from({ length: 6 }, (_, i) => ({
				stage: i + 1,
				text: `Fixture clue ${i + 1} for ${semId}.`,
				facts: []
			}))
		}
	}));
	mkdirSync(ROOT, { recursive: true });
	const path = join(ROOT, `${BUNDLE}.jsonl.zst`);
	if (!existsSync(path)) {
		const raw = cards.map((c) => JSON.stringify(c)).join('\n') + '\n';
		writeFileSync(path, Bun.zstdCompressSync(raw));
	}
	const insert = db.prepare(
		`INSERT OR IGNORE INTO mcp_objects (kind, obj_key, bundle, line, gen_at, etype, sem_id, title)
		 VALUES (?, ?, ?, ?, '2026-01-01', ?, ?, ?)`
	);
	cards.forEach((c, line) =>
		insert.run(c.kind, c.obj_key, BUNDLE, line, c.etype, c.sem_id, c.title)
	);
	console.log('[seed-game] inserted fixture bundle with 2 cards');
}
db.close();
