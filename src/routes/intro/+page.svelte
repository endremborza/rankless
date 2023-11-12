<script lang="ts">
	import rankedUniData from '$lib/assets/data/intro-stats.json';
	import { headLines } from '$lib/assets/data/intro-headlines.json';

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
</script>

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
</style>
