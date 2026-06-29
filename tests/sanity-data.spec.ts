import fs from 'node:fs';
import path from 'node:path';
import { expect, test } from './coverage/fixtures';
import { XMLParser } from 'fast-xml-parser';

// Collects structured data from curated + sampled entity pages into logs/sanity_check_data.json.
// The test itself always passes — the Python analyzer (pyscripts/sanity_check.py) does validation.

test.describe.configure({ timeout: 180_000 });

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

const SAMPLE_PER_TYPE = 3;

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

async function sitemapUrls(type: string, n: number): Promise<string[]> {
	const res = await fetch(`http://localhost:4173/sitemap-entity-${type}-1.xml`);
	expect(res.ok, `sitemap-entity-${type}-1.xml returned ${res.status}`).toBeTruthy();
	const parsed = new XMLParser().parse(await res.text());
	const entries = parsed?.urlset?.url;
	const arr = Array.isArray(entries) ? entries : entries ? [entries] : [];
	return arr.slice(0, n).map((u: { loc: string }) => new URL(u.loc).pathname);
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

	// Curated entities
	const curatedByType = new Map<string, string[]>();
	for (const c of CURATED) {
		const rootType = c.url.split('/')[1];
		curatedByType.set(rootType, [...(curatedByType.get(rootType) ?? []), c.url]);
	}

	// Sample additional entities from sitemaps, excluding curated ones
	const curatedUrls = new Set(CURATED.map((c) => c.url));
	for (const type of ROOT_TYPES) {
		const alreadyHave = (curatedByType.get(type) ?? []).length;
		const need = Math.max(0, SAMPLE_PER_TYPE - alreadyHave);
		if (need > 0) {
			const urls = await sitemapUrls(type, need + 10);
			const fresh = urls.filter((u) => !curatedUrls.has(u)).slice(0, need);
			for (const u of fresh) curatedUrls.add(u);
		}
	}

	// Navigate and extract: curated first
	await page.goto('/');
	for (const curated of CURATED) {
		await page.goto(curated.url, { waitUntil: 'networkidle' });
		snapshots.push(await extractSnapshot(page, curated.url, curated.expectedDomain));
	}

	// Then sampled
	for (const type of ROOT_TYPES) {
		const alreadyHave = (curatedByType.get(type) ?? []).length;
		const need = Math.max(0, SAMPLE_PER_TYPE - alreadyHave);
		if (need > 0) {
			const urls = await sitemapUrls(type, need + 10);
			const fresh = urls.filter((u) => !CURATED.some((c) => c.url === u)).slice(0, need);
			for (const url of fresh) {
				await page.goto(url, { waitUntil: 'networkidle' });
				snapshots.push(await extractSnapshot(page, url));
			}
		}
	}

	const logsDir = path.resolve('logs');
	fs.mkdirSync(logsDir, { recursive: true });
	fs.writeFileSync(
		path.join(logsDir, 'sanity_check_data.json'),
		JSON.stringify(snapshots, null, 2) + '\n'
	);
});
