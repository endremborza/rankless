import { type Page } from '@playwright/test';
import { test, expect } from './coverage/fixtures';
import { sitemapEntityUrls } from './helpers';

const BE_URL = process.env.BE_URL || 'http://127.0.0.1:3038/v1';

type Spec = {
	defaultIsSpec: boolean;
	breakdowns: { attributeType: string; sourceSide: boolean }[];
};
type Tree = {
	tree: { linkCount: number; children: Record<string, { linkCount: number }> };
	atts: { authors: Record<string, { specBaseline?: number }> };
};

// A branch is filled with a gradient keyed by its path in the tree, so a first-level branch's key is
// a bare dm id and deeper ones are hyphenated. Reading the keys left to right gives the order the
// tree is drawn in, without depending on label text or on how the labels are broken across lines.
async function firstLevelOrder(page: Page): Promise<number[]> {
	return page.evaluate(() => {
		const prefix = "url('#path-grad-";
		return [...document.querySelectorAll(`#impact svg path[fill^="${prefix}"]`)]
			.map((p) => ({
				key: p.getAttribute('fill')!.slice(prefix.length, -2),
				x: p.getBoundingClientRect().left
			}))
			.filter(({ key }) => !key.includes('-'))
			.sort((a, b) => a.x - b.x)
			.map(({ key }) => Number(key));
	});
}

// Switching the first-level breakdown lands the new tree, its spec and the ranking basis in one
// batch, and a `$:` statement runs at most once per flush: a basis that is synced into the control
// spec by a separate statement is written after the statement that consumes it, so the tree is drawn
// with the outgoing breakdown's basis until something else re-derives it. The author breakdown is
// the only institutions one ranked by citation volume, so entering it from any other breakdown is
// the transition that shows it.
test('the tree ranks by the new basis on the first render after a breakdown switch', async ({
	page
}) => {
	const specs: { specs: { institutions: Spec[] } } = await (await fetch(`${BE_URL}/specs`)).json();
	const treeId = specs.specs.institutions.findIndex(
		(s) => !s.defaultIsSpec && s.breakdowns[0].attributeType === 'authors'
	);
	expect(treeId, 'no volume-ranked author breakdown to switch into').toBeGreaterThan(-1);
	const { attributeType, sourceSide } = specs.specs.institutions[treeId].breakdowns[0];

	const [url] = await sitemapEntityUrls('institutions', 1);
	test.skip(!url, 'no institution sitemap entries');
	await page.goto(url, { waitUntil: 'load' });
	await page.waitForSelector('#impact .sentenceline select', { timeout: 20_000 });

	await page
		.locator('#impact .sentenceline select')
		.first()
		.selectOption(`${attributeType}-${sourceSide}`);
	await expect.poll(async () => (await firstLevelOrder(page)).length).toBeGreaterThan(2);
	await page.waitForTimeout(1000); // branch geometry transitions for 0.8s

	const shown = await firstLevelOrder(page);
	const semanticId = url.split('/').slice(2).join('/');
	const year = await page.locator('#impact select[aria-label="Since year"]').inputValue();
	const tree: Tree = await (
		await fetch(`${BE_URL}/trees/institutions/${semanticId}?tid=${treeId}&year=${year}`)
	).json();

	const volume = (id: number) => tree.tree.children[id].linkCount;
	const rate = (id: number) => volume(id) / tree.tree.linkCount;
	const specialization = (id: number) =>
		rate(id) / (tree.atts.authors[id]?.specBaseline || rate(id) * 0.5);
	// Ties fall back to the descending dm id the tree itself orders them by.
	const byVolume = [...shown].sort((a, b) => volume(b) - volume(a) || b - a);
	const bySpecialization = [...shown].sort(
		(a, b) => specialization(b) - specialization(a) || b - a
	);

	expect(
		bySpecialization,
		'this entity ranks the same on either basis, so the check is vacuous'
	).not.toEqual(byVolume);
	expect(shown).toEqual(byVolume);

	// Re-deriving the same state must leave the drawing alone; nudging the branch count and putting
	// it back is the cheapest control that forces one.
	const slider = page.locator('#impact input[type=range]').first();
	const branches = await slider.inputValue();
	await slider.fill(String(Number(branches) + 1));
	await slider.fill(branches);
	await page.waitForTimeout(1000);
	expect(await firstLevelOrder(page)).toEqual(shown);
});
