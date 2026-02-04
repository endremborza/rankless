<script lang="ts">
	export let show: boolean;
	export let style: string;
</script>

{#if show}
	<div class="hoverover padded shadowy transparent" {style}>
		<slot />
	</div>
{/if}
