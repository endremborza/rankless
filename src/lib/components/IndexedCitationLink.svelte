<script lang="ts">
	import { page } from '$app/state';
	import InfoTip from '$lib/components/InfoTip.svelte';
	import { listPhrase, pluralize } from '$lib/text-format-util';
</script>

<!-- The kinds and limits are read from the methodology the backend serves rather than named here,
	so this copy cannot fall behind the data. With none to read the word stands on its own, unlinked. -->

{#if page.data.methodology}
	{@const screen = page.data.methodology.workScreen}
	<InfoTip kind="inline" label="What counts as an indexed citation">
		indexed
		<span slot="text"
			>Citations made by papers that are in the data at all: not retracted, categorized by OpenAlex
			as {listPhrase(screen.kinds)}, published after {screen.startYear}, cited at least {pluralize(
				'time',
				screen.minCitations
			)}, and written by no more than {pluralize('author', screen.maxAuthors)}.</span
		>
	</InfoTip>
{:else}
	indexed
{/if}
