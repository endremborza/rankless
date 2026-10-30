import { TREE_SPECS } from '../src/lib/wire/rankless_server/responses';
import { test, expect } from './coverage/fixtures';
import {
	BE_URL,
	BREAKDOWN_SELECT,
	YEAR_SELECT,
	firstLevelOrder,
	openFirstInstitution,
	settledOrder
} from './helpers';

type Tree = {
	tree: { linkCount: number; children: Record<string, { linkCount: number }> };
	atts: { authors: Record<string, { specBaseline?: number }> };
};

// Switching the first-level breakdown lands the new tree, its spec and the ranking basis in one
// batch, and a `$:` statement runs at most once per flush: a basis that is synced into the control
// spec by a separate statement is written after the statement that consumes it, so the tree is drawn
// with the outgoing breakdown's basis until something else re-derives it. The author breakdown is
// the only institutions one ranked by citation volume, so entering it from any other breakdown is
// the transition that shows it.
test('the tree ranks by the new basis on the first render after a breakdown switch', async ({
	page
}) => {
	const specs = TREE_SPECS.specs.institutions;
	const treeId = specs.findIndex(
		(s) => !s.defaultIsSpec && s.breakdowns[0].attributeType === 'authors'
	);
	expect(treeId, 'no volume-ranked author breakdown to switch into').toBeGreaterThan(-1);
	const { attributeType, sourceSide } = specs[treeId].breakdowns[0];

	const url = await openFirstInstitution(page);

	await page.locator(BREAKDOWN_SELECT).first().selectOption(`${attributeType}-${sourceSide}`);
	await expect.poll(async () => (await firstLevelOrder(page)).length).toBeGreaterThan(2);

	const shown = await settledOrder(page);
	const semanticId = url.split('/').slice(2).join('/');
	const year = await page.locator(YEAR_SELECT).inputValue();
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
	expect(await settledOrder(page)).toEqual(shown);
});
