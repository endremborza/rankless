<script lang="ts">
	import { formatNumber } from '$lib/text-format-util';
	import { entToLink } from '$lib/tree-functions';
	export let data;
</script>

<div class="container padded">
	{#if data.user}
		<h1>Welcome, {data.user.name}!</h1>
		<p>Your ORCID iD: {data.user.orcid}</p>

		{#if data.searchResult}
			<span>
				Your profile:
				<h3>
					<a href={entToLink(data.searchResult)}>{data.searchResult.name}</a>
				</h3>
				<span
					>{formatNumber(data.searchResult.papers, 0)} papers,
					{formatNumber(data.searchResult.citations, 0)} citations</span
				>
			</span>
		{:else}
			You seem to have no Rankless profile
		{/if}
		<hr />
		<a href="/logout">Logout</a>
	{:else}
		<h1>Not logged in</h1>
		<a href="/login">Login with ORCID</a>
	{/if}
</div>

<style>
	.container {
		max-width: 800px;
		margin: 0 auto;
		padding-top: 110px;
	}
</style>
