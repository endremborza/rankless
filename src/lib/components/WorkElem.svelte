<script lang="ts">
	import type { AttributeLabels, AttributeLabel, OaPaperResp } from '$lib/tree-types';
	import { onMount } from 'svelte';
	import { getCachedPaper, setCachedPaper } from '$lib/stores';
	import { reconstructAbstractFromInvIndex } from '$lib/utils/paper-helpers';

	export let workId: number;
	export let citeText: string;
	export let attributeLabels: AttributeLabels;
	export let instId: number | undefined;

	let placeholder = 'Loading...';
	let title = '';
	let doi = '';
	let abstract = '';
	let abstractExpanded = false;
	let y = 0;
	let authors: { name: string; link: string; isOfInst: boolean }[] = [];
	let localCount = 0;

	let paperResp: OaPaperResp | undefined;
	let mounted = false;

	$: paperResp = getCachedPaper(workId);

	function getInstInfo(labels: AttributeLabels, id: number | undefined): [AttributeLabel, number] {
		let instAtts: AttributeLabel = { name: '', oaId: -1, specBaseline: 0 };
		let instOaNum = -1;
		let instLabs = labels?.institutions;
		if (instLabs != undefined && id != undefined) {
			let thisInstAtts = instLabs[id];
			if (thisInstAtts != undefined) {
				instAtts = thisInstAtts;
				instOaNum = instAtts.oaId || -1;
			}
		}
		return [instAtts, instOaNum];
	}

	$: [instAtts, instOaNum] = getInstInfo(attributeLabels, instId);
	$: instName = instAtts.name || '';
	$: fullInstName = instName.length > 50 ? 'affiliated' : `from ${instName}`;
	$: oaLink = `https://openalex.org/works/W${workId}`;
	$: errMsg = `Failed to load top paper from OpenAlex <a href="${oaLink}">link</a>`;
	$: href = doi.length > 0 ? doi : oaLink;

	$: updateByWorkId(workId);
	$: parsePaperResp(paperResp);

	function parsePaperResp(paperResp: OaPaperResp) {
		if (paperResp == undefined) return;
		let instOaId = `https://openalex.org/I${instOaNum}`;
		title = paperResp.title;
		doi = paperResp.doi;
		y = paperResp.year;
		abstract = paperResp.abstract;
		let outAuthors = [];
		localCount = 0;
		for (let aship of paperResp.authors) {
			let isOfInst = false;
			for (let aff of aship.institutions || []) {
				if (aff == instOaId) {
					isOfInst = true;
					localCount = localCount + 1;
					break;
				}
			}
			outAuthors.push({ name: aship.name, link: aship.link, isOfInst });
		}
		authors = outAuthors.sort((l, r) => Number(r.isOfInst) - Number(l.isOfInst));
	}
	function updateByWorkId(workId: number) {
		if (!mounted || workId == 0 || paperResp != undefined) return;
		let oaUrl = `https://api.openalex.org/works/W${workId}?select=publication_year,title,doi,authorships,abstract_inverted_index`;
		fetch(oaUrl)
			.then((resp) => {
				resp
					.json()
					.then((o) => {
						let abstract = reconstructAbstractFromInvIndex(o.abstract_inverted_index) ?? '';
						let authors = [];
						for (let aship of o.authorships) {
							let institutions = [];
							for (let aff of aship.institutions || []) {
								institutions.push(aff.id);
							}
							let lElems = aship.author.id.split('/');
							let link = `/oa-id/${lElems[lElems.length - 1]}`;
							authors.push({ name: aship.author.display_name, link, institutions });
						}
						paperResp = {
							title: o.title,
							doi: o.doi || '',
							year: o.publication_year,
							abstract,
							authors
						};
						setCachedPaper(workId, paperResp);
					})
					.catch(() => {
						placeholder = errMsg;
					});
			})
			.catch(() => {
				placeholder = errMsg;
			});
	}

	onMount(() => {
		mounted = true;
		updateByWorkId(workId);
	});
</script>

{#if title}
	<div id="main" class="padded">
		<row>
			<h2 class="hover-l">Top Paper:</h2>
			<p class="hover-s"><a {href} target="_blank">{@html title} ({y})</a></p>
		</row>
		{#if abstract}
			<div class="abstract-section">
				<p class="abstract-text" class:expanded={abstractExpanded}>{abstract}</p>
				{#if abstract.length > 300}
					<button class="expand-btn" on:click={() => (abstractExpanded = !abstractExpanded)}>
						{abstractExpanded ? '▴ less' : '▾ more'}
					</button>
				{/if}
			</div>
		{/if}
		{#if authors.length > 0}
			<row>
				<h4 class="hover-m">
					Author{authors.length > 1 ? 's' : ''}:
				</h4>
				<al class="hover-s">
					{#each authors.slice(0, 3).entries() as [i, author]}
						<a href={author.link} target="_blank"
							>{author.name}{author.isOfInst ? '*' : ''}{i < Math.min(authors.length - 1, 2)
								? ','
								: ''}
						</a>
					{/each}
					{#if authors.length > 3}
						<a href={oaLink} target="_blank">& {authors.length - 3} others</a>
					{/if}
				</al>
			</row>
		{/if}
		<row>
			<p class="hover-s">
				{citeText}
			</p>
		</row>
		<footnote class="hover-xs">
			{#if localCount > 0}*: author {fullInstName} ({localCount}/{authors.length}){/if}
		</footnote>
	</div>
{:else}
	<div class="loading-sign"><h4>{@html placeholder}</h4></div>
{/if}

<style>
	h2,
	h4 {
		margin: calc(var(--unified-padding) / 2);
	}
	h4 {
		text-align: center;
	}

	a {
		text-decoration: underline;
	}

	p a {
		display: -webkit-box;
		-webkit-line-clamp: 3;
		line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.abstract-section {
		font-size: min(0.85rem, 2.2vw);
		padding: 0 calc(var(--unified-padding) / 2);
	}

	.abstract-text {
		display: -webkit-box;
		-webkit-line-clamp: 3;
		line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
		margin: 0;
		line-height: 1.5;
		opacity: 0.85;
	}

	.abstract-text.expanded {
		display: block;
		overflow: visible;
		-webkit-line-clamp: unset;
		line-clamp: unset;
	}

	.expand-btn {
		background: none;
		border: none;
		padding: 2px 0;
		font-size: 0.75rem;
		opacity: 0.5;
		cursor: pointer;
		color: inherit;
	}

	.expand-btn:hover {
		opacity: 0.9;
	}

	@media (min-width: 1100px) {
		.abstract-text {
			display: block;
			overflow: visible;
			-webkit-line-clamp: unset;
			line-clamp: unset;
		}

		.expand-btn {
			display: none;
		}
	}

	row {
		width: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
	}

	al {
		display: flex;
		flex-direction: row;
		justify-content: space-around;
		flex-wrap: wrap;
		gap: calc(var(--unified-padding) / 2);
	}

	footnote {
		width: 100%;
		text-align: right;
	}

	.loading-sign {
		display: flex;
		align-items: center;
		justify-content: center;
	}

	#main {
		height: 100%;
		display: flex;
		flex-direction: column;
		justify-content: flex-start;
		gap: calc(var(--unified-padding) / 2);
		align-items: stretch;
		overflow-y: auto;
		padding-top: 0px;
	}
</style>
