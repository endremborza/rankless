import fs from 'node:fs';
import path from 'node:path';
import { expect, test } from './coverage/fixtures';
import { XMLParser } from 'fast-xml-parser';

// Collects structured data from curated + sampled entity pages into logs/sanity_check_data.json.
// The test itself always passes — the Python analyzer (pyscripts/sanity_check.py) does validation.

test.describe.configure({ timeout: 360_000 });

const ROOT_TYPES = [
	'authors',
	'institutions',
	'sources',
	'countries',
	'subfields',
	'hit-papers'
] as const;

const CURATED: { url: string; expectedDomain: string }[] = [
	{ url: '/authors/daron-acemoglu', expectedDomain: 'economics, political economy' },
	{ url: '/authors/robert-langer', expectedDomain: 'biomedical engineering, drug delivery' },
	{ url: '/authors/yoshua-bengio', expectedDomain: 'deep learning, machine learning' },
	{
		url: '/institutions/mit',
		expectedDomain: 'broad research university'
	},
	{ url: '/institutions/harvard-university', expectedDomain: 'broad research university' },
	{ url: '/sources/nature', expectedDomain: 'multidisciplinary science' },
	{ url: '/sources/the-lancet', expectedDomain: 'medicine, clinical research' },
	{ url: '/countries/usa', expectedDomain: 'broad research' },
	{ url: '/countries/jpn', expectedDomain: 'broad research' },
	{
		url: '/subfields/artificial-intelligence',
		expectedDomain: 'computer science, machine learning'
	},
	{ url: '/subfields/organic-chemistry', expectedDomain: 'chemistry' }
];

// Widen + randomize: per root type we sample this many entities, picked at random
// from the sitemap so every run reviews a different slice. Override with
// EXPLORE_SAMPLE_PER_TYPE. Curated entities (above) are always included on top.
const SAMPLE_PER_TYPE = Number(process.env.EXPLORE_SAMPLE_PER_TYPE ?? 8);

function shuffle<T>(arr: T[]): T[] {
	for (let i = arr.length - 1; i > 0; i--) {
		const j = Math.floor(Math.random() * (i + 1));
		[arr[i], arr[j]] = [arr[j], arr[i]];
	}
	return arr;
}

type EntitySnapshot = {
	url: string;
	rootType: string;
	name: string;
	stats: string;
	fields: string[];
	leaders: { label: string; items: string[] }[];
	aboutText: string;
	expectedDomain?: string;
};

async function sitemapUrls(type: string): Promise<string[]> {
	const res = await fetch(`http://localhost:4173/sitemap-entity-${type}-1.xml`);
	expect(res.ok, `sitemap-entity-${type}-1.xml returned ${res.status}`).toBeTruthy();
	// parseTagValue:false keeps <loc> as strings (no numeric coercion); we now scan
	// the whole sitemap to randomize, so skip any malformed/empty entry defensively.
	const parsed = new XMLParser({ parseTagValue: false }).parse(await res.text());
	const entries = parsed?.urlset?.url;
	const arr = Array.isArray(entries) ? entries : entries ? [entries] : [];
	const paths: string[] = [];
	for (const u of arr) {
		if (typeof u?.loc !== 'string') continue;
		try {
			paths.push(new URL(u.loc).pathname);
		} catch {
			// skip malformed sitemap entries
		}
	}
	return paths;
}

async function extractSnapshot(
	page: import('@playwright/test').Page,
	url: string,
	expectedDomain?: string
): Promise<EntitySnapshot> {
	const rootType = url.split('/')[1];

	const name = await page
		.locator('#overview h1')
		.textContent({ timeout: 20_000 })
		.then((t) => t?.trim() ?? '');

	const stats = await page
		.locator('#overview .stat')
		.textContent()
		.then((t) => t?.trim() ?? '');

	const fields = await page.$$eval('.chip-name', (els) =>
		els.map((e) => e.textContent?.trim() ?? '')
	);

	const leaders = await page.$$eval('.leader', (els) =>
		els.map((el) => ({
			label: el.querySelector('dt')?.textContent?.trim() ?? '',
			items: Array.from(el.querySelectorAll('dd a, dd span')).map(
				(a) => a.textContent?.trim() ?? ''
			)
		}))
	);

	const aboutText = await page
		.locator('.about-seo p')
		.first()
		.textContent({ timeout: 5_000 })
		.catch(() => '');

	return {
		url,
		rootType,
		name,
		stats,
		fields,
		leaders,
		aboutText: aboutText?.trim() ?? '',
		...(expectedDomain ? { expectedDomain } : {})
	};
}

test('collect entity page data for sanity checking', async ({ page }) => {
	const snapshots: EntitySnapshot[] = [];

	// Per type, how many curated anchors we already have (counted toward the quota).
	const curatedByType = new Map<string, number>();
	for (const c of CURATED) {
		const rootType = c.url.split('/')[1];
		curatedByType.set(rootType, (curatedByType.get(rootType) ?? 0) + 1);
	}

	// Build a randomized sample list once: for each type, shuffle the sitemap and
	// take enough fresh (non-curated) urls to reach SAMPLE_PER_TYPE.
	const curatedUrls = new Set(CURATED.map((c) => c.url));
	const sampled: string[] = [];
	for (const type of ROOT_TYPES) {
		const need = Math.max(0, SAMPLE_PER_TYPE - (curatedByType.get(type) ?? 0));
		if (need === 0) continue;
		const pool = (await sitemapUrls(type)).filter((u) => !curatedUrls.has(u));
		for (const u of shuffle(pool).slice(0, need)) {
			curatedUrls.add(u);
			sampled.push(u);
		}
	}

	// Navigate and extract: curated anchors first, then the randomized sample.
	await page.goto('/');
	for (const curated of CURATED) {
		await page.goto(curated.url, { waitUntil: 'networkidle' });
		snapshots.push(await extractSnapshot(page, curated.url, curated.expectedDomain));
	}
	for (const url of sampled) {
		await page.goto(url, { waitUntil: 'networkidle' });
		snapshots.push(await extractSnapshot(page, url));
	}

	const logsDir = path.resolve('logs');
	fs.mkdirSync(logsDir, { recursive: true });
	fs.writeFileSync(
		path.join(logsDir, 'sanity_check_data.json'),
		JSON.stringify(snapshots, null, 2) + '\n'
	);
});
