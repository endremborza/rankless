<script lang="ts">
	import { LATEST_YEAR } from '$lib/constants';
	import { getColor, getColorArr } from '$lib/style-util';
	import { formatNumber } from '$lib/text-format-util';
	import type * as tt from '$lib/tree-types';
	import { onMount } from 'svelte';

	export let papers: tt.Paper[];
	const xPad = 2;
	const yPad = 1;
	const xBase = 26;
	const yBase = 12;
	const maxN = 5;
	const fontSize = 0.5;
	let highlighted = 0;
	//TODO!! - scrolling fails in brave!

	let listContainer: HTMLUListElement;
	let listItemElements: HTMLLIElement[] = [];
	let firstVisible: number | null = null;
	let intervalSetup: number;
	let scrollTimeout: ReturnType<typeof setTimeout>;

	function getVisInds(papers: tt.Paper[], first: number) {
		const inds = [];
		const endI = Math.min(papers.length, first + maxN);
		for (let i = first; i < endI; i++) inds.push(i);
		return inds;
	}

	function getFigureBasis(papers: tt.Paper[], inds: number[]) {
		let minYear = LATEST_YEAR;
		let paper: tt.Paper;
		let cMax = 0;
		let nPapers = inds.length;
		for (const i of inds) {
			paper = papers[i];
			if (paper.year < minYear) {
				minYear = paper.year;
			}
			if (paper.citations > cMax) {
				cMax = paper.citations;
			}
		}

		const yearSpan = LATEST_YEAR - minYear;
		const width = xBase + xPad * 2;
		const height = yBase + yPad * 2;
		const xMin = -xPad;
		const yMin = -height + yPad;
		const aspect = width / height;
		const yScale = cMax / yBase;
		const xScale = (yearSpan - 1) / xBase;
		let figPapers = [];
		for (const i of inds) {
			paper = papers[i];
			let startYear = paper.year - minYear;
			let cCum = 0;
			const pBasis = [];
			for (const [y, yCites] of paper.yearlyCites.entries()) {
				if (y + startYear + minYear >= LATEST_YEAR) break;
				cCum -= yCites / yScale;
				const ch = y == 0 ? 'M' : 'L';
				pBasis.push(`${ch} ${(startYear + y) / xScale} ${cCum}`);
			}
			pBasis.push(`V 0 H ${startYear / xScale} z`);
			let pNameMax = Math.floor(((LATEST_YEAR - paper.year) / xScale) * 3.5);
			let pathName = paper.name;
			if (pathName.length + 3 > pNameMax) {
				pathName = pathName.slice(0, pNameMax) + '...';
			}
			figPapers.push({
				i,
				rate: (i - inds[0]) / nPapers,
				path: pBasis.join(' '),
				name: paper.name,
				doi: paper.doi,
				pathName,
				year: paper.year,
				citations: paper.citations
			});
		}

		const yearTicks = [
			{ name: minYear, x: 0 },
			{ name: LATEST_YEAR, x: xBase }
		];
		const toT = (i: number, k: number) => i == Math.floor((k * yearSpan) / 3);
		for (let i = 1; i < yearSpan - 1; i++) {
			let name = toT(i, 1) || toT(i, 2) ? minYear + i : undefined;
			yearTicks.push({ name, x: i / xScale });
		}

		return { width, height, xMin, yMin, figPapers, yearTicks, aspect, cMax };
	}

	function fixHighlight(i: number) {
		clearInterval(intervalSetup);
		highlighted = i;
	}

	function getLiStyle(i: number, visInds: number[], highlighted: number | undefined) {
		if (visInds.includes(i)) {
			let rate = (i - visInds[0]) / visInds.length;
			let ext =
				highlighted == i ? '0.5); box-shadow: 3px 3px 10px var(--color-theme-shadow);' : '0.3)';
			return `background-color: rgba(${getColorArr(rate)}, ${ext}`;
		}
		return '';
	}

	function updateFirstVisible(): void {
		const containerRect = listContainer.getBoundingClientRect();

		const fullyVisibleItems = listItemElements
			.map((el, index) => ({ el, index, rect: el.getBoundingClientRect() }))
			.filter(({ rect }) => rect.top >= containerRect.top && rect.bottom <= containerRect.bottom)
			.sort((a, b) => a.rect.top - b.rect.top);

		firstVisible = fullyVisibleItems.length > 0 ? fullyVisibleItems[0].index : null;
	}

	function onScrollDebounced() {
		clearTimeout(scrollTimeout);
		scrollTimeout = setTimeout(() => {
			updateFirstVisible();
		}, 50);
	}

	onMount(() => {
		intervalSetup = setInterval(() => {
			highlighted = (highlighted + 1) % fb.figPapers.length;
		}, 1200);

		listItemElements = Array.from(listContainer.querySelectorAll('li[data-index]'));
		listContainer.addEventListener('scroll', onScrollDebounced);
		updateFirstVisible();
	});

	$: visInds = getVisInds(papers, firstVisible || 0);
	$: fb = getFigureBasis(papers, visInds);
	$: highlightedVis = visInds.includes(highlighted) ? highlighted - visInds[0] : undefined;
