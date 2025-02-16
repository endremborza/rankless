<script lang="ts">
	import rankedUniData from '$lib/assets/data/intro-stats.json';
	import { headLines } from '$lib/assets/data/intro-headlines.json';
	import dStats from '$lib/assets/data/desc-stats.json';
	import oalexConcepts from '$lib/assets/data/concept-hier.json';

	import TileTreeMap from '$lib/components/TileTreeMap.svelte';
	import type { OMap, NamedNode } from '$lib/tree-types';

	let scrollState = 0;
	const scrollStepSize = 1000;
	const minFrame = -2;
	const maxFrame = 15;

	$: currentFrameNum = Math.floor(scrollState / scrollStepSize);

	function getMinHeadline<T>(i: number, frames: T) {
		for (const frame of frames) {
			if (frame.frame >= i) {
				return frame;
			}
		}
		return frames[frames.length - 1];
	}

	$: currentHeadline = getMinHeadline(currentFrameNum, headLines).text;

	//maybe include RCA?
	// 1. ranking, cross out and remove rankings and scores, move name out of tile
	// 2. globally topics
	// 3. continent divided countries, rejoin before redivide
	// + how much data is used  -> you know exactly what is behind it

	type SvgFrame = {
		frame: number;
		elems: OMap<{
			x: number;
			y: number;
			height: number;
			width: number;
			data: NamedNode;
			combined: boolean;
		}>;
		texts: { x: number; y: number; text: string }[];
	};

	function getFrames(): SvgFrame[] {
		const trueFrames = [];

		for (const frameNum of [0, 2, 3, 5, 9]) {
			const texts = [];
			let elems = {};
			for (const [i, [uniK, uniD]] of Object.entries(rankedUniData).entries()) {
				if (frameNum > 2) {
					texts.push({ x: 110 + 330 * i, y: 50, text: uniD.name });
				}

				if (frameNum < 2) {
					texts.push({
						x: 700,
						y: 150 + 330 * i,
						text: 'Shanghai 2023 Rank: ' + uniD.outsideRanks.ShaRank
					});
					texts.push({
						x: 700,
						y: 220 + 330 * i,
						text: 'THE 2024 Rank: ' + uniD.outsideRanks.TheRank
					});
					texts.push({
						x: 700,
						y: 290 + 330 * i,
						text: 'THE 2024 Score: ' + uniD.outsideRanks.TheScore
					});
				}

				elems[uniK.toString()] = {
					x: frameNum < 2 ? 50 : 100 + 330 * i,
					y: frameNum < 2 ? 100 + 330 * i : 50,
					height: frameNum < 2 ? 220 : 900,
					width: frameNum < 2 ? 600 : 220,
					data: frameNum < 4 ? uniD.conceptTree : uniD.countryTree,
					combined: frameNum < 3
				};
			}
			trueFrames.push({ frame: frameNum, texts, elems });
		}
		return trueFrames;
	}

	const trueFrames = getFrames();

	let currentSvgFrame: SvgFrame;
	$: currentSvgFrame = getMinHeadline(currentFrameNum, trueFrames);

	function changeScroll(e: WheelEvent) {
		scrollState = Math.min(
			Math.max(scrollState - e.wheelDeltaY, minFrame * scrollStepSize),
			maxFrame * scrollStepSize
		);
	}

	import { formatNumber } from '$lib/text-format-util';

	import BrokenFittedText from '$lib/components/BrokenFittedText.svelte';
	import { onMount } from 'svelte';

	type TextAtt = { x: number; y: number; width: number; height: number };

	let innerWidth: number;
	let viewBox: string;
	let subjectTextAtts: TextAtt;
	let subjectNumAtts: TextAtt;

	function getSvgShape(width: number) {
		viewBox = '-300 0 1600 1000';
		subjectTextAtts = { x: -250, y: 500, width: 230, height: 140 };
		subjectNumAtts = { x: 1020, y: 450, width: 230, height: 80 };
		if (width < 1200) {
			viewBox = '0 -200 1000 1200';
			subjectTextAtts = { x: 25, y: -10, width: 500, height: 140 };
			subjectNumAtts = { x: 650, y: -100, width: 300, height: 80 };
		}
	}

	const dCards = [
		{ desc: 'Works', num: dStats.counts.work, color: 15 },
		{ desc: 'Institutions', num: dStats.counts.inst, color: 25 },
		{ desc: 'Citations', num: dStats.counts.cite, color: 50 },
		{ desc: 'Countries', num: dStats.counts.country, color: 90 }
	];

	let childNames = Object.values(oalexConcepts.children).map((e) => e.name);
	let childInd = 0;

	function updateGraph() {
		if (childInd == childNames.length * 4) {
			openChildren = [];
			expandedChild = undefined;
			explainBox = undefined;
			childInd = 0;
		} else {
			if (childInd % 4 == 0) {
				openChildren = [childNames[childInd / 4]];
				explainBox = Object.values(oalexConcepts.children).filter(
					(n) => n.name == openChildren[0]
				)[0];
			} else if (childInd % 4 == 1) {
				expandedChild = childNames[(childInd - 1) / 4];
			} else if (childInd % 4 == 2) {
				//expandedChild = childNames[(childInd - 1) / 4];
			} else {
				explainBox = undefined;
				expandedChild = undefined;
				openChildren = [];
			}
			childInd++;
		}
	}

	onMount(() => {
		setInterval(updateGraph, 3500);
	});

	let expandedChild: string | undefined = undefined;
	let openChildren: string[] = [];
	let explainBox: undefined | { cited_by_count: number; works_count: number; name: string } =
		undefined;

	$: getSvgShape(innerWidth);
	$: lowerNumAtts = { ...subjectNumAtts, y: subjectNumAtts.y + 90 };
