<script lang="ts">
	import TypeWriter from '$lib/components/TypeWriter.svelte';
	import { entToLink } from '$lib/tree-functions';

	export let data;

	let texts = ['topics', 'geographies', 'publications', 'relationships'];
	let wordInd = 0;
</script>

<div id="typewrite">
	<span id="tw-full">
		<span id="tw-1"> explore </span>
		<span id="tw-2">
			<TypeWriter {texts} speed={50} bind:wordInd />
		</span>
	</span>
</div>

<div id="tops">
	{#each data.tops as entityTop}
		<div>
			<h3>{entityTop.name}</h3>
			<ul>
				{#each entityTop.entities as ent}
					<li><a href={entToLink({ ...ent, rootType: entityTop.name })}>{ent.name}</a></li>
				{/each}
			</ul>
		</div>
	{/each}
</div>

<style>
	h3 {
		text-align: center;
	}

	#typewrite {
		position: fixed;
		top: 0px;
		height: 7svh;
		z-index: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 100%;
	}

	#tops {
		margin-top: 10svh;
		display: flex;
		flex-wrap: wrap;
		align-items: space-around;
		justify-content: center;
	}

	#tops > div {
		width: 400px;
		margin: 100px;
		padding: 25px;
		border-radius: 30px;
		background: var(--color-theme-pink);
	}

	#tw-full {
		width: min(290px, 60vw);
		font-size: min(1.4rem, 4vw);
		left: 20vw;
	}

	#tw-2 {
		background-color: var(--color-theme-darkblue);
		color: var(--color-theme-white);
	}
</style>
