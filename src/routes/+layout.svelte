<script lang="ts">
	import {APP_NAME} from '$lib/constants';
	import {base} from '$app/paths';
	import logoImg from '$lib/assets/images/icons/logo.png';
	import './styles.css';
	import PathLogo from '$lib/components/PathLogo.svelte';

	const year = new Date().getFullYear();
</script>

<svelte:head>
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
	<link href="https://fonts.googleapis.com/css2?family=Roboto+Mono&family=Roboto:ital,wght@0,300;0,400;0,500;0,700;1,300;1,400;1,500;1,700&display=swap"
		rel="stylesheet" />
	<title>{APP_NAME}</title>
</svelte:head>

<div class="main-fix">
	<div class="main-head">
		<div class="hl">
			<a href={`${base}/`}><svg height="40px" width="40px" viewBox="0 0 20 20">
					<PathLogo />
				</svg></a>
			<a href={`${base}/`}> <b>{APP_NAME}</b></a>
		</div>
		<div class="hr">
			<a href={`${base}/about`}>About</a>
			<a href={`${base}/methods`}>Methods</a>
		</div>
	</div>
	<div class="main-content">
		<slot />
	</div>
	<div class="main-foot">{APP_NAME} {year}</div>
</div>

<style>
	.main-fix {
		display: flex;
		flex-flow: column;
		height: 100%;
	}

	.main-fix .main-head {
		flex: 0 0 60px;
		display: flex;
		justify-content: space-between;
		/* background-color: rgba(var(--color-range-15), 0.55); */
		background-color: var(--color-theme-yellow);
		z-index: 10;
	}

	.main-fix .main-content {
		flex: 1 1 auto;
	}

	.main-fix .main-foot {
		display: flex;
		align-items: center;
		justify-content: center;
		flex: 0 0 70px;
		/* background-color: rgba(var(--color-range-65), 0.6); */
		background-color: var(--color-theme-yellow);
		z-index: 10;
	}

	.hl {
		display: flex;
		align-items: center;
		padding: 8px;
		padding-left: 40px;
	}

	.hl>a>b {
		font-size: 1.3rem;
		padding-left: 15px;
		color: #4F4F4F;
	}
	
	.hl > a > b:hover {
    /* Add styles for hover state here */
    /* For example, change text color */
    	color: #0F62FE;
	}

	.hr {
		padding: 8px;
		padding-right: 40px;
		display: flex;
		align-items: center;
	}

	.hr>a {
		margin-left: 10px;
	}

	a {
		text-decoration: none;
		color: #4F4F4F;
	}
	.hr a:hover {
    /* Add styles for hover state here */
    /* For example, change text color */
    	color: #0F62FE;
		font-weight: bold;
	}
</style>
