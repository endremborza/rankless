// Seeds a fixture bundle of every geography-quiz card kind when the target
// store holds none, so the game e2e spec has a full daily to play. Run via the
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
const BUNDLE = 'seed-geo-fixture';

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

function card(
	kind: string,
	semId: string,
	name: string,
	payload: Record<string, unknown>
): FixtureObject {
	return {
		kind,
		obj_key: `institutions|${semId}`,
		etype: 'institutions',
		sem_id: semId,
		title: name,
		payload: { semId, name, note: `Fixture note for ${name}.`, papers: 1, citations: 1, ...payload }
	};
}

const inst = (semId: string, name: string, cc = 'AT', city = 'Vienna') => ({
	semId,
	name,
	cc,
	city
});

// Every answer is knowable from the option text alone (tests/game-geo.spec.ts
// matches on it): country cards resolve to Hungary, city cards to Budapest,
// nearest cards to "Near One", intruder and local cards to their anchor. The
// country-card sem-ids are real institutions: serving computes badge
// standings from the local backend (which the e2e suite needs running
// anyway), and a country card without a standing never serves.
const countryCards = ['massey-university', 'embo', 'nwafu', 'brandeis-university'].map((semId, i) =>
	card('country-card', semId, `Fixture Misnomer University ${i + 1}`, {
		cc: 'HU',
		decoys: ['DE', 'FR', 'ES']
	})
);
const intruderCards = [1, 2, 3].map((i) =>
	card('intruder-card', `fixture-intruder-${i}`, `Fixture Intruder ${i}`, {
		cc: 'HU',
		country: 'AT',
		options: [
			inst(`local-a-${i}`, 'Local Uni A'),
			inst(`local-b-${i}`, 'Local Uni B'),
			inst(`local-c-${i}`, 'Local Uni C')
		]
	})
);
const nearestCards = [1, 2, 3].map((i) =>
	card('nearest-card', `fixture-nearest-${i}`, `Fixture Nearest ${i}`, {
		cc: 'HU',
		lat: 47.5,
		lon: 19.05,
		options: [
			{ ...inst(`near-${i}`, 'Near One', 'HU', 'Szeged'), lat: 46.25, lon: 20.15, km: 160 },
			{ ...inst(`far-2-${i}`, 'Far Two', 'DE', 'Munich'), lat: 48.15, lon: 11.58, km: 560 },
			{ ...inst(`far-3-${i}`, 'Far Three', 'FR', 'Paris'), lat: 48.86, lon: 2.35, km: 1250 },
			{ ...inst(`far-4-${i}`, 'Far Four', 'ES', 'Madrid'), lat: 40.42, lon: -3.7, km: 1970 }
		]
	})
);
const cityCards = [1, 2, 3].map((i) =>
	card('city-card', `fixture-city-${i}`, `Fixture Institute ${i}`, {
		cc: 'HU',
		city: 'Budapest',
		decoys: ['Vienna', 'Prague', 'Warsaw']
	})
);
const localCards = [1, 2].map((i) =>
	card('local-card', `fixture-local-${i}`, `Fixture Local ${i}`, {
		cc: 'HU',
		city: 'Budapest',
		options: [
			inst(`away-a-${i}`, 'Away Uni A'),
			inst(`away-b-${i}`, 'Away Uni B'),
			inst(`away-c-${i}`, 'Away Uni C')
		]
	})
);
const objects = [...countryCards, ...intruderCards, ...nearestCards, ...cityCards, ...localCards];

const kinds = [...new Set(objects.map((o) => o.kind))];
const have = db
	.prepare(
		`SELECT count(*) AS n FROM mcp_objects WHERE kind IN (${kinds.map(() => '?').join(',')})`
	)
	.get(...kinds) as { n: number };
if (have.n === 0) {
	mkdirSync(ROOT, { recursive: true });
	const path = join(ROOT, `${BUNDLE}.jsonl.zst`);
	if (!existsSync(path)) {
		const raw = objects.map((c) => JSON.stringify(c)).join('\n') + '\n';
		writeFileSync(path, Bun.zstdCompressSync(raw));
	}
	const insert = db.prepare(
		`INSERT OR IGNORE INTO mcp_objects (kind, obj_key, bundle, line, gen_at, etype, sem_id, title)
		 VALUES (?, ?, ?, ?, '2026-01-01', ?, ?, ?)`
	);
	objects.forEach((c, line) =>
		insert.run(c.kind, c.obj_key, BUNDLE, line, c.etype, c.sem_id, c.title)
	);
	console.log(`[seed-game] inserted fixture bundle ${BUNDLE} with ${objects.length} cards`);
}
db.close();
