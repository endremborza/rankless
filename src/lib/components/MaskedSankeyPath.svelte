<script lang="ts">
	import {linkVertical} from 'd3-shape';

	export let id = 'gen';
	export let widths = {child: 20, parent: 8};
	export let heights = {top: 8, path: 10, bot: 5};
	export let xOffsets = {top: 2, bot: 4};
	export let yOffset = 2;
	export let color = 'red';
	export let cssClass = '';

	/* 	const unitPath = linkVertical()
		// @ts-ignore
		.source((d) => d.start)
		// @ts-ignore
		.target((d) => d.end)({ start: [0, 1], end: [1, 0] });
	console.log(unitPath);
	   */
	const upPath = 'L0,1C0,0.5,1,0.5,1,0';
	const downPath = 'L0,0C0,0.5,1,0.5,1,1';
	// left-top of main path is 0,0
	// path height is 1
	// first everything scaled to that
	// then everything translated
	const leftEdge = -1;
	const rightEdge = 2;
	const topEdge = -50;
	const botEdge = 51;

	const leftUpwardMaskPath = `M ${leftEdge},${botEdge} H0 ${upPath} V${topEdge} H${leftEdge} z`;
	const rightUpwardMaskPath = `M ${rightEdge},${botEdge} H0 ${upPath} V${topEdge} H${rightEdge} z`;
	const leftDownwardMaskPath = `M ${leftEdge},${topEdge} H0 ${downPath} V${botEdge} H${leftEdge} z`;
	const rightDownwardMaskPath = `M ${rightEdge},${topEdge} H0 ${downPath} V${botEdge} H${rightEdge} z`;

	const cut = (x: number) => Math.max(0, x);
	const getScale = (pHeight: number, slope: number) => `scale(${cut(slope)}, ${pHeight})`;

	$: totalWidth = Math.max(...Object.values(xEnds)) - Math.min(...Object.values(xOffsets));
	$: totalHeight = Object.values(heights).reduce((x, y) => x + y);
	$: xEnds = {top: xOffsets.top + widths.parent, bot: xOffsets.bot + widths.child};
	$: lSlope = (xOffsets.top - xOffsets.bot) / totalWidth;
	$: rSlope = (xEnds.top - xEnds.bot) / totalWidth;

	$: leftUpwardT = getScale(heights.path, lSlope);
	$: leftDownwardT = getScale(heights.path, -lSlope);
	$: rightUpwardT = `translateX(${1 - rSlope}px) ` + getScale(heights.path, rSlope);
	$: rightDownwardT = `translateX(${1 + rSlope}px) ` + getScale(heights.path, -rSlope);
	$: rectMaskTransform = `translateY(${-heights.top}px) scaleY(${totalHeight})`;
	$: rectTransform = `translate(${Math.min(
		...Object.values(xOffsets)
	)}px, ${yOffset}px) scaleX(${totalWidth})`;
</script>

<mask {id}>
	<rect width={rightEdge - leftEdge} x={leftEdge} height="1" style="--t: {rectMaskTransform}" fill="white" />
	<path d={leftUpwardMaskPath} style="--t: {leftUpwardT}" fill="black" />
	<path d={leftDownwardMaskPath} style="--t: {leftDownwardT}" fill="black" />
	<path d={rightUpwardMaskPath} style="--t: {rightUpwardT}" fill="black" />
	<path d={rightDownwardMaskPath} style="--t: {rightDownwardT}" fill="black" />
</mask>
<rect class={cssClass} width={rightEdge - leftEdge - 2} x={leftEdge + 1} height={botEdge - topEdge - 2} y={topEdge + 1}
	fill={color} style="--t: {rectTransform}" mask={`url(#${id}`} />

<style>
	path,
	rect {
		transform: var(--t);
		transition-property: transform;
		transition-duration: 1s;
	}
</style>
