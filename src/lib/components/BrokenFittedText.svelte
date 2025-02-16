<script lang="ts">
	import { getStylesForWords } from '$lib/text-format-util';
	import { fade } from 'svelte/transition';

	export let text: string;
	export let width: number;
	export let height: number;
	export let anchor: 'left' | 'center' | 'right' = 'left';
	export let bottomAligned: boolean = true;
	export let x = 0;
	export let y = 0;
	export let allowRotation = true;
	export let fadeMs = 600;
	export let transMs = 800;
	//default for monospace
	export let heightMultiplier: number = 1.2;
	export let widthMultiplier: number = 0.6;

	const baseFontSize = 10;

	$: words = (text || '').split(' ');
	$: styles = getStylesForWords(
		words,
		width,
		height,
		heightMultiplier,
		widthMultiplier,
		baseFontSize,
		anchor,
		bottomAligned,
		allowRotation
	);
	$: rotMatrix = `0,${-styles.scale},${styles.scale},0,${x + width}`;
	$: simpleMatrix = `${styles.scale},0,0,${styles.scale},${x}`;
	$: gstyle = `transform:  matrix(${styles.rotate ? rotMatrix : simpleMatrix}, ${y})`;
</script>

<g style="{gstyle}; transition: all {transMs}ms" transition:fade={{ duration: fadeMs }}>
	{#each words as word, wordInd}
		<text
			style=" transform: {styles.translates[wordInd]}; transition: all {transMs}ms"
			text-anchor="left">{word}</text
		>
	{/each}
</g>

<style>
	text {
		font-family: var(--font-mono);
		font-size: 10px;
	}
</style>
