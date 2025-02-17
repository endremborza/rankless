<script lang="ts">
	export let show: boolean;
	export let style: string;
</script>

{#if show}
	<div class="hoverover" id="spec-hover" {style}>
		<slot />
	</div>
{/if}

<style>
	div {
		padding: 12px;
		font-size: 0.9rem;
		position: absolute;
	}
</style>
