<script lang="ts">
	import { getStylesForWords } from '$lib/text-format-util';
	import { fade } from 'svelte/transition';

	export let text: string;
	export let width: number;
	export let height: number;
	export let anchor: string = 'left';
	export let x = 0;
	export let y = 0;
	export let fadeMs = 600;
	const baseFontSize = 10;

	$: words = (text || '').split(' ');
	$: styles = getStylesForWords(words, width, height, 1.2, 0.6, baseFontSize, anchor == 'left');
	$: rotMatrix = `0,${-styles.scale},${styles.scale},0,${x + width}`;
	$: simpleMatrix = `${styles.scale},0,0,${styles.scale},${x}`;
	$: gstyle = `transform:  matrix(${styles.rotate ? rotMatrix : simpleMatrix}, ${y})`;
</script>

<g style={gstyle} transition:fade={{ duration: fadeMs }}>
	{#each words as word, wordInd}
		<text style=" transform: {styles.translates[wordInd]}" text-anchor="left">{word}</text>
	{/each}
</g>

<style>
	text {
		transition: transform 1s;
		font-family: monospace;
		font-size: 10px;
	}
</style>
