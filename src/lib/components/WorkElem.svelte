<script lang="ts">
	import { formatNumber } from '$lib/text-format-util';
	import type { AttributeLabels } from '$lib/tree-types';
	import { onMount } from 'svelte';

	export let workId: number;
	export let workCitations: number;
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
	<div>
		<h4 class="hover-l">Most Cited Paper</h4>
	</div>
	<div>
		<h3 class="hover-xl"><a {href} target="_blank">{title}</a> ({y})</h3>
	</div>
	<div>
		{#if doi}
			<span class="hover-m">
				<a href={doi} target="_blank">{doi}</a>
			</span>
		{/if}
		<span class="hover-m">
			{formatNumber(workCitations, 0)} relevant citations
		</span>
	</div>
	{#if authors.length > 0}
		<div>
			<h3 class="hover-m" style="flex: 3">
				{authors.length} author{authors.length > 1 ? 's' : ''}
				{#if localCount > 0}({localCount} {fullInstName}){/if}
			</h3>
			<al class="hover-m" style="flex: 7">
				{#each authors.slice(0, 3) as author}
					<a href={author.link} class={author.isOfInst ? 'bold' : ''} target="_blank"
						>{author.name}</a
					>
				{/each}

				{#if authors.length > 3}
					<a {href} target="_blank">{authors.length - 3} others</a>
				{/if}
			</al>
		</div>
	{/if}
	<hr />
{/if}

<style>
	:root {
		--side-pad: 20px;
	}

	a:hover {
		font-weight: inherit;
	}

	a {
		text-decoration: underline;
	}

	h3,
	h4 {
		text-align: center;
		margin: 0px;
		padding-left: var(--side-pad);
		padding-right: var(--side-pad);
	}

	span {
		padding-left: var(--side-pad);
		padding-right: var(--side-pad);
	}

	hr {
		width: 80%;
	}

	div {
		width: 100%;
		margin: 12px;
		display: flex;
		flex-direction: row;
		justify-content: space-around;
		align-items: center;
	}

	al {
		display: flex;
		flex-direction: row;
		justify-content: space-around;
		align-items: center;
		padding-right: var(--side-pad);
	}

	al > a {
		padding-left: 5px;
	}

	.bold {
		font-weight: 600;
	}
</style>
