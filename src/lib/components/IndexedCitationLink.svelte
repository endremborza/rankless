<script lang="ts">
	import HoverBlock from '$lib/components/HoverBlock.svelte';

	let show = false;
</script>

<HoverBlock
	{show}
	style="position: fixed; top: 20svh; left: 20vw; width: 60vw; max-width: 550px; z-index: 40;"
>
	Citations made by non-retracted papers categorized as "article", "book", or "review" that have
	received at least one citation.
</HoverBlock><a
	href="/#indexed-citation"
	target="blank_"
	on:mouseover={() => (show = true)}
	on:mouseleave={() => (show = false)}
	on:focus={() => (show = true)}
	on:blur={() => (show = false)}>indexed</a
>
