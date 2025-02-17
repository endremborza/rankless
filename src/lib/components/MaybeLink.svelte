<script lang="ts">
	import { entToLink } from '$lib/tree-functions';
	import type { RootType } from '$lib/tree-types';

	export let semanticId: string;
	export let name: string;
	export let rootType: RootType;
</script>

{#if semanticId.length > 0}
	<a href={entToLink({ semanticId, rootType })}>{name}</a>
{:else}
	{name}
{/if}
