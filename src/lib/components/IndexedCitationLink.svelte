<script lang="ts">
	import InfoTip from '$lib/components/InfoTip.svelte';
	import { workScreenPhrase } from '$lib/text-format-util';
	import { METHODOLOGY } from '$lib/wire/rankless_server/responses';
</script>

<!-- The kinds and limits are read from the methodology rather than named here, so this copy cannot
	fall behind the data. -->

<InfoTip kind="inline" label="What counts as an indexed citation">
	indexed
	<span slot="text"
		>Citations made by papers that are in the data at all: {workScreenPhrase(
			METHODOLOGY.workScreen
		)}.</span
	>
</InfoTip>
