<script lang="ts">
	import InfoTip from '$lib/components/InfoTip.svelte';
	import type { WorkScreen } from '$lib/tree-types';
	import { listPhrase, pluralize } from '$lib/text-format-util';

	// The screen the pipeline actually ran, from `/methodology` via the (stat) layout load. The
	// kinds are rendered from it rather than named here, so this copy cannot fall behind the
	// data. With no screen to read the word stands on its own, unlinked.
	export let screen: WorkScreen | null;
</script>

{#if screen}
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
