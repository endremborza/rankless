<script lang="ts">
	import { page } from '$app/stores';
	import { APP_NAME } from '$lib/constants';
	import type { PaperProfileResp } from '$lib/tree-types';
	import { buildPaperMap, isAuthored } from '$lib/utils/paper-helpers';
	import type { AuthorPeersResp } from '$lib/tree-types';
	import PaperRainbow from '$lib/components/PaperRainbow.svelte';
	import ImpactDag from '$lib/components/ImpactDag.svelte';
	import AllWorks from '$lib/components/AllWorks.svelte';
	import AuthorPeers from '$lib/components/AuthorPeers.svelte';

	export let data: {
		name: string;
		profile: PaperProfileResp | null;
		peersData: AuthorPeersResp | null;
		semanticId: string;
		paperText: string;
		citeText: string;
		isOwner: boolean;
		hasOrcid: boolean;
		disownedWids: number[];
		claimedDois: string[];
	};

	$: user = $page.data.user;
	$: papers = data.profile?.papers.papers ?? [];
	$: entityAtts = data.profile?.papers.entityAtts ?? {};
	$: discAuthorNames = data.profile?.papers.discAuthorNames ?? {};
	$: authorsMeta = data.profile?.papers.authorsMeta ?? {};
	$: authoredHitPapers = papers.filter(
		(p) => isAuthored(p, data.semanticId, entityAtts) && p.yearlyCites && p.yearlyCites.length > 0
	);
	$: paperMap = data.profile ? buildPaperMap(papers) : {};

	$: dagEmpty =
		!data.profile ||
		data.profile.dag === 'Leaf' ||
		Object.keys((data.profile.dag as { Node: object }).Node ?? {}).length === 0;

	$: disownedSet = new Set(data.disownedWids);

	let claimDoi = '';
	let claimStatus = '';

	async function handleDisown(e: CustomEvent<number>) {
		const wid = e.detail;
		disownedSet.add(wid);
		disownedSet = disownedSet;
		await fetch('/api/papers/disown', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ wid })
		});
	}

	async function handleUndisown(e: CustomEvent<number>) {
		const wid = e.detail;
		disownedSet.delete(wid);
		disownedSet = disownedSet;
		await fetch('/api/papers/disown', {
			method: 'DELETE',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ wid })
		});
	}

	async function handleClaim() {
		const doi = claimDoi.trim();
		if (!doi) return;
		claimStatus = 'Submitting...';
		const resp = await fetch('/api/papers/claim', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ doi })
		});
		if (resp.ok) {
			data.claimedDois = [...data.claimedDois, doi];
			claimDoi = '';
			claimStatus = 'Claimed';
		} else {
			claimStatus = 'Failed';
		}
	}

	async function handleUnClaim(doi: string) {
		data.claimedDois = data.claimedDois.filter((d) => d !== doi);
		await fetch('/api/papers/claim', {
			method: 'DELETE',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ doi })
		});
	}
</script>

<svelte:head>
	<title>{APP_NAME} | {data.name} – Paper Profile</title>
	<meta
		name="description"
		content="Paper profile for {data.name} – {data.paperText}, {data.citeText}"
	/>
</svelte:head>

<div id="head" class="shadowy padded marged">
	<a href="/authors/{data.semanticId}" class="back-link">&larr; Back to full profile</a>
	<h1>{data.name}</h1>
	<p class="stats">{data.paperText} &middot; {data.citeText}</p>
</div>