</script>

<div>
	<svg
		viewBox="{fb.xMin} {fb.yMin} {fb.width} {fb.height}"
		style="aspect-ratio: {fb.aspect.toFixed(3)};"
	>
		{#each fb.figPapers as paper}
			<path
				role="region"
				fill={getColor(paper.rate)}
				stroke="none"
				d={paper.path}
				opacity={paper.i == highlighted ? 0.95 : 0.2}
				id="hit-paper-path-{paper.i}"
				on:mouseover={() => fixHighlight(paper.i)}
				on:focus={() => fixHighlight(paper.i)}
			/>
		{/each}
		{#if highlightedVis != undefined}
			<text font-size="0.4">
				<textPath href="#hit-paper-path-{highlighted}">
					{fb.figPapers[highlightedVis].pathName}
				</textPath>
			</text>
		{/if}

		<g stroke-width="0.03" stroke="var(--color-text)" font-size={fontSize}>
			<path d="M 0, 0 h {xBase}" />
			{#each fb.yearTicks as yTick}
				<path d="M {yTick.x}, 0 v {yPad / 4}" />
				{#if yTick.name != undefined}
					<text x={yTick.x} y={yPad * 0.9} text-anchor="middle">{yTick.name}</text>
				{/if}
			{/each}
			<path d="M {xBase}, {-yBase} h {xPad / 8}" />
			<text x={xBase + xPad / 4} y={-yBase + fontSize / 3.5} text-anchor="left"
				>{formatNumber(fb.cMax)}</text
			>
		</g>
	</svg>

	<ol id="paper-list" bind:this={listContainer}>
		{#each papers as paper, i}
			<li
				style={getLiStyle(i, visInds || [], highlighted)}
				data-index={i}
				on:mouseover={() => fixHighlight(i)}
				on:focus={() => fixHighlight(i)}
			>
				{#if paper.doi.length > 0}
					<a href={paper.doi} target="_blank">{paper.name} ({paper.year})</a>
				{:else}
					{paper.name} ({paper.year})
				{/if}
			</li>
		{/each}
	</ol>
</div>

<style>
	div {
		display: flex;
		flex-wrap: wrap;
	}

	svg {
		min-width: 600px;
		flex: 8;
	}

	text {
		pointer-events: none;
	}

	path,
	li {
		transition: all 400ms;
	}

	#paper-list {
		flex: 4;
		min-width: 400px;
		padding-top: 40px;
		padding-right: 18px;
		max-height: 55svh;
		overflow-y: scroll;
	}

	#paper-list > li {
		margin-top: var(--unified-margin);
		padding: var(--unified-padding);
		font-weight: 600;
	}
</style>
