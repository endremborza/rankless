<script lang="ts">
	import { cutToFit, getStylesForWords } from '$lib/text-format-util';
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
	// Below this scale of the base font the text is left out rather than drawn unreadably small,
	// or, with `truncate`, shortened with an ellipsis until it fits at this scale; it grows to fill
	// its box up to `maxScale`.
	export let minScale = 0;
	export let maxScale = Infinity;
	export let truncate = false;

	const baseFontSize = 10;

	$: allWords = (text || '').split(' ');
	$: layout = (ws: string[]) => {
		const styles = getStylesForWords(
			ws,
			width,
			height,
			heightMultiplier,
			widthMultiplier,
			baseFontSize,
			anchor,
			bottomAligned,
			allowRotation,
			maxScale * baseFontSize
		);
		return styles.scale >= minScale ? styles : null;
	};
	$: fitted = truncate ? cutToFit(allWords, layout) : { words: allWords, layout: layout(allWords) };
	$: styles = fitted?.layout;
	$: matrix =
		styles &&
		(styles.rotate
			? `0,${-styles.scale},${styles.scale},0,${x + width}`
			: `${styles.scale},0,0,${styles.scale},${x}`);
	$: gstyle = matrix ? `transform:  matrix(${matrix}, ${y})` : '';
</script>

<g style="{gstyle}; transition: all {transMs}ms" transition:fade={{ duration: fadeMs }}>
	{#if fitted && styles}
		{#each fitted.words as word, wordInd (wordInd)}
			<text
				style=" transform: {styles.translates[wordInd]}; transition: all {transMs}ms"
				text-anchor="left">{word}</text
			>
		{/each}
	{/if}
</g>

<style>
	text {
		font-family: var(--font-mono);
		font-size: 10px;
	}
</style>
