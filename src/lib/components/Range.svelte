<script lang="ts">
	export let value = 4;
	export let min = 1;
	export let max = 10;

	export let width = 20;
	export let height = 1.5;

	$: r = (height / 2) * 0.9;
	$: cx = ((value - min) / max) * width;

	$: valueSteps = [...Array(max - min).keys()].map((e) => e + min);
	$: posSteps = [...Array(max - min).keys()].map((e) => (e / (max - min)) * width);

	let moveHandler = (e: MouseEvent) => {};

	function trueMover(e: MouseEvent) {
		console.log(e);
		let ind = Math.floor((e.layerX / width) * (valueSteps.length - 1));
		cx = posSteps[ind];
		value = valueSteps[ind];
	}

	function dragOn(e: MouseEvent) {
		moveHandler = trueMover;
	}

	function dragOff(e: MouseEvent) {
		moveHandler = (e: MouseEvent) => {};
	}
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<g
	on:mousedown={dragOn}
	on:mouseup={dragOff}
	on:mousemove={moveHandler}
	on:mouseleave={dragOff}
	style="--x-off: 0px; --y-off: 0px"
>
	<rect {height} rx={height / 2} {width} />

	<circle {cx} {r} cy={height / 2} />
	<text font-size="{height * 0.6}px" y={0.72 * height} text-anchor="middle" x={cx}>{value}</text>
</g>

<style>
	circle {
		fill: var(--color-theme-lightblue);
		stroke: var(--color-theme-pink);
		stroke-width: 0.1px;
	}

	rect {
		fill: var(--color-theme-blue);
		border-radius: 50%;
	}

	text {
		cursor: default;
		-webkit-user-select: none;
		-moz-user-select: none;
		-ms-user-select: none;
		user-select: none;
	}
</style>
