<script lang="ts">
	export let show: boolean;
	export let style: string;
</script>

{#if show}
	<div class="hoverover padded shadowy" id="spec-hover" {style}>
		<slot />
	</div>
{/if}

<style>
	div {
		position: absolute;
	}
</style>
