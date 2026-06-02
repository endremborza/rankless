<script lang="ts">
	export let color = 'white';
	export let width = 12.5;
	export let opacity = 0.8;
	export let paths: string[] = [];
</script>

{#each paths as d, __i (__i)}
	<path {d} fill="none" style="stroke: {color}" stroke-opacity={opacity} stroke-width={width} />
{/each}
