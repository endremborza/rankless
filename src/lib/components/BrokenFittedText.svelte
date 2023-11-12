<script lang="ts">
	import { formatTextToLines } from '$lib/text-format-util';

	export let text: string;
	export let width: number;
	export let height: number;
	export let anchor: string = 'left';

	$: brokenText = formatTextToLines(text || '', width, height);

	function getStyle(
		brokenText: { rotate: boolean; lines: string[]; fontSize: number },
		ind: number
	) {
		let extStyle;
		if (brokenText.rotate) {
			extStyle = `--x: ${
				(ind - brokenText.lines.length + 1) * brokenText.fontSize * 1.2 + width
			}px; --y: 0px; --rot: -90deg; --rcx: ${(ind + 1) * brokenText.fontSize * 1.2}px; --rcy: 0px`;
		} else {
			extStyle = `--x: 0px; --y: ${
				(ind - brokenText.lines.length + 1) * brokenText.fontSize * 1.2
			}px; --rot: 0deg; --rcx: 0px; --rcy: 0px`;
		}
		return `font-size: ${brokenText.fontSize}px; ` + extStyle;
	}
</script>

{#each brokenText.lines as text, textInd}
	<text style="{getStyle(brokenText, textInd)};" text-anchor={anchor}>{text}</text>
{/each}

<style>
	text {
		transition: font-size 1s, transform 1s;
		transform: translate(var(--x), var(--y)) rotate(var(--rot));
		/* transform-origin: var(--rcx) var(--rcy); */
		transform-origin: top left;
	}
</style>
