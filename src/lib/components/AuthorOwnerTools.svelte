<script lang="ts">
	import type { AuthorMergeRequest } from '$lib/tree-types';

	export let semanticId: string;
	export let claimedDois: string[] = [];
	export let authorMergeRequests: AuthorMergeRequest[] = [];

	let localClaimedDois = [...claimedDois];
	let localMergeRequests = [...authorMergeRequests];

	let claimDoi = '';
	let claimStatus = '';
	let otherProfileInput = '';
	let mergeRequestNote = '';
	let mergeRequestStatus = '';

	function parseSemanticId(input: string): string {
		const trimmed = input.trim();
		const match = trimmed.match(/\/authors\/(.+?)(?:\?|$)/);
		if (match) return match[1];
		return trimmed.replace(/^\/+/, '');
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
			localClaimedDois = [...localClaimedDois, doi];
			claimDoi = '';
			claimStatus = 'Claimed';
		} else {
			claimStatus = 'Failed';
		}
	}

	async function handleUnClaim(doi: string) {
		localClaimedDois = localClaimedDois.filter((d) => d !== doi);
		await fetch('/api/papers/claim', {
			method: 'DELETE',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ doi })
		});
	}

	async function handleAuthorMergeRequest() {
		const otherSemanticId = parseSemanticId(otherProfileInput);
		if (!otherSemanticId || otherSemanticId === semanticId) return;
		mergeRequestStatus = 'Submitting...';
		const resp = await fetch('/api/authors/merge-request', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				my_semantic_id: semanticId,
				other_semantic_id: otherSemanticId,
				note: mergeRequestNote.trim() || null
			})
		});
		if (resp.ok) {
			localMergeRequests = [
				...localMergeRequests,
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
		localMergeRequests = localMergeRequests.filter((r) => r.other_semantic_id !== otherSemanticId);
		await fetch('/api/authors/merge-request', {
			method: 'DELETE',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ other_semantic_id: otherSemanticId })
		});
	}
</script>

<div class="owner-tools">
	<div class="tool-section">
		<h3>Claim a Paper</h3>
		<div class="claim-form">
			<input type="text" bind:value={claimDoi} placeholder="Enter DOI" class="text-input" />
			<button class="btn-sm confirm" on:click={handleClaim}>Claim</button>
		</div>
		{#if claimStatus}
			<span class="op-status">{claimStatus}</span>
		{/if}
		{#if localClaimedDois.length > 0}
			<div class="item-list">
				<h4>Claimed (pending validation)</h4>
				{#each localClaimedDois as doi}
					<div class="item-row">
						<a href="https://doi.org/{doi}" target="_blank" rel="noopener">{doi}</a>
						<button class="btn-sm" on:click={() => handleUnClaim(doi)}>Remove</button>
					</div>
				{/each}
			</div>
		{/if}
	</div>

	<div class="tool-section">
		<h3>Report Duplicate Profile</h3>
		<p class="hint-text">
			If another author profile represents the same person, submit a merge request. A human will
			review it before any changes are applied.
		</p>
		<div class="merge-form">
			<input
				type="text"
				bind:value={otherProfileInput}
				placeholder="Profile URL or semantic ID"
				class="text-input"
			/>
			<textarea
				bind:value={mergeRequestNote}
				placeholder="Optional note (e.g. institution, ORCID, DOI of shared paper)"
				class="text-input note-input"
				rows="2"
			/>
			<div class="form-row">
				<button class="btn-sm confirm" on:click={handleAuthorMergeRequest}>Submit Request</button>
				{#if mergeRequestStatus}
					<span class="op-status">{mergeRequestStatus}</span>
				{/if}
			</div>
		</div>
		{#if localMergeRequests.length > 0}
			<div class="item-list">
				<h4>Pending Review</h4>
				{#each localMergeRequests as req}
					<div class="item-row">
						<a href="/authors/{req.other_semantic_id}" target="_blank" rel="noopener"
							>{req.other_semantic_id}</a
						>
						{#if req.note}<span class="hint-text">{req.note}</span>{/if}
						<button class="btn-sm" on:click={() => handleCancelMergeRequest(req.other_semantic_id)}
							>Cancel</button
						>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>

<style>
	.owner-tools {
		margin-bottom: 20px;
		padding: 14px 16px;
		border-radius: 4px;
		border: 1px solid rgba(var(--color-range-15), 0.18);
		background: rgba(var(--color-range-15), 0.04);
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.tool-section h3 {
		font-size: var(--text-base);
		margin: 0 0 6px 0;
		text-align: left;
	}

	.claim-form,
	.merge-form {
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

	.text-input {
		font-size: var(--text-sm);
		padding: 4px 8px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: transparent;
		color: var(--color-text);
		font-family: inherit;
		max-width: 400px;
		flex: 1;
	}

	.note-input {
		resize: vertical;
		flex: unset;
	}

	.op-status {
		font-size: var(--text-xs);
		opacity: 0.5;
		margin-left: 8px;
	}

	.item-list {
		margin-top: 8px;
	}

	.item-list h4 {
		font-size: var(--text-sm);
		opacity: 0.5;
		margin: 0 0 4px 0;
	}

	.item-row {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: var(--text-sm);
		padding: 2px 0;
	}
</style>
