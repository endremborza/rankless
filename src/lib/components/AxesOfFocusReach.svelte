<script lang="ts">
	import BrokenFittedText from './BrokenFittedText.svelte';
	import HoverI from '$lib/components/HoverI.svelte';
	import HoverBlock from '$lib/components/HoverBlock.svelte';
	import { getColor } from '$lib/style-util';

	export let data: {
		view: {
			sfCoords: [number, number];
			comparisons: [{ sfCoords: [number, number]; name: string }];
		};
	};
	let axEnds = 3.5;
	let axWidth = 0.032;
	let colorRange = [0.05, 0.3, 0.55, 0.8].map(getColor);
	let axEndLabels = {
		yPlus: 'Field-Specific Impact',
		yMinus: 'Wide Academic Reach',
		xPlus: 'Focused Research',
		xMinus: 'Broad Publications'
	};
	let quadrantNames = {
		NW: 'Boundary Explorers',
		NE: 'Field Anchors',
		SE: 'Broad Impact Specialists',
		SW: 'Knowledge Integrators'
	};
	let showAxesHelp = false;
	let showComparisons = false;
	let hoveredName = '';
</script>

<div id="sf-map">
	<h3 class="mid-head">
		Axes of Focus &amp Reach
		<HoverI bind:hoverToggle={showAxesHelp} />
	</h3>
	<HoverBlock show={showAxesHelp} style={'x: 0; y:0;'}
		>The position on this graph is based in the entropy of the categorization of the papers. For the
		horizontal axis, the entropy for the subfields of the published papers are calculated, for the
		vertical axis the entropy for the papers citing these papers are calculated. To make the graph
		more reliable and easier to read, PCA based dimension reduction and some normalizing monotonic
		transformations are applied</HoverBlock
	>
	<svg viewBox="-4 -4 8 8" class="map-svg">
		<defs>
			<marker
				id="arrow"
				viewBox="0 0 10 10"
				refX="5"
				refY="5"
				markerWidth="6"
				markerHeight="6"
				orient="auto-start-reverse"
			>
				<path d="M 0 0 L 10 5 L 0 10 z" />
			</marker>
		</defs>
		<g id="quadrant-bgs" fill-opacity="0.22">
			<rect y={-axEnds} x={-axEnds} height={axEnds} width={axEnds} fill={colorRange[0]} />
			<rect y={-axEnds} height={axEnds} width={axEnds} fill={colorRange[1]} />
			<rect height={axEnds} width={axEnds} fill={colorRange[2]} />
			<rect x={-axEnds} height={axEnds} width={axEnds} fill={colorRange[3]} />
		</g>

		<g id="quadrants" fill-opacity="0.65">
			<g fill={colorRange[0]}>
				<BrokenFittedText
					x={-axEnds / 2}
					y={-axEnds / 2 + 0.35}
					text={quadrantNames.NW}
					width={axEnds / 2}
					height={0.7}
					anchor={'center'}
				/>
			</g>
			<g fill={colorRange[1]}>
				<BrokenFittedText
					x={axEnds / 2}
					y={-axEnds / 2 + 0.35}
					text={quadrantNames.NE}
					width={axEnds / 2}
					height={0.7}
					anchor={'center'}
				/>
			</g>
			<g fill={colorRange[2]}>
				<BrokenFittedText
					x={axEnds / 2}
					y={axEnds / 2 + 0.35}
					text={quadrantNames.SE}
					width={axEnds / 2}
					height={0.7}
					anchor={'center'}
				/>
			</g>
			<g fill={colorRange[3]}>
				<BrokenFittedText
					x={-axEnds / 2}
					y={axEnds / 2 + 0.35}
					text={quadrantNames.SW}
					width={axEnds / 2}
					height={0.7}
					anchor={'center'}
				/>
			</g>
		</g>

		<line
			x1="0"
			y1="-{axEnds}"
			x2="0"
			y2={axEnds}
			stroke="black"
			stroke-width={axWidth}
			marker-start="url(#arrow)"
			marker-end="url(#arrow)"
		/>
		<line
			x1={-axEnds - axWidth * 3}
			y1="0"
			x2={axEnds + axWidth * 3}
			y2="0"
			stroke="black"
			stroke-width={axWidth}
			marker-start="url(#arrow)"
			marker-end="url(#arrow)"
		/>
		<BrokenFittedText
			x={0}
			y={-axEnds - 0.15}
			text={axEndLabels.yPlus}
			width={axEnds}
			height={0.4}
			anchor={'center'}
		/>
		<BrokenFittedText
			x={0}
			y={axEnds + 0.15 + 0.225}
			text={axEndLabels.yMinus}
			width={axEnds}
			height={0.35}
			anchor={'center'}
		/>
		<BrokenFittedText
			x={-axEnds + axWidth * 2}
			y={0.3}
			text={axEndLabels.xMinus}
			width={axEnds / 1.2}
			height={0.7}
			anchor={'left'}
		/>
		<BrokenFittedText
			x={axEnds - axWidth * 2}
			y={0.3}
			text={axEndLabels.xPlus}
			width={axEnds / 2}
			height={0.7}
			anchor={'right'}
		/>

		{#if showComparisons}
			{#each data.view.comparisons as comp}
				<circle
					cx={comp.sfCoords[0]}
					cy={-comp.sfCoords[1]}
					r="0.08"
					fill="var(--color-theme-darkblue)"
					role="none"
					on:mouseover={() => {
						hoveredName = comp.name;
					}}
					on:focus={() => {
						hoveredName = comp.name;
					}}
				/>
				<rect
					x={comp.sfCoords[0] - axEnds / 4}
					y={-comp.sfCoords[1] - axEnds / 20}
					height={axEnds / 20}
					width={axEnds / 2}
					fill="white"
					opacity="0.5"
				/>
				<g opacity="0.9">
					<BrokenFittedText
						x={comp.sfCoords[0]}
						y={-comp.sfCoords[1]}
						height={axEnds / 20}
						width={axEnds / 2}
						anchor={'center'}
						text={comp.name}
						allowRotation={false}
					/>
				</g>
			{/each}
		{/if}
		<circle
			cx={data.view.sfCoords[0]}
			cy={-data.view.sfCoords[1]}
			r="0.12"
			fill="var(--color-theme-red)"
			stroke-width={0.03}
			stroke="var(--color-theme-darkblue)"
		/>
	</svg>
</div>
