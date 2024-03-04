<script lang="ts">
	import MaskedSankeyPath from '$lib/components/MaskedSankeyPath.svelte';
	import {linkVertical} from 'd3-shape';

	let child = 9;
	let parent = 4;
	let top = 3;
	let path = 8;
	let bot = 2;

	let xOffTop = 2;
	let xOffBot = 4;
	$: widths = {child, parent};
	$: heights = {top, path, bot};
	$: xOffsets = {top: xOffTop, bot: xOffBot};
	let yOffset = 2;
</script>

<svg viewBox="-10 -10 30 30" width="1800px" height="700px">
	<MaskedSankeyPath {widths} {heights} {xOffsets} {yOffset} />
</svg>

<br>
xOffTop: {xOffTop} <br><input type="range" bind:value={xOffTop} min="-3" max="3" step="0.01" />
<br>
xOffBot: {xOffBot} <br><input type="range" bind:value={xOffBot} min="-3" max="3" step="0.01" />
<br>
yOffset: {yOffset} <br><input type="range" bind:value={yOffset} min="-3" max="3" step="0.01" />
<br>
child: {child} <br><input type="range" bind:value={child} min="0" max="9" step="0.01" />
<br>
parent: {parent} <br><input type="range" bind:value={parent} min="0" max="9" step="0.01" />
<br>
top: {top} <br><input type="range" bind:value={top} min="0" max="9" step="0.01" />
<br>
path: {path} <br><input type="range" bind:value={path} min="0" max="9" step="0.01" />
<br>
bot: {bot} <br><input type="range" bind:value={bot} min="0" max="9" step="0.01" />

<style>
	svg {
		border: solid red;
	}
</style>
