<script lang="ts">
	import type { AttributeLabels } from '$lib/tree-types';
	import { onMount } from 'svelte';

	export let workId: number;
	export let citeText: string;
	export let attributeLabels: AttributeLabels;
	export let instId: number | undefined;

	let title = '';
	let doi = '';
	let y = 0;
	let authors: { name: string; link: string; isOfInst: boolean }[] = [];
	let localCount = 0;

	$: instAtts = instId === undefined ? { name: '' } : attributeLabels?.institutions[instId];
	$: instName = instAtts?.name || '';
	$: instOaNum = (attributeLabels?.institutions || {})[instId || 0]?.oaId || -1;
	$: fullInstName = instName.length > 50 ? 'affiliated' : `from ${instName}`;
	$: href = `https://openalex.org/works/W${workId}`;

	onMount(() => {
		if (workId == 0) return;
		let oaUrl = `https://api.openalex.org/works/W${workId}?select=publication_year,title,doi,authorships`;
		let instOaId = `https://openalex.org/I${instOaNum}`;
		fetch(oaUrl).then((resp) => {
			resp.json().then((o) => {
				doi = o.doi;
				y = o.publication_year;
				for (let aship of o.authorships) {
					let isOfInst = false;
					for (let aff of aship.institutions || []) {
						if (aff.id == instOaId) {
							isOfInst = true;
							localCount = localCount + 1;
							break;
						}
					}
					authors.push({ name: aship.author.display_name, link: aship.author.id, isOfInst });
				}
				authors = authors.sort((l, r) => Number(r.isOfInst) - Number(l.isOfInst));
				title = o.title;
			});
		});
	});
</script>

{#if title}
	<div id="main" class="padded">
		<h4 class="hover-l">Top Paper</h4>
		<row>
			<rowheader class="hover-m">Title:</rowheader>
			<h3 class="hover-l"><a {href} target="_blank">{title}</a> ({y})</h3>
		</row>
		{#if doi}
			<row>
				<rowheader class="hover-m">Doi:</rowheader>
				<span class="hover-m">
					<a href={doi} target="_blank">{doi}</a>
				</span>
			</row>
		{/if}
		{#if authors.length > 0}
			<row>
				<rowheader class="hover-m">
					Author{authors.length > 1 ? 's' : ''}:
				</rowheader>
				<al class="hover-m">
					{#each authors.slice(0, 3).entries() as [i, author]}
						<a href={author.link} target="_blank"
							>{author.name}{author.isOfInst ? '*' : ''}{i < Math.min(authors.length - 1, 2)
								? ','
								: ''}
						</a>
					{/each}
					{#if authors.length > 3}
						<a {href} target="_blank">& {authors.length - 3} others</a>
					{/if}
				</al>
			</row>
		{/if}
		<row>
			<rowheader class="hover-m">Citations: </rowheader>
			<span class="hover-m">
				{citeText}
			</span>
		</row>
		<footnote class="hover-s">
			{#if localCount > 0}*: author of {fullInstName} ({localCount}/{authors.length}){/if}
		</footnote>
		<hr />
	</div>
{/if}

<style>
	h3,
	h4 {
		margin: 0px;
	}

	a {
		text-decoration: underline;
	}

	row {
		width: 100%;
		display: flex;
		gap: 20px;
		justify-content: space-between;
	}

	rowheader {
		flex: 2;
	}

	hr {
		width: 100%;
	}

	al {
		display: flex;
		flex-direction: row;
		justify-content: space-around;
		align-items: center;
	}

	al > a {
		padding-left: 15px;
	}

	footnote {
		width: 100%;
		text-align: right;
	}

	#main {
		height: 100%;
		display: flex;
		flex-direction: column;
		justify-content: space-around;
		align-items: start;
	}
</style>
