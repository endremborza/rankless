<script lang="ts">
	import { base } from '$app/paths';
	import { APP_NAME } from '$lib/constants';
	import PathLogo from './PathLogo.svelte';

	export let size = 40;
	export let pad = 40;
	export let varColor = 'color-theme-darkgrey';
</script>

<div id="hl" style="padding-left: {pad}px;">
	<svg height="{size}px" width="{size}px" viewBox="0 0 20 20">
		<PathLogo />
	</svg>
	<span id="logo-text">
		<a href={`${base}/`} style="color: var(--{varColor})"> <b>{APP_NAME}</b></a>
		<span id="by-span" style="color: var(--{varColor})">by CCL</span>
	</span>
</div>

<style>
	#by-span {
		font-size: var(--text-xs);
	}

	#logo-text {
		padding-left: 3px;
		display: flex;
		flex-direction: column;
		justify-content: end;
		align-items: end;
	}

	#hl {
		display: flex;
		align-items: center;
		padding: 8px;
	}

	#logo-text > a > b {
		font-size: var(--text-base);
		padding-left: 15px;
	}

	#logo-text > a > b:hover {
		color: var(--color-theme-darkblue);
	}

	a {
		text-decoration: none;
	}
</style>
