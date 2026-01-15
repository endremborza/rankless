<script lang="ts">
	import SearchLogo from '$lib/components/SearchLogo.svelte';
	import SearchResults from '$lib/components/SearchResults.svelte';
	import TextedLogo from '$lib/components/TextedLogo.svelte';
	import PathLogo from '$lib/components/PathLogo.svelte';
	import SurveyPrompt from '$lib/components/SurveyPrompt.svelte';
	import { afterNavigate } from '$app/navigation';
	import { onMount } from 'svelte';
	import { slide } from 'svelte/transition';

	import type { RootType } from '$lib/tree-types';
	import { LATEST_YEAR, ROOT_TYPES } from '$lib/constants';
	import { prettifyRoot } from '$lib/text-format-util';
	import { resultsHidden } from '$lib/stores';

	export let data: { surveyShouldPrompt: boolean };
	let options: RootType[] = ROOT_TYPES.filter((e) => e != 'hit-papers');
	let cat: RootType = options[0];

	let mounted = false;
	let runner: number;

	function init(el: HTMLInputElement) {
		el.focus();
	}

	function focusSelect(e: FocusEvent) {
		resultsHidden.set(false);
		if (e.target != undefined) {
			(e.target as HTMLTextAreaElement).select();
		}
	}

	function onFocus() {
		resultsHidden.set(false);
	}

	onMount(() => {
		runner = setInterval(changeText, speed);
		mounted = true;
	});
	afterNavigate(() => {
		slimOpened = false;
		resultsHidden.set(true);
	});

	let slimOpened = false;
	let hideSearchButton = false;

	let searchTerm = '';

	function keyBind(key: { key: string }) {
		if (key.key == 'Escape') {
			resultsHidden.set(true);
		}
	}

	function setNoScroll(rHide: boolean) {
		if (mounted) {
			if (rHide) {
				document.body.classList.remove('no-scroll');
			} else {
				document.body.classList.add('no-scroll');
			}
		}
	}

	//typewriter
	let speed = 80;
	let stopAtEnd = 480;
	let texts = options.map(prettifyRoot);
	let wordInd = 0;
	let text: string = texts[wordInd];
	$: basePlaceholder = 'Explore ' + text;

	let letterInd = Math.floor(text.length / 2);
	let direction = +1;

	function changeText() {
		if (wordInd == texts.length) {
			wordInd = 0;
		}
		let word = texts[wordInd];
		text = word.slice(0, letterInd);
		if (letterInd == word.length) {
			clearInterval(runner);
			setTimeout(() => {
				runner = setInterval(changeText, speed);
			}, stopAtEnd);
		}
		letterInd += direction;
		if (letterInd == word.length) {
			direction = -1;
		}
		if (letterInd == 0) {
			direction = 1;
			wordInd = wordInd + 1;
		}
	}

	$: currenHidden = $resultsHidden;
	$: placeholder = currenHidden ? '' : basePlaceholder;
	$: setNoScroll(currenHidden);
</script>

<svelte:window on:keydown={keyBind} />
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div id="main-fix">
	{#if $resultsHidden}
		<a href="/" id="head-l" class="head-side-elem shadowy">
			<svg viewBox="0 0 20 20">
				<PathLogo />
			</svg>
		</a>
	{:else}
		<!-- svelte-ignore a11y-no-static-element-interactions -->
		<!-- svelte-ignore a11y-click-events-have-key-events -->
		<span id="result-closer" class="marged" on:click={() => resultsHidden.set(true)}>&#10006;</span>
	{/if}
	{#if !hideSearchButton}
		<div class="head-side-elem shadowy" id="head-r" on:click={onFocus}>
			{#if !$resultsHidden}
				<input
					in:slide={{ duration: 300, axis: 'x' }}
					bind:value={searchTerm}
					on:focus={focusSelect}
					use:init
					{placeholder}
					type="text"
					id="search-input"
				/>
				<div in:slide={{ duration: 200, delay: 250, axis: 'y' }}>
					{#each options as opt}
						<label>
							<input
								checked={cat === opt}
								on:change={() => {
									cat = opt;
								}}
								type="radio"
								name="category"
								value={opt}
							/>
							{prettifyRoot(opt)}
						</label>
					{/each}
				</div>
			{:else}
				<svg
					id="search-logo"
					viewBox="-10 -10 60 50"
					fill="none"
					xmlns="http://www.w3.org/2000/svg"
				>
					<SearchLogo />
				</svg>
			{/if}
		</div>
	{/if}
	<SearchResults {searchTerm} {cat} />
	<div
		id="main-content"
		on:click={() => {
			slimOpened = false;
		}}
	>
		<slot />
	</div>
	<div id="main-foot">
		<TextedLogo pad={0} size={30} />
		<span>{LATEST_YEAR}</span>
		<div id="foot-r"><a href="/#contact">Contact</a></div>
	</div>
</div>

{#if data.surveyShouldPrompt}
	<SurveyPrompt />
{/if}

<style>
	svg {
		--svg-size: min(min(30px, 5.5vw), 3.8svh);
		width: var(--svg-size);
		height: var(--svg-size);
	}

	label {
		color: var(--color-theme-darkblue);
	}

	.head-side-elem {
		position: fixed;
		top: 3px;
		padding: 7px;
		margin-left: var(--unified-margin);
		margin-right: var(--unified-margin);
		margin-top: 1.2svh;
		border: solid var(--color-theme-darkblue) 2px;
		cursor: pointer;
		background-color: var(--color-theme-white);
		z-index: 10;
		pointer-events: auto;
	}

	#main-fix {
		display: flex;
		flex-flow: column;
		min-height: 100dvh;
	}

	#head-l {
		left: 0px;
		padding-bottom: 4px;
		z-index: 15;
	}

	#head-r {
		right: 0px;
		padding-top: 1px;
		border-top: solid var(--color-theme-darkblue) 7px;
		z-index: 25;
	}

	#search-logo {
		position: relative;
		left: 0px;
		top: 0px;
		pointer-events: none;
		z-index: 7;
	}

	#search-input {
		width: 90vw;
		height: 35px;
		border: 0px;
		font-size: 22px;
		font-style: italic;
		background: none;
		z-index: 25;
		text-indent: 25px;
	}

	#search-input:hover {
		border-top-color: var(--color-theme-white);
		background-color: rgba(171, 171, 171, 0.9);
		color: white;
	}

	input#search-input:focus {
		outline: none;
	}

	#result-closer {
		transition: transform 0.2s ease;
		position: fixed;
		top: 0px;
		left: 0px;
		font-size: 37px;
		text-align: center;
		cursor: pointer;
		z-index: 30;
	}

	@media (max-width: 1000px) {
		#result-closer {
			top: 100px;
		}
	}

	#result-closer:hover {
		font-size: 40px;
		color: var(--color-theme-darkblue);
	}

	#main-content {
		flex: 1 1 auto;
	}

	#main-foot {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-left: 3vw;
		padding-right: 3vw;
		padding-top: 3px;
		padding-bottom: 3px;
		background-color: var(--color-theme-yellow);
		color: var(--color-theme-darkgrey);
		flex: 0 0 50px;
		z-index: 1;
		height: min(50px, 3svh);
	}

	#foot-r > a {
		color: var(--color-theme-darkgrey);
	}
</style>
