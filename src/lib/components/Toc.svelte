<script lang="ts">
	import { onMount } from 'svelte';

	export let sections: { id: string; label: string }[];

	let activeId = sections[0]?.id ?? '';

	onMount(() => {
		const obs = new IntersectionObserver(
			(entries) => {
				for (const entry of entries) {
					if (entry.isIntersecting) {
						activeId = entry.target.id;
						break;
					}
				}
			},
			{ threshold: 0.05, rootMargin: '-60px 0px -55% 0px' }
		);
		for (const sec of sections) {
			const el = document.getElementById(sec.id);
			if (el) obs.observe(el);
		}
		return () => obs.disconnect();
	});
</script>

<nav class="toc" aria-label="Page sections">
	{#each sections as sec}
		<a href="#{sec.id}" class:active={activeId === sec.id}>{sec.label}</a>
	{/each}
</nav>

<style>
	.toc {
		position: sticky;
		top: var(--header-height);
		z-index: 15;
		display: flex;
		flex-wrap: wrap;
		gap: 4px;
		padding: var(--control-bar-pad-v) var(--control-bar-pad-h);
		background: var(--text-bg);
		font-size: var(--control-bar-font);
	}

	a {
		padding: var(--control-bar-pill-pad);
		border-radius: var(--control-bar-pill-radius);
		text-decoration: none;
		opacity: 0.45;
		transition: opacity 0.15s, background 0.15s;
		color: var(--color-text);
		white-space: nowrap;
	}

	a:hover {
		opacity: 0.8;
	}

	a.active {
		opacity: 1;
		background: rgba(var(--color-range-15), 0.1);
	}
</style>
