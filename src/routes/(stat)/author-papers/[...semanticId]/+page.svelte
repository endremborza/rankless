<script lang="ts">
	import { page } from '$app/stores';
	import { APP_NAME } from '$lib/constants';
	import type { PaperProfileResp } from '$lib/tree-types';
	import { buildPaperMap, isAuthored } from '$lib/utils/paper-helpers';
	import type { AuthorPeersResp, AuthorMergeRequest } from '$lib/tree-types';
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
		mergedPairs: [number, number][];
		authorMergeRequests: AuthorMergeRequest[];
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
	$: mergedPairsState = [...data.mergedPairs];

	let claimDoi = '';
	let claimStatus = '';

	let otherProfileInput = '';
	let mergeRequestNote = '';
	let mergeRequestStatus = '';
	let authorMergeRequests = data.authorMergeRequests;

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

	async function handleMerge(e: CustomEvent<{ keep: number; drop: number }>) {
		const { keep, drop } = e.detail;
		mergedPairsState = [...mergedPairsState, [keep, drop]];
		await fetch('/api/papers/merge', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ wid_keep: keep, wid_drop: drop })
		});
	}

	async function handleUnmerge(e: CustomEvent<{ keep: number; drop: number }>) {
		const { keep, drop } = e.detail;
		mergedPairsState = mergedPairsState.filter(([k, d]) => !(k === keep && d === drop));
		await fetch('/api/papers/merge', {
			method: 'DELETE',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ wid_keep: keep, wid_drop: drop })
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

	function parseSemanticId(input: string): string {
		const trimmed = input.trim();
		const match = trimmed.match(/\/authors\/(.+?)(?:\?|$)/);
		if (match) return match[1];
		const authorPapersMatch = trimmed.match(/\/author-papers\/(.+?)(?:\?|$)/);
		if (authorPapersMatch) return authorPapersMatch[1];
		return trimmed.replace(/^\/+/, '');
	}

	async function handleAuthorMergeRequest() {
		const otherSemanticId = parseSemanticId(otherProfileInput);
		if (!otherSemanticId || otherSemanticId === data.semanticId) return;
		mergeRequestStatus = 'Submitting...';
		const resp = await fetch('/api/authors/merge-request', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				my_semantic_id: data.semanticId,
				other_semantic_id: otherSemanticId,
				note: mergeRequestNote.trim() || null
			})
		});
		if (resp.ok) {
			authorMergeRequests = [
				...authorMergeRequests,
				{
					other_semantic_id: otherSemanticId,
					note: mergeRequestNote.trim() || null,
					created_at: new Date().toISOString()
				}
			];
			otherProfileInput = '';
			mergeRequestNote = '';
			mergeRequestStatus = 'Submitted for review';
		} else {
			mergeRequestStatus = 'Failed';
		}
	}

	async function handleCancelMergeRequest(otherSemanticId: string) {
		authorMergeRequests = authorMergeRequests.filter(
			(r) => r.other_semantic_id !== otherSemanticId
		);
		await fetch('/api/authors/merge-request', {
			method: 'DELETE',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ other_semantic_id: otherSemanticId })
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
	</div>
	<AllWorks
		semanticId={data.semanticId}
		{entityAtts}
		{discAuthorNames}
		disownedWids={disownedSet}
		mergedPairs={mergedPairsState}
		isOwner={data.isOwner}
		on:disown={handleDisown}
		on:undisown={handleUndisown}
		on:merge={handleMerge}
		on:unmerge={handleUnmerge}
	/>

	{#if data.isOwner}
		<div class="owner-tools">
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

			<div class="author-merge-section">
				<h3>Report Duplicate Profile</h3>
				<p class="section-hint">
					If another author profile represents the same person, submit a merge request. A human will
					review it before any changes are applied.
				</p>
				<div class="merge-request-form">
					<input
						type="text"
						bind:value={otherProfileInput}
						placeholder="Profile URL or semantic ID"
						class="doi-input"
					/>
					<textarea
						bind:value={mergeRequestNote}
						placeholder="Optional note (e.g. institution, ORCID, DOI of shared paper)"
						class="note-input"
						rows="2"
					/>
					<div class="form-row">
						<button on:click={handleAuthorMergeRequest}>Submit Request</button>
						{#if mergeRequestStatus}
							<span class="claim-status">{mergeRequestStatus}</span>
						{/if}
					</div>
				</div>
				{#if authorMergeRequests.length > 0}
					<div class="pending-requests">
						<h4>Pending Review</h4>
						{#each authorMergeRequests as req}
							<div class="claimed-row">
								<a href="/authors/{req.other_semantic_id}" target="_blank" rel="noopener"
									>{req.other_semantic_id}</a
								>
								{#if req.note}<span class="req-note">{req.note}</span>{/if}
								<button
									class="undo-btn"
									on:click={() => handleCancelMergeRequest(req.other_semantic_id)}>Cancel</button
								>
							</div>
						{/each}
					</div>
				{/if}
			</div>
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

	.owner-tools {
		margin-top: 16px;
		padding-top: 12px;
		border-top: 1px solid rgba(var(--color-range-15), 0.1);
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.claim-section h3,
	.author-merge-section h3 {
		font-size: 0.9rem;
		margin: 0 0 6px 0;
	}

	.section-hint {
		font-size: 0.7rem;
		opacity: 0.5;
		margin: 0 0 8px 0;
	}

	.claim-form,
	.merge-request-form {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.claim-form {
		flex-direction: row;
		align-items: center;
	}

	.form-row {
		display: flex;
		align-items: center;
		gap: 8px;
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

	.note-input {
		max-width: 400px;
		font-size: 0.75rem;
		padding: 4px 8px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: transparent;
		color: var(--color-text);
		resize: vertical;
		font-family: inherit;
	}

	.claim-form button,
	.merge-request-form button {
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

	.claimed-list,
	.pending-requests {
		margin-top: 8px;
	}

	.claimed-list h4,
	.pending-requests h4 {
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

	.req-note {
		font-size: 0.7rem;
		opacity: 0.5;
		font-style: italic;
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
