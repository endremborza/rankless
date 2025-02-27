<script lang="ts">
	import { base } from '$app/paths';
	import TextedLogo from '$lib/components/TextedLogo.svelte';
	import { APP_NAME, LATEST_YEAR } from '$lib/constants';
</script>

<svelte:head>
	<meta
		name="description"
		content="Explore academic impact beyond rankings. Rankless offers a fresh perspective on how universities influence each geography and topic, emphasizing diverse forms of impact and providing a richer understanding of academic influence."
	/>
	<title>{APP_NAME}</title>
</svelte:head>

<slot />