</script>

<div class="bstrip" id="tile-strip">
	<svg id="concept-tiles" {viewBox}>
		<g id="tmviz">
			<TileTreeMap
				data={oalexConcepts}
				maxPad={10}
				{openChildren}
				{expandedChild}
				transitionMs={1200}
			/>
		</g>
		{#if explainBox != undefined}
			<BrokenFittedText text={explainBox.name} {...subjectTextAtts} />
			<BrokenFittedText
				text="{formatNumber(explainBox.cited_by_count, 0)} citations"
				{...subjectNumAtts}
			/>
			<BrokenFittedText text="{formatNumber(explainBox.works_count, 0)} works" {...lowerNumAtts} />
		{/if}
	</svg>
</div>
<div on:wheel={changeScroll} class="main">
	<div class="left">
		<h1>{scrollState}</h1>
		<h1>{currentHeadline}</h1>
	</div>
	<div class="right">
		<svg width="80%" height="80%" viewBox="-50 -50 {1100} {1100}">
			{#each Object.entries(currentSvgFrame.elems) as [k, frame]}
				<g style="--x-off: {frame.x}px; --y-off: {frame.y}px">
					<TileTreeMap
						data={frame.data}
						width={frame.width}
						height={frame.height}
						combined={frame.combined}
						transitionMs={900}
					/>
				</g>
			{/each}
			{#each currentSvgFrame.texts as textElem}
				<g style="--x-off: {textElem.x}px; --y-off: {textElem.y}px">
					<text>{textElem.text}</text>
				</g>
			{/each}
		</svg>
	</div>
</div>

<style>
	.main {
		height: 100%;
		display: flex;
	}

	h1 {
		padding: 20px;
		transition: 400ms;
	}

	.left {
		flex: 1 1 700px;
		display: flex;
		align-items: center;
	}

	.right {
		flex: 2 2 1400px;
	}

	#card-block {
		margin-top: 70px;
		margin-bottom: 40px;
	}

	#tile-strip {
		padding-top: 80px;
		padding-bottom: 80px;
		background-color: var(--color-theme-lightblue);
	}

	#concept-tiles {
		height: 800px;
		max-height: min(80svh, 110vw);
		width: 100%;
	}

	.b-card {
		display: flex;
		justify-content: end;
		font-weight: bold;
		padding: 30px;
		padding-top: 18px;
		padding-bottom: 18px;
		margin: 20px;
		flex: 0 0 200px;
		box-shadow: 0px 4px 13px 0px rgba(0, 0, 0, 0.25);
	}

	.card-text {
		text-align: right;
		font-size: 18px;
	}

	.card-desc {
		font-weight: 300;
	}

	.card-box {
		width: 44px;
		height: 44px;
		margin-left: 20px;
		opacity: 75%;
	}
</style>
