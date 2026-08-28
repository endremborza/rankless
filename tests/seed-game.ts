// Seeds fixture game-card / country-card bundles when the target store holds
// none, so the game e2e specs have cards to play against. Run via the
// playwright webServer command (bun), before build + preview; the playwright
// configs point RANKLESS_DB_PATH / MCP_OBJECTS_ROOT at a scratch dir so
// fixtures never touch the real store. Bundle layout must stay identical to
// pyscripts/object_store.py.
import { mkdirSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { Database } from 'bun:sqlite';

import { OBJECTS_SCHEMA } from '../src/lib/server/objects-schema';

const ROOT = process.env.MCP_OBJECTS_ROOT ?? 'data/mcp-objects';
const DB_PATH = process.env.RANKLESS_DB_PATH ?? 'data/rankless.sqlite';

type FixtureObject = {
	kind: string;
	obj_key: string;
	etype: string;
	sem_id: string;
	title: string;
	payload: Record<string, unknown>;
};

mkdirSync(dirname(DB_PATH), { recursive: true });
const db = new Database(DB_PATH);
db.run('PRAGMA busy_timeout = 5000');
db.run('PRAGMA journal_mode = WAL');
db.run(OBJECTS_SCHEMA);

function seedBundle(kind: string, bundle: string, objects: FixtureObject[]) {
	const have = db.prepare('SELECT count(*) AS n FROM mcp_objects WHERE kind = ?').get(kind) as {
		n: number;
	};
	if (have.n > 0) return;
	mkdirSync(ROOT, { recursive: true });
	const path = join(ROOT, `${bundle}.jsonl.zst`);
	if (!existsSync(path)) {
		const raw = objects.map((c) => JSON.stringify(c)).join('\n') + '\n';
		writeFileSync(path, Bun.zstdCompressSync(raw));
	}
	const insert = db.prepare(
		`INSERT OR IGNORE INTO mcp_objects (kind, obj_key, bundle, line, gen_at, etype, sem_id, title)
		 VALUES (?, ?, ?, ?, '2026-01-01', ?, ?, ?)`
	);
	objects.forEach((c, line) =>
		insert.run(c.kind, c.obj_key, bundle, line, c.etype, c.sem_id, c.title)
	);
	console.log(`[seed-game] inserted fixture bundle ${bundle} with ${objects.length} cards`);
}

const clueCards = (
	[
		['fixture-a', 'Fixture University A', 47.5, 19.05],
		['fixture-b', 'Fixture Institute B', -33.9, 151.2]
	] as const
).map(
	([semId, name, lat, lon]): FixtureObject => ({
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
	})
);

// Every country card resolves to HU, so the spec can answer (or miss) at will
// without knowing the shuffled deck order. The sem-ids are real institutions:
// serving computes badge standings from the local backend (which the e2e suite
// needs running anyway), and a card without a standing never serves.
const countryCards = ['massey-university', 'embo', 'nwafu', 'brandeis-university', 'ucc'].map(
	(semId, i): FixtureObject => ({
		kind: 'country-card',
		obj_key: `institutions|${semId}`,
		etype: 'institutions',
		sem_id: semId,
		title: `Fixture Misnomer University ${i + 1}`,
		payload: {
			semId,
			name: `Fixture Misnomer University ${i + 1}`,
			cc: 'HU',
			decoys: ['DE', 'FR', 'ES'],
			note: `Fixture note ${i + 1}: it is in Hungary after all.`,
			papers: 1,
			citations: 1
		}
	})
);

seedBundle('game-card', 'seed-game-fixture', clueCards);
seedBundle('country-card', 'seed-country-fixture', countryCards);
db.close();
