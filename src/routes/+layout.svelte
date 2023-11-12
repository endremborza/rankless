<script lang="ts">
	import { APP_NAME } from '$lib/constants';
	import { base } from '$app/paths';
	import logoImg from '$lib/assets/images/icons/logo.png';
	import './styles.css';

	const year = new Date().getFullYear();
</script>

<svelte:head>
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
	<link
		href="https://fonts.googleapis.com/css2?family=Roboto+Mono&family=Roboto:ital,wght@0,300;0,400;0,500;0,700;1,300;1,400;1,500;1,700&display=swap"
		rel="stylesheet"
	/>
	<title>{APP_NAME}</title></svelte:head
>

<div class="main-fix">
	<div class="main-head">
		<div class="hl">
			<a href={`${base}/`}><img src={logoImg} height="40px" width="40px" alt="logo" /></a>
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
		background-color: rgba(var(--color-range-15), 0.55);
	}

	.main-fix .main-content {
		flex: 1 1 auto;
	}

	.main-fix .main-foot {
		display: flex;
		align-items: center;
		justify-content: center;
		flex: 0 0 40px;
		background-color: rgba(var(--color-range-65), 0.6);
	}

	.hl {
		display: flex;
		align-items: center;
		padding: 8px;
		padding-left: 40px;
	}

	.hr {
		padding: 8px;
		padding-right: 40px;
		display: flex;
		align-items: center;
	}

	.hr > a {
		margin-left: 10px;
	}

	a {
		text-decoration: none;
		color: rgba(10, 10, 10, 0.85);
	}
</style>
