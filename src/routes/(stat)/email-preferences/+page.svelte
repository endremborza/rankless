<script lang="ts">
	import EmailPreferences from '$lib/components/EmailPreferences.svelte';
</script>

<svelte:head>
	<title>Email preferences — Rankless</title>
	<meta name="robots" content="noindex" />
</svelte:head>

<section>
	<h1>Email preferences</h1>
	<EmailPreferences />
</section>

<style>
	section {
		max-width: 640px;
		margin: 0 auto;
		padding: 56px var(--unified-margin, 16px);
	}

	h1 {
		font-size: 2.2rem;
		margin: 0 0 12px 0;
		letter-spacing: -0.01em;
	}
</style>