{#if authoredHitPapers.length > 0}
	<div class="shadowy padded marged">
		<h2>Standout Papers</h2>
		<PaperRainbow papers={authoredHitPapers} {entityAtts} {discAuthorNames} />
	</div>
{/if}

<div class="shadowy padded marged">
	<h2>Immediate Impact</h2>
	{#if dagEmpty}
		<p class="status">No citation impact paths found for this author.</p>
	{:else if data.profile}
		<ImpactDag
			dag={data.profile.dag}
			{paperMap}
			{entityAtts}
			{discAuthorNames}
			{authorsMeta}
			sourceAuthorSemId={data.semanticId}
			authorName={data.name}
		/>
	{/if}
</div>

{#if data.peersData && data.peersData.peers.length > 0}
	<div class="shadowy padded marged">
		<h2>Author Peers</h2>
		<AuthorPeers data={data.peersData} />
	</div>
{/if}

<div class="shadowy padded marged">
	<div class="works-header">
		<h2>All Works</h2>
		{#if data.isOwner}
			<a href="/logout" class="auth-link" data-sveltekit-preload-data="off">Logout</a>
		{:else if data.hasOrcid && !user}
			<div class="login-prompt">
				<a
					href="/login?returnTo=/author-papers/{data.semanticId}"
					class="auth-link"
					data-sveltekit-preload-data="off">Login with ORCID</a
				>
				<span class="login-hint">to disown or claim papers</span>
			</div>
		{/if}
	</div>
	<AllWorks
		semanticId={data.semanticId}
		{entityAtts}
		{discAuthorNames}
		disownedWids={disownedSet}
		isOwner={data.isOwner}
		on:disown={handleDisown}
		on:undisown={handleUndisown}
	/>

	{#if data.isOwner}
		<div class="claim-section">
			<h3>Claim a Paper</h3>
			<div class="claim-form">
				<input type="text" bind:value={claimDoi} placeholder="Enter DOI" class="doi-input" />
				<button on:click={handleClaim}>Claim</button>
			</div>
			{#if claimStatus}
				<span class="claim-status">{claimStatus}</span>
			{/if}
			{#if data.claimedDois.length > 0}
				<div class="claimed-list">
					<h4>Claimed (pending validation)</h4>
					{#each data.claimedDois as doi}
						<div class="claimed-row">
							<a href="https://doi.org/{doi}" target="_blank" rel="noopener">{doi}</a>
							<button class="undo-btn" on:click={() => handleUnClaim(doi)}>Remove</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.back-link {
		font-size: 0.8rem;
		opacity: 0.6;
		transition: opacity 0.15s;
	}

	.back-link:hover {
		opacity: 1;
	}

	.works-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
		gap: 4px;
	}

	.login-prompt {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.login-hint {
		font-size: 0.7rem;
		opacity: 0.4;
	}

	.auth-link {
		font-size: 0.75rem;
		opacity: 0.5;
	}

	.auth-link:hover {
		opacity: 1;
	}

	h1 {
		margin-top: 4px;
		margin-bottom: 4px;
	}

	.stats {
		opacity: 0.6;
		margin: 0;
	}

	h2 {
		margin-bottom: 8px;
		text-align: center;
	}

	.status {
		opacity: 0.6;
		font-style: italic;
	}

	.claim-section {
		margin-top: 16px;
		padding-top: 12px;
		border-top: 1px solid rgba(var(--color-range-15), 0.1);
	}

	.claim-section h3 {
		font-size: 0.9rem;
		margin: 0 0 8px 0;
	}

	.claim-form {
		display: flex;
		gap: 8px;
		align-items: center;
	}

	.doi-input {
		flex: 1;
		max-width: 400px;
		font-size: 0.8rem;
		padding: 4px 8px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: transparent;
		color: var(--color-text);
	}

	.claim-form button {
		font-size: 0.75rem;
		padding: 4px 12px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: none;
		cursor: pointer;
		color: var(--color-text);
	}

	.claim-status {
		font-size: 0.7rem;
		opacity: 0.5;
		margin-left: 8px;
	}

	.claimed-list {
		margin-top: 8px;
	}

	.claimed-list h4 {
		font-size: 0.8rem;
		opacity: 0.5;
		margin: 0 0 4px 0;
	}

	.claimed-row {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: 0.75rem;
		padding: 2px 0;
	}

	.undo-btn {
		font-size: 0.6rem;
		padding: 1px 6px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.15);
		background: none;
		cursor: pointer;
		color: var(--color-text);
		opacity: 0.5;
	}

	.undo-btn:hover {
		opacity: 1;
	}
</style>
