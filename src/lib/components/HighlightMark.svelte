<script lang="ts">
	import type { Mark } from '$lib/utils/impact-highlights';

	export let mark: Mark;
</script>

{#if mark.href}<a
		class="mark {mark.kind ?? ''}"
		class:on={!!mark.kind}
		href={mark.href}
		title={mark.title}>{mark.label}</a
	>{:else}<span class="mark {mark.kind ?? ''}" class:on={!!mark.kind} title={mark.title}
		>{mark.label}</span
	>{/if}

<style>
	.mark {
		color: inherit;
		text-decoration: none;
	}

	a.mark:hover {
		text-decoration: underline;
	}

	.on {
		display: inline-block;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		vertical-align: bottom;
		padding: 0 4px;
		border-radius: 3px;
		font-weight: 600;
	}

	.on.hit {
		background: var(--badge-hit-bg);
		color: var(--badge-hit-text);
	}

	.on.apex,
	.on.institution {
		background: var(--badge-prestigious-bg);
		color: var(--badge-prestigious-text);
	}

	.on.laureate,
	.on.star {
		background: var(--badge-award-bg);
		color: var(--badge-award-text);
	}
</style>
