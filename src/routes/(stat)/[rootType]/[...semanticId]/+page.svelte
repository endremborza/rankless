<script lang="ts">
	import { APP_NAME, REL_TYPES } from '$lib/constants';
	import { prettifyRoot, pluralize } from '$lib/text-format-util';

	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { isAuthored, fetchOaAbstract, stripHtml } from '$lib/utils/paper-helpers';
	import { onMount } from 'svelte';

	import FullQc from '$lib/components/FullQc.svelte';
	import YearTicks from '$lib/components/YearTicks.svelte';
	import RandTreeLink from '$lib/components/RandTreeLink.svelte';
	import HoverBlock from '$lib/components/HoverBlock.svelte';
	import WorldMapSvg from '$lib/components/WorldMapSvg.svelte';
	import ConceptMap from '$lib/components/ConceptMap.svelte';
	import AuthorNetwork from '$lib/components/AuthorNetwork.svelte';
	import Toc from '$lib/components/Toc.svelte';
	import PaperRainbow from '$lib/components/PaperRainbow.svelte';
	import EntityPeers from '$lib/components/EntityPeers.svelte';
	import AllWorks from '$lib/components/AllWorks.svelte';

	export let data: {
		view: tt.View;
		conf: tt.FullTreeConfig;
		selectionState: tt.BareNode;
		treeSpecs: tt.TreeSpecs;
		tree: tt.ResponseNode;
		atts: tt.AttributeLabels;
		svgLink: string;
		shallowed: boolean;
		aboutParagraph: tt.AboutPara;
		metaDescriptions: string;
		paperText: string;
		citeText: string;
		prefixText: string;
		profile: tt.PaperProfileResp | null;
		peersData: tt.EntityPeersResp | null;
		initialPapers: tt.Paper[];
		initialEntityAtts: tt.EntityAttsForLinks;
		initialDiscAuthorNames: Record<string, string>;
		initialTotalPapers: number;
		initialWorksSliceEnd: number;
		isOwner: boolean;
		disownedWids: number[];
		claimedDois: string[];
		mergedPairs: [number, number][];
		authorMergeRequests: tt.AuthorMergeRequest[];
	};

	let showIndexedCiteText = false;
	let ticksHeight: number;

	// Author-specific state
	let claimDoi = '';
	let claimStatus = '';
	let otherProfileInput = '';
	let mergeRequestNote = '';
	let mergeRequestStatus = '';
	let authorMergeRequests = data.authorMergeRequests;

	$: isAuthor = data.conf.rootType === 'authors';
	$: isHitPaper = data.conf.rootType === 'hit-papers';
	$: rawPapers = isAuthor ? parseInt(data.view.meta?.rawPapers ?? '0') || 0 : 0;

	let hitPaperAbstract: string | null = null;
	let abstractExpanded = false;
	onMount(async () => {
		if (isHitPaper) {
			hitPaperAbstract = await fetchOaAbstract(data.conf.semanticId);
		}
	});
	$: rawCites = isAuthor ? parseInt(data.view.meta?.rawCites ?? '0') || 0 : 0;

	// Combined entity attribute maps (profile data + initial works batch)
	let entityAtts: tt.EntityAttsForLinks = {
		...(data.profile?.papers.entityAtts ?? {}),
		...data.initialEntityAtts
	};
	let discAuthorNames: Record<string, string> = {
		...(data.profile?.papers.discAuthorNames ?? {}),
		...data.initialDiscAuthorNames
	};

	$: papers = data.profile?.papers.papers ?? [];
	$: authoredHitPapers = papers.filter(
		(p) =>
			isAuthored(p, data.conf.semanticId, entityAtts) && p.yearlyCites && p.yearlyCites.length > 0
	);

	$: disownedSet = new Set(data.disownedWids);
	$: mergedPairsState = [...data.mergedPairs];

	function getAuthorStats(view: tt.View) {
		let authorNames: string[] = [];
		let authorScores: number[] = [];
		for (const rel of view.primeRelations) {
			if (REL_TYPES[rel.relType] == 'paper-authors') {
				authorNames.push(rel.name);
				authorScores.push(rel.score);
			}
		}
		return { authorNames, authorScores, edgeWeights: view.authorNetwork };
	}

	$: indsByEntityType = tf.getTreeIndsByEntityType(data.treeSpecs.specs[data.conf.rootType]);
	$: showsCountry = indsByEntityType.countries.length > 0;
	$: showsSubfields = indsByEntityType.subfields.length > 0;
	$: authorStats = getAuthorStats(data.view);

	$: tocSections = [
		{ id: 'overview', label: 'Overview' },
		{ id: 'impact', label: 'Impact' },
		...(isAuthor && authoredHitPapers.length > 0
			? [{ id: 'papers', label: 'Standout Papers' }]
			: []),
		...(isAuthor && (data.peersData?.peers.length ?? 0) > 0
			? [{ id: 'peers', label: 'Peers' }]
			: []),
		...(showsCountry ? [{ id: 'geography', label: 'Geography' }] : []),
		...(showsSubfields ? [{ id: 'research-space', label: 'Research Space' }] : []),
		...(isAuthor ? [{ id: 'network', label: 'Co-Authors' }] : []),
		...(isAuthor ? [{ id: 'works', label: 'Works' }] : [])
	];

	async function handleDisown(e: CustomEvent<number>) {
		const wid = e.detail;
		disownedSet.add(wid);
		disownedSet = disownedSet;
		const resp = await fetch('/api/papers/disown', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ wid })
		});
		if (!resp.ok) {
			disownedSet.delete(wid);
			disownedSet = disownedSet;
		}
	}

	async function handleUndisown(e: CustomEvent<number>) {
		const wid = e.detail;
		disownedSet.delete(wid);
		disownedSet = disownedSet;
		const resp = await fetch('/api/papers/disown', {
			method: 'DELETE',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ wid })
		});
		if (!resp.ok) {
			disownedSet.add(wid);
			disownedSet = disownedSet;
		}
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
		const apMatch = trimmed.match(/\/author-papers\/(.+?)(?:\?|$)/);
		if (apMatch) return apMatch[1];
		return trimmed.replace(/^\/+/, '');
	}

	async function handleAuthorMergeRequest() {
		const otherSemanticId = parseSemanticId(otherProfileInput);
		if (!otherSemanticId || otherSemanticId === data.conf.semanticId) return;
		mergeRequestStatus = 'Submitting...';
		const resp = await fetch('/api/authors/merge-request', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				my_semantic_id: data.conf.semanticId,
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
	<title>{APP_NAME} | {stripHtml(data.view.name)}</title>
	<meta name="twitter:card" content="summary" />
	<meta name="twitter:creator" content="@LearningCCL" />
	<meta name="description" content={data.metaDescriptions} />
	<meta property="og:image" content={data.svgLink} />
	<meta property="og:title" content="{data.view.name} | {APP_NAME}" />
	<link rel="canonical" href={tf.externalEntityUrl(data.conf.rootType, data.conf.semanticId)} />
</svelte:head>

<section id="overview" class="shadowy padded marged main-block">
	<div id="name-block">
		<HoverBlock
			show={showIndexedCiteText}
			style={'top: 20svh; left:20vw; width: 60vw;max-width: 550px'}
		>
			Citations made by non-retracted papers categorized as "article", "book", or "review" that have
			received at least one citation.
		</HoverBlock>
		<!-- svelte-ignore a11y-mouse-events-have-key-events -->
		<div id="nametag">
			<h1>{@html data.view.name}</h1>
			{#if isHitPaper}
				<div>
					<span>{data.citeText}</span>
				</div>
			{:else if rawCites > 0}
				<div>
					<span>{pluralize('total citation', rawCites)}</span>
					{#if isAuthor && authoredHitPapers.length > 0}
						·
						<a href="#papers">{pluralize('hit paper', authoredHitPapers.length)}</a>
					{/if}
					<br />
					<span class="indexed-subtext"
						>{pluralize('paper', data.view.papers)}, {pluralize('citation', data.view.citations)}
						<a
							on:mouseover={() => {
								showIndexedCiteText = true;
							}}
							on:mouseleave={() => {
								showIndexedCiteText = false;
							}}
							href="/#indexed-citation"
							target="blank_">indexed</a
						></span
					>
				</div>
			{:else}
				<div>
					<span>{data.paperText}</span>
					and
					<span
						><a
							on:mouseover={() => {
								showIndexedCiteText = true;
							}}
							on:mouseleave={() => {
								showIndexedCiteText = false;
							}}
							href="/#indexed-citation"
							target="blank_">{data.citeText}</a
						></span
					>
				</div>
			{/if}
		</div>
		{#if isHitPaper}
			<details id="abstract" bind:open={abstractExpanded}>
				<summary><h2>Abstract</h2></summary>
				{#if hitPaperAbstract}
					<p class="abstract-text" class:abstract-truncated={!abstractExpanded}>
						{hitPaperAbstract}
					</p>
				{:else}
					<p class="abstract-loading">loading...</p>
				{/if}
			</details>
		{/if}
		<div id="about">
			<h2>About</h2>
			<div>
				{@html data.aboutParagraph.prefix}.
				{@html data.aboutParagraph.postText}
			</div>
		</div>
	</div>
	<div id="era">
		<h2>In The Last Decade</h2>
		<div bind:clientHeight={ticksHeight}>
			<YearTicks
				bottomStacks={data.view.yearlyPapers}
				topStacks={data.view.yearlyCites}
				fullHeight={ticksHeight}
				showBottom={!isHitPaper}
			/>
		</div>
		{#if isHitPaper}
			{@const doi = !data.conf.semanticId.startsWith('W') ? data.conf.semanticId : null}
			<a
				href={doi ? `https://doi.org/${doi}` : `https://openalex.org/${data.conf.semanticId}`}
				target="_blank"
				rel="noopener"
				class="dag-link">{doi ? `doi.org/${doi}` : 'OpenAlex'} →</a
			>
		{/if}
	</div>
</section>

<Toc sections={tocSections} />

<section id="impact" class="shadowy padded marged main-block">
	<FullQc
		rootName={data.view.name}
		prefixText={data.prefixText}
		selectedQcRootId={data.view.dmId}
		conf={data.conf}
		selectionState={data.selectionState}
		treeSpecs={data.treeSpecs}
		attributeLabels={data.atts}
		completeTree={data.tree}
		shallowed={data.shallowed}
		shoPathLevelInfo={!isHitPaper}
	/>
</section>

{#if isAuthor && authoredHitPapers.length > 0}
	<section id="papers" class="shadowy padded marged main-block">
		<h2>Hit Papers</h2>
		<PaperRainbow
			papers={authoredHitPapers}
			{entityAtts}
			{discAuthorNames}
			treeSpecs={data.treeSpecs}
		/>
	</section>
{/if}

{#if isAuthor && data.peersData && data.peersData.peers.length > 0}
	<section id="peers" class="shadowy padded marged main-block">
		<h2>Peers</h2>
		<EntityPeers data={data.peersData} />
	</section>
{/if}

{#if showsCountry}
	<section id="geography" class="shadowy padded marged main-block heighted">
		<WorldMapSvg
			rootId={data.view.dmId}
			{indsByEntityType}
			rootName={data.view.name}
			conf={data.conf}
			treeSpecs={data.treeSpecs}
		/>
	</section>
{/if}

{#if showsSubfields}
	<section id="research-space" class="shadowy padded marged main-block heighted">
		<ConceptMap
			rootId={data.view.dmId}
			{indsByEntityType}
			rootName={data.view.name}
			conf={data.conf}
			treeSpecs={data.treeSpecs}
		/>
	</section>
{/if}

{#if isAuthor}
	<section id="network" class="shadowy padded marged main-block heighted">
		<AuthorNetwork
			nodes={authorStats.authorNames}
			edgeWeights={authorStats.edgeWeights}
			nodeIntensities={authorStats.authorScores}
			rootName={data.view.name}
		/>
	</section>

	<section id="works" class="shadowy padded marged main-block">
		<h2>All Works</h2>

		{#if data.isOwner}
			<div class="owner-tools">
				<div class="claim-section">
					<h3>Claim a Paper</h3>
					<div class="claim-form">
						<input type="text" bind:value={claimDoi} placeholder="Enter DOI" class="doi-input" />
						<button class="btn-sm confirm" on:click={handleClaim}>Claim</button>
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
									<button class="btn-sm" on:click={() => handleUnClaim(doi)}>Remove</button>
								</div>
							{/each}
						</div>
					{/if}
				</div>

				<div class="author-merge-section">
					<h3>Report Duplicate Profile</h3>
					<p class="section-hint">
						If another author profile represents the same person, submit a merge request. A human
						will review it before any changes are applied.
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
							<button class="btn-sm confirm" on:click={handleAuthorMergeRequest}
								>Submit Request</button
							>
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
										class="btn-sm"
										on:click={() => handleCancelMergeRequest(req.other_semantic_id)}>Cancel</button
									>
								</div>
							{/each}
						</div>
					{/if}
				</div>
			</div>
		{/if}

		<AllWorks
			semanticId={data.conf.semanticId}
			{entityAtts}
			{discAuthorNames}
			initialPapers={data.initialPapers}
			initialSliceEnd={data.initialWorksSliceEnd}
			initialTotalPapers={data.initialTotalPapers}
			disownedWids={disownedSet}
			mergedPairs={mergedPairsState}
			isOwner={data.isOwner}
			on:disown={handleDisown}
			on:undisown={handleUndisown}
			on:merge={handleMerge}
			on:unmerge={handleUnmerge}
		/>
	</section>
{/if}

<section id="similars" class="shadowy padded marged">
	<p>
		Rankless uses publication and citation data sourced from OpenAlex, an open and comprehensive
		bibliographic database. While OpenAlex provides broad and valuable coverage of the global
		research landscape, it—like all bibliographic datasets—has inherent limitations. These include
		incomplete records, variations in author disambiguation, differences in journal indexing, and
		delays in data updates. As a result, some metrics and network relationships displayed in
		Rankless may not fully capture the entirety of a scholar's output or impact.
	</p>
	{#if data.aboutParagraph.footText.length > 0}<p>{@html data.aboutParagraph.footText}</p>{/if}
	<h3>Explore {prettifyRoot(data.conf.rootType)} with similar magnitude of impact</h3>
	<div class="similars-grid">
		{#each data.view.similars as sim}
			<span>
				<RandTreeLink
					semanticId={sim.semanticId}
					name={sim.name}
					rootType={data.conf.rootType}
					treeSpecs={data.treeSpecs}
				/>
			</span>
		{/each}
	</div>
</section>

<style>
	.heighted {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
	}

	@media (max-width: 800px) {
		#era > div {
			width: 100%;
		}
	}

	@media (min-width: 801px) {
		#overview {
			display: flex;
			flex-wrap: wrap;
			align-items: stretch;
			gap: 40px;
		}
	}

	#overview {
		margin-top: var(--unified-margin);
		margin-bottom: var(--unified-margin);
	}

	#name-block {
		flex: 8;
	}

	#era {
		flex: 4;
		display: flex;
		flex-direction: column;
		justify-content: space-evenly;
	}

	#era > div {
		aspect-ratio: 2.5;
	}

	.dag-link {
		font-size: 0.75rem;
		opacity: 0.4;
		text-decoration: none;
		color: var(--color-text);
		transition: opacity 0.15s;
		padding: 2px 0;
	}

	.dag-link:hover {
		opacity: 0.8;
	}

	.main-block {
		margin-bottom: 0px;
	}

	#similars {
		margin-bottom: 40px;
	}

	.similars-grid {
		width: 100%;
		padding-top: 28px;
		padding-bottom: 48px;
		display: flex;
		flex-wrap: wrap;
		justify-content: space-evenly;
		align-items: stretch;
		gap: 40px;
	}

	.similars-grid > span {
		min-width: 180px;
		flex: 1 0 21%;
		padding: 6px;
		border-bottom: solid var(--color-theme-blue) 3px;
		background: rgba(var(--color-range-15), 0.1);
	}

	.indexed-subtext {
		opacity: 0.8;
		font-size: 0.8rem;
	}

	h2 {
		margin-bottom: 8px;
		text-align: center;
	}

	#abstract summary {
		cursor: pointer;
		list-style: none;
	}

	#abstract summary::-webkit-details-marker {
		display: none;
	}

	#abstract summary h2 {
		display: inline;
		font-size: 0.9rem;
		opacity: 0.5;
	}

	#abstract p {
		font-size: 0.9rem;
		line-height: 1.6;
		opacity: 0.85;
	}

	.abstract-text.abstract-truncated {
		display: -webkit-box;
		-webkit-line-clamp: 4;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.abstract-loading {
		opacity: 0.35;
		font-size: 0.8rem;
	}

	section {
		scroll-margin-top: 90px;
	}

	/* Owner tools */
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

	.claim-section h3,
	.author-merge-section h3 {
		font-size: var(--text-base);
		margin: 0 0 6px 0;
		text-align: left;
	}

	.section-hint {
		font-size: var(--text-xs);
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

	.doi-input,
	.note-input {
		max-width: 400px;
		font-size: var(--text-sm);
		padding: 4px 8px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: transparent;
		color: var(--color-text);
		font-family: inherit;
	}

	.doi-input {
		flex: 1;
	}

	.note-input {
		resize: vertical;
	}

	.claim-status {
		font-size: var(--text-xs);
		opacity: 0.5;
		margin-left: 8px;
	}

	.claimed-list,
	.pending-requests {
		margin-top: 8px;
	}

	.claimed-list h4,
	.pending-requests h4 {
		font-size: var(--text-sm);
		opacity: 0.5;
		margin: 0 0 4px 0;
	}

	.claimed-row {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: var(--text-sm);
		padding: 2px 0;
	}

	.req-note {
		font-size: var(--text-xs);
		opacity: 0.5;
		font-style: italic;
	}
</style>
